import os
import time
import json

import boto3
from boto3.dynamodb.conditions import Attr, Key

from common import ApiError, can_access_ticket, handle_error, identity, is_admin, pagination_key, pagination_token, response, set_cors_origin

dynamodb = boto3.resource("dynamodb")
tickets = dynamodb.Table(os.environ["TICKETS_TABLE"])
requests = dynamodb.Table(os.environ["IDEMPOTENCY_TABLE"])
audits = dynamodb.Table(os.environ["AUDIT_TABLE"])
sqs = boto3.client("sqs")


def handler(event, context):
    set_cors_origin(event)
    try:
        user = identity(event)
        admin = is_admin(user)
        path = event.get("resource") or event.get("path", "")
        path_parameters = event.get("pathParameters") or {}
        ticket_id = path_parameters.get("ticket_id")
        operation_id = path_parameters.get("operation_id")
        if path == "/admin/dlq":
            if not admin:
                raise ApiError(403, "Administrator access is required")
            result = sqs.receive_message(QueueUrl=os.environ["DLQ_QUEUE_URL"], MaxNumberOfMessages=10,
                                         WaitTimeSeconds=0, VisibilityTimeout=0,
                                         AttributeNames=["ApproximateReceiveCount", "MessageGroupId"])
            messages = []
            for message in result.get("Messages", []):
                try:
                    operation = json.loads(message["Body"])
                except ValueError:
                    operation = {"unparseable": True}
                if operation.get("operation_id"):
                    try:
                        requests.update_item(Key={"idempotency_key": operation["operation_id"]},
                            UpdateExpression="SET #s=:failed, last_error=:reason",
                            ConditionExpression="attribute_exists(idempotency_key) AND #s <> :completed",
                            ExpressionAttributeNames={"#s": "status"},
                            ExpressionAttributeValues={":failed": "FAILED", ":completed": "COMPLETED",
                                                       ":reason": "Message reached the SQS dead-letter queue; inspect the operation before redriving"})
                    except Exception as exc:
                        if getattr(exc, "response", {}).get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                            raise
                messages.append({"message_id": message["MessageId"], "receive_count": message.get("Attributes", {}).get("ApproximateReceiveCount"),
                                 "message_group_id": message.get("Attributes", {}).get("MessageGroupId"), "operation": operation})
            return response(200, {"messages": messages})
        if path.endswith("/audit") and ticket_id:
            if not admin:
                raise ApiError(403, "Administrator access is required")
            if not tickets.get_item(Key={"ticket_id": ticket_id}, ConsistentRead=True).get("Item"):
                raise ApiError(404, "Ticket not found")
            params = event.get("queryStringParameters") or {}
            limit = _limit(params.get("limit", "25"))
            kwargs = {"KeyConditionExpression": Key("ticket_id").eq(ticket_id), "Limit": limit,
                      "ScanIndexForward": False}
            start = pagination_key(params.get("next_token"))
            if start:
                if start.get("ticket_id") != ticket_id or "event_sort" not in start:
                    raise ApiError(400, "Pagination token does not match this audit query")
                kwargs["ExclusiveStartKey"] = start
            result = audits.query(**kwargs)
            payload = {"ticket_id": ticket_id, "events": result.get("Items", [])}
            token = pagination_token(result.get("LastEvaluatedKey"))
            if token:
                payload["next_token"] = token
            return response(200, payload)
        if path.startswith("/requests/"):
            if not operation_id:
                raise ApiError(400, "operation_id path parameter is required")
            item = requests.get_item(Key={"idempotency_key": operation_id}, ConsistentRead=True).get("Item")
            if not item or int(item.get("expires_at", 0)) <= int(time.time()):
                raise ApiError(404, "Request not found")
            if not admin and user["sub"] not in {item.get("created_by"), item.get("ticket_owner", item.get("created_by"))}:
                raise ApiError(404, "Request not found")
            if item.get("status") == "SUBMITTING" and int(time.time()) - int(item.get("submission_claimed_at", 0)) >= 300:
                try:
                    requests.update_item(Key={"idempotency_key": operation_id},
                        UpdateExpression="SET #s=:ambiguous, last_error=:reason",
                        ConditionExpression="#s=:submitting AND submission_claim_id=:claim",
                        ExpressionAttributeNames={"#s": "status"},
                        ExpressionAttributeValues={":ambiguous": "AMBIGUOUS", ":submitting": "SUBMITTING",
                                                   ":claim": item.get("submission_claim_id", ""),
                                                   ":reason": "Submission claim expired; acceptance is unknown"})
                except Exception as exc:
                    if getattr(exc, "response", {}).get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                        raise
                item = requests.get_item(Key={"idempotency_key": operation_id}, ConsistentRead=True).get("Item", item)
            keys = {"ticket_id", "created_at", "status", "completed_at", "last_error", "ambiguous_at"}
            payload = {"operation_id": operation_id, **{k: v for k, v in item.items() if k in keys}}
            return response(200, payload)
        if ticket_id:
            item = tickets.get_item(Key={"ticket_id": ticket_id}, ConsistentRead=True).get("Item")
            if not item:
                raise ApiError(404, "Ticket not found")
            if not can_access_ticket(user, item):
                raise ApiError(404, "Ticket not found")
            if not admin and item.get("status") == "DELETED":
                raise ApiError(404, "Ticket not found")
            return response(200, item)
        params = event.get("queryStringParameters") or {}
        limit = _limit(params.get("limit", "25"))
        kwargs = {"IndexName": "AdminTicketsIndex" if admin else "UserTicketsIndex",
                  "KeyConditionExpression": Key("admin_partition" if admin else "created_by").eq("ALL_TICKETS" if admin else user["sub"]),
                  "ScanIndexForward": False, "Limit": limit}
        start = pagination_key(params.get("next_token"))
        if start:
            expected_partition = {"admin_partition": "ALL_TICKETS"} if admin else {"created_by": user["sub"]}
            if any(start.get(key) != value for key, value in expected_partition.items()) or "ticket_id" not in start or "created_sort" not in start:
                raise ApiError(400, "Pagination token does not match this user's ticket query")
            kwargs["ExclusiveStartKey"] = start
        items = []
        result = None
        # Deleted support-user rows are filtered after evaluation by DynamoDB. Continue querying
        # until a visible page is full or DynamoDB has no more rows.
        while len(items) < limit:
            kwargs["Limit"] = max(limit - len(items), 1)
            result = tickets.query(**kwargs)
            page = result.get("Items", [])
            items.extend(page if admin else [item for item in page if item.get("status") != "DELETED"])
            next_key = result.get("LastEvaluatedKey")
            if not next_key:
                break
            kwargs["ExclusiveStartKey"] = next_key
        if len(items) > limit:
            items = items[:limit]
        payload = {"tickets": items}
        token = pagination_token(result.get("LastEvaluatedKey"))
        if token:
            payload["next_token"] = token
        return response(200, payload)
    except Exception as exc:
        return handle_error(exc)


def _limit(value):
    try:
        limit = int(value)
    except (TypeError, ValueError):
        raise ApiError(400, "limit must be an integer between 1 and 100")
    if limit < 1:
        raise ApiError(400, "limit must be an integer between 1 and 100")
    return min(limit, 100)
