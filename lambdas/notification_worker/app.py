"""Scheduled SNS outbox dispatcher.

Only PENDING and RETRY records can be claimed for publication. Once a record is
claimed it is never republished automatically: a crash, timeout, or connection
failure may have happened after SNS accepted the message.
"""
import json
import os
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config
from botocore.exceptions import ClientError

table = boto3.resource("dynamodb").Table(os.environ["NOTIFICATION_TABLE"])
# One attempt prevents botocore from silently retrying a publish whose outcome
# may be unknown after a connection or service failure.
SNS_CONFIG = Config(retries={"mode": "standard", "total_max_attempts": 1})
sns = boto3.client("sns", config=SNS_CONFIG)
cloudwatch = boto3.client("cloudwatch")
topic_arn = os.environ["ALERT_TOPIC_ARN"]
MAX_DEFINITE_ATTEMPTS = 3
CLAIM_TIMEOUT = timedelta(minutes=5)


def _definite_rejection(exc):
    """Only a clear non-timeout 4xx response proves SNS rejected the publish."""
    metadata = exc.response.get("ResponseMetadata", {})
    status = metadata.get("HTTPStatusCode")
    return isinstance(status, int) and 400 <= status < 500 and status != 408


def _now():
    return datetime.now(timezone.utc)


def _iso(value):
    return value.isoformat(timespec="seconds")


def _update(notification_id, condition, values, names=None):
    table.update_item(
        Key={"notification_id": notification_id},
        UpdateExpression="SET #status=:status, updated_at=:now" + values.pop("_extra", ""),
        ConditionExpression=condition,
        ExpressionAttributeNames={"#status": "status", **(names or {})},
        ExpressionAttributeValues={":now": _iso(_now()), **values},
    )


def _claim(item, current):
    notification_id = item["notification_id"]
    status = item.get("status")
    if status == "PROCESSING":
        try:
            claimed_at = datetime.fromisoformat(item.get("claimed_at", "1970-01-01T00:00:00+00:00"))
        except ValueError:
            claimed_at = datetime.min.replace(tzinfo=timezone.utc)
        if claimed_at.tzinfo is None:
            claimed_at = claimed_at.replace(tzinfo=timezone.utc)
        if current - claimed_at >= CLAIM_TIMEOUT:
            try:
                condition = "#status=:processing"
                values = {":status": "AMBIGUOUS", ":processing": "PROCESSING"}
                if item.get("claimed_at"):
                    condition += " AND claimed_at=:claimed"
                    values[":claimed"] = item["claimed_at"]
                else:
                    condition += " AND attribute_not_exists(claimed_at)"
                _update(notification_id, condition, values)
                return "AMBIGUOUS"
            except ClientError:
                pass
        return False
    if status not in ("PENDING", "RETRY"):
        return False
    claimed_at = _iso(current)
    try:
        table.update_item(
            Key={"notification_id": notification_id},
            UpdateExpression="SET #status=:processing, claimed_at=:claimed, updated_at=:claimed ADD attempts :one",
            ConditionExpression="#status=:expected",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":processing": "PROCESSING", ":claimed": claimed_at,
                                       ":expected": status, ":one": 1},
        )
    except ClientError:
        return False
    item["attempts"] = int(item.get("attempts", 0)) + 1
    return True


def _publish(item):
    # Keep user supplied ticket content and identity out of notification payloads.
    message = {"event": "critical_ticket", "ticket_id": item["ticket_id"],
               "notification_id": item["notification_id"]}
    return sns.publish(TopicArn=topic_arn, Subject="Critical support ticket",
                       Message=json.dumps(message, separators=(",", ":")))


def process_item(item, current=None):
    current = current or _now()
    claim = _claim(item, current)
    if claim == "AMBIGUOUS":
        return claim
    if not claim:
        return item.get("status", "IGNORED")
    notification_id = item["notification_id"]
    attempts = item["attempts"]
    try:
        _publish(item)
    except ClientError as exc:
        if not _definite_rejection(exc):
            try:
                _update(notification_id, "#status=:processing",
                        {":status": "AMBIGUOUS", ":processing": "PROCESSING",
                         "_extra": ", last_error=:error", ":error": exc.response.get("Error", {}).get("Code", "SNSOutcomeUnknown")})
            except ClientError:
                pass
            return "AMBIGUOUS"
        # Clear 4xx rejections are retryable; timeouts and 5xx outcomes are not.
        state = "RETRY" if attempts < MAX_DEFINITE_ATTEMPTS else "FAILED"
        try:
            _update(notification_id, "#status=:processing",
                    {":status": state, ":processing": "PROCESSING",
                     "_extra": ", attempts=:attempts, last_error=:error",
                     ":attempts": attempts, ":error": exc.response.get("Error", {}).get("Code", "SNSRejected")})
        except ClientError:
            # Leave PROCESSING. The stale-claim path will convert it to AMBIGUOUS.
            return "PROCESSING"
        return state
    except Exception as exc:
        # Endpoint/read timeout and unknown transport failures can occur after SNS
        # accepted the publish. Never republish them automatically.
        try:
            _update(notification_id, "#status=:processing",
                    {":status": "AMBIGUOUS", ":processing": "PROCESSING",
                     "_extra": ", last_error=:error", ":error": type(exc).__name__})
        except ClientError:
            pass
        return "AMBIGUOUS"
    try:
        _update(notification_id, "#status=:processing",
                {":status": "SENT", ":processing": "PROCESSING", "_extra": ", sent_at=:now"})
    except ClientError:
        # SNS may already have accepted the message. A stuck PROCESSING record is
        # conservatively moved to AMBIGUOUS by a later scheduled invocation.
        return "PROCESSING"
    return "SENT"


def handler(event, context):
    current = _now()
    processed = {"SENT": 0, "RETRY": 0, "FAILED": 0, "AMBIGUOUS": 0, "PROCESSING": 0}
    for status in ("PENDING", "RETRY", "PROCESSING"):
        query_args = {"IndexName": "NotificationStatusIndex", "KeyConditionExpression": Key("status").eq(status)}
        while True:
            page = table.query(**query_args)
            for item in page.get("Items", []):
                outcome = process_item(item, current)
                if outcome in processed:
                    processed[outcome] += 1
            if "LastEvaluatedKey" not in page:
                break
            query_args["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    metrics = [{"MetricName": name, "Unit": "Count", "Value": value}
               for name, value in (("Ambiguous", processed["AMBIGUOUS"]), ("Failed", processed["FAILED"])) if value]
    if metrics:
        cloudwatch.put_metric_data(Namespace="TechAssist/Notifications", MetricData=metrics)
    return {"processed": processed}
