import json
import os
import uuid
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from common import ApiError, log_event, new_ticket_record, now, notification_required, should_process_operation, update_ticket_record


dynamodb = boto3.resource("dynamodb")
dynamodb_client = boto3.client("dynamodb")
tickets = dynamodb.Table(os.environ["TICKETS_TABLE"])
idempotency = dynamodb.Table(os.environ["IDEMPOTENCY_TABLE"])
audits = dynamodb.Table(os.environ["AUDIT_TABLE"])


def _audit(ticket_id, action, user_id, timestamp, changes):
    return {"Put": {"TableName": os.environ["AUDIT_TABLE"], "Item": {
        "ticket_id": {"S": ticket_id}, "event_sort": {"S": f"{timestamp}#{uuid.uuid4()}"},
        "action": {"S": action}, "performed_by": {"S": user_id}, "performed_at": {"S": timestamp},
        "changes": {"S": json.dumps(changes, separators=(",", ":"), default=str)}}}}


def _complete(key, ticket_id, at):
    return {"Update": {"TableName": os.environ["IDEMPOTENCY_TABLE"],
        "Key": {"idempotency_key": {"S": key}}, "UpdateExpression": "SET #s=:done, completed_at=:at",
        "ConditionExpression": "attribute_exists(idempotency_key) AND #s IN (:pending, :submitting, :sent, :ambiguous, :failed)",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":done": {"S": "COMPLETED"}, ":at": {"S": at},
                                      ":pending": {"S": "PENDING"}, ":submitting": {"S": "SUBMITTING"},
                                      ":sent": {"S": "SENT"}, ":ambiguous": {"S": "AMBIGUOUS"},
                                      ":failed": {"S": "FAILED"}}}}


def _set_terminal_status(key, status, message):
    """Terminal failure transitions never replace completed or newer terminal state."""
    try:
        idempotency.update_item(Key={"idempotency_key": key},
            UpdateExpression="SET #s=:next, last_error=:error",
            ConditionExpression="#s IN (:pending, :submitting, :sent, :ambiguous)",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":next": status, ":error": message,
                                       ":pending": "PENDING", ":submitting": "SUBMITTING",
                                       ":sent": "SENT", ":ambiguous": "AMBIGUOUS"})
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise


def process(op):
    method, ticket_id, body, user = op["method"], op["ticket_id"], op.get("body", {}), op["user"]
    key, actor, at = op["operation_id"], user["sub"], now()
    if method == "POST":
        item = new_ticket_record(ticket_id, body, actor, at)
        txn = [{"Put": {"TableName": os.environ["TICKETS_TABLE"], "Item": {k: _av(v) for k,v in item.items()},
                         "ConditionExpression": "attribute_not_exists(ticket_id)"}},
               _audit(ticket_id, "CREATE", actor, at, item), _complete(key, ticket_id, at)]
        notify = notification_required(method, None, item["priority"])
        if notify:
            txn.append(_notification(ticket_id, key, at))
        dynamodb_client.transact_write_items(TransactItems=txn)
        return
    current = tickets.get_item(Key={"ticket_id": ticket_id}, ConsistentRead=True).get("Item")
    if not current:
        raise ValueError("Ticket not found")
    prior = dict(current)
    if method not in ("PUT", "DELETE"):
        raise ValueError("Unsupported operation")
    current, action = update_ticket_record(current, body, user, at, method)
    expected = int(prior["version"])
    changed = {k: current[k] for k in current if prior.get(k) != current[k]}
    txn = [{"Put": {"TableName": os.environ["TICKETS_TABLE"], "Item": {k: _av(v) for k,v in current.items()},
                     "ConditionExpression": "version = :v AND created_by = :owner",
                     "ExpressionAttributeValues": {":v": {"N": str(expected)}, ":owner": {"S": current["created_by"]}}}},
           _audit(ticket_id, action, actor, at, changed), _complete(key, ticket_id, at)]
    notify = notification_required(method, prior.get("priority"), current.get("priority"))
    if notify: txn.append(_notification(ticket_id, key, at))
    dynamodb_client.transact_write_items(TransactItems=txn)
    # Notification intent is committed transactionally; the scheduled outbox worker
    # publishes it separately and records definite versus ambiguous outcomes.


def _av(value):
    if isinstance(value, bool): return {"BOOL": value}
    if isinstance(value, int): return {"N": str(value)}
    if isinstance(value, (float, Decimal)): return {"N": str(value)}
    if value is None: return {"NULL": True}
    if isinstance(value, list): return {"L": [_av(v) for v in value]}
    if isinstance(value, dict): return {"M": {k: _av(v) for k,v in value.items()}}
    return {"S": str(value)}


def _notification(ticket_id, key, at):
    nid = f"{ticket_id}#{key}"
    return {"Put": {"TableName": os.environ["NOTIFICATION_TABLE"], "Item": {
        "notification_id": {"S": nid}, "ticket_id": {"S": ticket_id}, "operation_id": {"S": key},
        "notification_type": {"S": "CRITICAL_TICKET"}, "status": {"S": "PENDING"}, "created_at": {"S": at}}}}


def handler(event, context):
    failures = []
    for record in event.get("Records", []):
        op = {}
        try:
            op = json.loads(record["body"])
            # A completed operation is a safe duplicate no-op.
            state = idempotency.get_item(Key={"idempotency_key": op["operation_id"]}, ConsistentRead=True).get("Item", {})
            if should_process_operation(state.get("status")): process(op)
        except ClientError as exc:
            log_event("write_retryable_aws_failure", message_id=record.get("messageId"),
                      error_code=exc.response.get("Error", {}).get("Code", "Unknown"),
                      error_message=exc.response.get("Error", {}).get("Message", "No details available"),
                      cancellation_reasons=exc.response.get("CancellationReasons", []))
            if exc.response.get("Error", {}).get("Code") == "TransactionCanceledException" and op:
                try:
                    state = idempotency.get_item(Key={"idempotency_key": op["operation_id"]}, ConsistentRead=True).get("Item", {})
                    latest = tickets.get_item(Key={"ticket_id": op["ticket_id"]}, ConsistentRead=True).get("Item")
                    expected = op.get("body", {}).get("version")
                    if state.get("status") == "COMPLETED":
                        continue
                    if latest and isinstance(expected, int) and int(latest.get("version", 0)) != expected:
                        _set_terminal_status(op["operation_id"], "CONFLICT",
                            "Ticket version conflict; retrieve the latest ticket and retry")
                        continue
                except Exception:
                    pass
            failures.append({"itemIdentifier": record["messageId"]})
        except (ApiError, ValueError, PermissionError, RuntimeError) as exc:
            log_event("write_terminal_failure", message_id=record.get("messageId"), error_type=type(exc).__name__)
            try:
                if not op:
                    raise ValueError("Malformed queue operation")
                result_status = "CONFLICT" if isinstance(exc, ApiError) and exc.status == 409 else "FAILED"
                _set_terminal_status(op["operation_id"], result_status, str(exc)[:500])
            except Exception:
                failures.append({"itemIdentifier": record["messageId"]})
        except Exception:
            log_event("write_retryable_failure", message_id=record.get("messageId"), error_type="UnhandledException")
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
