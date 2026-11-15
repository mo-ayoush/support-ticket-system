import json
import os
import time
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from common import ApiError, handle_error, identity, is_admin, now, parse_body, request_fingerprint, response, set_cors_origin, validate_idempotency_key, validate_write

IDEMPOTENCY_TTL_SECONDS = 30 * 24 * 60 * 60
SUBMISSION_CLAIM_TTL_SECONDS = 300
dynamodb = boto3.resource("dynamodb")
# SQS sends must not be silently retried after a connection outcome becomes unknown.
sqs = boto3.client("sqs", config=Config(retries={"mode": "standard", "total_max_attempts": 1}))
records = dynamodb.Table(os.environ["IDEMPOTENCY_TABLE"])
tickets = dynamodb.Table(os.environ["TICKETS_TABLE"])


def _definite_rejection(exc):
    metadata = exc.response.get("ResponseMetadata", {})
    status = metadata.get("HTTPStatusCode")
    return isinstance(status, int) and 400 <= status < 500 and status != 408


def _claim_submission(item):
    key = item["idempotency_key"]
    status = item.get("status")
    now_epoch = int(time.time())
    if status == "SUBMITTING":
        claimed_at = int(item.get("submission_claimed_at", 0))
        if now_epoch - claimed_at >= SUBMISSION_CLAIM_TTL_SECONDS:
            try:
                records.update_item(Key={"idempotency_key": key},
                    UpdateExpression="SET #s=:ambiguous, last_error=:reason",
                    ConditionExpression="#s=:submitting AND submission_claim_id=:claim",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={":ambiguous": "AMBIGUOUS", ":submitting": "SUBMITTING",
                    ":claim": item.get("submission_claim_id", ""),
                                               ":reason": "Submission claim expired; acceptance is unknown"})
            except ClientError:
                pass
            return None, records.get_item(Key={"idempotency_key": key}, ConsistentRead=True).get("Item", item)
        return None, item
    if status != "PENDING":
        return None, item
    claim_id = str(uuid.uuid4())
    try:
        records.update_item(Key={"idempotency_key": key},
            UpdateExpression="SET #s=:submitting, submission_claim_id=:claim, submission_claimed_at=:claimed_epoch REMOVE last_error",
            ConditionExpression="#s=:pending",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":submitting": "SUBMITTING", ":pending": "PENDING",
                                       ":claim": claim_id, ":claimed_epoch": now_epoch})
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        current = records.get_item(Key={"idempotency_key": key}, ConsistentRead=True).get("Item", item)
        return None, current
    return claim_id, {**item, "status": "SUBMITTING", "submission_claim_id": claim_id,
                      "submission_claimed_at": now_epoch}


def _claim_condition(claim_id):
    return "#s=:submitting AND submission_claim_id=:claim", {":submitting": "SUBMITTING", ":claim": claim_id}


def _set_claim_state(key, claim_id, state, error):
    condition, values = _claim_condition(claim_id)
    values.update({":next": state, ":error": error})
    try:
        records.update_item(Key={"idempotency_key": key},
            UpdateExpression="SET #s=:next, last_error=:error REMOVE submission_claim_id, submission_claimed_at",
            ConditionExpression=condition, ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues=values)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise


def handler(event, context):
    set_cors_origin(event)
    try:
        user = identity(event)
        method = event.get("httpMethod")
        path_parameters = event.get("pathParameters") or {}
        ticket_id = path_parameters.get("ticket_id")
        key = next((value for name, value in (event.get("headers") or {}).items()
                    if name.lower() == "idempotency-key"), None)
        if not validate_idempotency_key(key):
            raise ApiError(400, "Idempotency-Key must be 8-128 letters, digits, dots, underscores, colons, or hyphens")
        body = parse_body(event)
        if method in ("POST", "PUT"):
            validate_write(body, method)
        if method == "DELETE" and (set(body) != {"version"} or type(body.get("version")) is not int or body["version"] < 1):
            raise ApiError(400, "DELETE body must contain the positive integer version last read")
        if method not in ("POST", "PUT", "DELETE"):
            raise ApiError(405, "Unsupported write method")
        timestamp = int(time.time())
        old = records.get_item(Key={"idempotency_key": key}, ConsistentRead=True).get("Item")
        if method == "POST":
            if old and int(old.get("expires_at", 0)) > timestamp:
                ticket_id = old["ticket_id"]
            else:
                ticket_id = str(uuid.uuid4())
        elif not ticket_id:
            raise ApiError(400, "ticket_id path parameter is required")
        # Binding the key to user and operation prevents accidental cross-operation reuse.
        operation_hash = request_fingerprint(user["sub"], method, ticket_id, body)
        if old and int(old.get("expires_at", 0)) > timestamp:
            if old.get("operation_hash") != operation_hash:
                raise ApiError(409, "Idempotency-Key was already used for a different operation")
            ticket_id = old["ticket_id"]
            if old.get("status") == "SUBMITTING":
                _, old = _claim_submission(old)
            if old.get("status") != "PENDING":
                return response(202, {"operation_id": key, "ticket_id": ticket_id, "status": old.get("status", "PENDING")},
                                {"Location": f"/{os.environ.get('API_STAGE_NAME', 'v1')}/requests/{key}"})
            item = old
        else:
            # Reject invalid or unauthorized targets before queueing so request-status polling
            # cannot become an oracle for other users' ticket IDs. The writer repeats these checks.
            ticket_owner = user["sub"]
            if method in ("PUT", "DELETE"):
                target = tickets.get_item(Key={"ticket_id": ticket_id}, ConsistentRead=True).get("Item")
                if not target or (not is_admin(user) and target.get("created_by") != user["sub"]):
                    raise ApiError(404, "Ticket not found")
                if target.get("status") == "DELETED":
                    raise ApiError(409, "Deleted tickets cannot be modified")
                ticket_owner = target["created_by"]
            item = {"idempotency_key": key, "ticket_id": ticket_id, "created_at": now(),
                    "created_by": user["sub"], "ticket_owner": ticket_owner,
                    "expires_at": timestamp + IDEMPOTENCY_TTL_SECONDS, "status": "PENDING",
                    "operation_hash": operation_hash,
                    "operation": {"method": method, "ticket_id": ticket_id, "body": body,
                                  "user": user, "operation_id": key}}
            try:
                records.put_item(Item=item,
                    ConditionExpression="attribute_not_exists(idempotency_key) OR expires_at <= :now",
                    ExpressionAttributeValues={":now": timestamp})
            except ClientError as put_error:
                if put_error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                    raise
                raced = records.get_item(Key={"idempotency_key": key}, ConsistentRead=True).get("Item")
                if not raced or int(raced.get("expires_at", 0)) <= timestamp or raced.get("operation_hash") != operation_hash:
                    raise ApiError(409, "Idempotency-Key was concurrently used for a different operation")
                ticket_id = raced["ticket_id"]
                if raced.get("status") == "SUBMITTING":
                    _, raced = _claim_submission(raced)
                if raced.get("status") != "PENDING":
                    return response(202, {"operation_id": key, "ticket_id": ticket_id, "status": raced.get("status", "PENDING")},
                                    {"Location": f"/{os.environ.get('API_STAGE_NAME', 'v1')}/requests/{key}"})
                item = raced
        claim_id, claimed_item = _claim_submission(item)
        if not claim_id:
            return response(202, {"operation_id": key, "ticket_id": ticket_id,
                                  "status": claimed_item.get("status", "PENDING")},
                            {"Location": f"/{os.environ.get('API_STAGE_NAME', 'v1')}/requests/{key}"})
        try:
            sqs.send_message(QueueUrl=os.environ["WRITE_QUEUE_URL"], MessageBody=json.dumps(item["operation"]),
                             MessageGroupId=ticket_id, MessageDeduplicationId=key)
        except ClientError as exc:
            if _definite_rejection(exc):
                _set_claim_state(key, claim_id, "PENDING", "SQS_REJECTED:" + exc.response.get("Error", {}).get("Code", "Unknown"))
                raise
            try:
                _set_claim_state(key, claim_id, "AMBIGUOUS", exc.response.get("Error", {}).get("Code", "SQSOutcomeUnknown"))
            except ClientError:
                pass
            raise ApiError(503, "Queue submission outcome is ambiguous; check this operation's status before manual recovery") from exc
        except Exception as exc:
            try:
                _set_claim_state(key, claim_id, "AMBIGUOUS", type(exc).__name__)
            except ClientError:
                pass
            raise ApiError(503, "Queue submission outcome is ambiguous; check this operation's status before manual recovery") from exc
        try:
            _set_claim_state(key, claim_id, "SENT", "")
        except ClientError:
            # Keep SUBMITTING as a durable non-retryable claim. A status read or
            # same-key retry after five minutes quarantines it as AMBIGUOUS.
            pass
        state = records.get_item(Key={"idempotency_key": key}, ConsistentRead=True).get("Item", {}).get("status", "SENT")
        return response(202, {"operation_id": key, "ticket_id": ticket_id, "status": state},
                        {"Location": f"/{os.environ.get('API_STAGE_NAME', 'v1')}/requests/{key}"})
    except Exception as exc:
        return handle_error(exc)
