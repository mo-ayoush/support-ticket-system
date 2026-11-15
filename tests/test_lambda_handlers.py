"""Handler tests with small in-memory AWS SDK doubles (no AWS credentials required)."""
import importlib.util
import json
import os
import sys
import types
import unittest
import threading
import time
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "lambdas" / "shared"))
for name, value in {
    "TICKETS_TABLE": "tickets-test", "IDEMPOTENCY_TABLE": "idempotency-test",
    "AUDIT_TABLE": "audit-test", "NOTIFICATION_TABLE": "notifications-test",
    "WRITE_QUEUE_URL": "https://sqs.local/write.fifo", "DLQ_QUEUE_URL": "https://sqs.local/dlq.fifo",
    "ALERT_TOPIC_ARN": "arn:aws:sns:eu-central-1:000000000000:test",
}.items():
    os.environ[name] = value


class FakeClientError(Exception):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.response = {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}}


class FakeTable:
    def __init__(self):
        self.items = {}
        self.query_result = {"Items": []}
        self.lock = threading.RLock()
        self.fail_status_updates = False

    @staticmethod
    def _key(item):
        for name in ("idempotency_key", "notification_id", "ticket_id"):
            if name in item:
                return name, item[name]
        return None, None

    def put_item(self, Item, ConditionExpression=None, ExpressionAttributeValues=None):
        with self.lock:
            _, key = self._key(Item)
            old = self.items.get(key)
            if ConditionExpression and "attribute_not_exists(idempotency_key) OR expires_at <= :now" in ConditionExpression:
                if old and int(old.get("expires_at", 0)) > ExpressionAttributeValues[":now"]:
                    raise FakeClientError("ConditionalCheckFailedException")
            elif ConditionExpression == "attribute_not_exists(idempotency_key)" and old:
                raise FakeClientError("ConditionalCheckFailedException")
            self.items[key] = dict(Item)

    def get_item(self, Key, **kwargs):
        with self.lock:
            _, key = self._key(Key)
            return {"Item": dict(self.items[key])} if key in self.items else {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues, ExpressionAttributeNames=None,
                    ConditionExpression=None, **kwargs):
        with self.lock:
            _, key = self._key(Key)
            item = self.items.setdefault(key, dict(Key))
            values = ExpressionAttributeValues
            condition = ConditionExpression or ""
            if self.fail_status_updates and "#s" in UpdateExpression:
                raise FakeClientError("InternalServerError", status=500)
            if " IN (" in condition:
                allowed = [values[token] for token in values if token in condition]
                if item.get("status") not in allowed:
                    raise FakeClientError("ConditionalCheckFailedException")
            for token in (":pending", ":submitting", ":processing", ":expected"):
                if token in condition and " IN (" not in condition and item.get("status") != values.get(token):
                    raise FakeClientError("ConditionalCheckFailedException")
            for field, token in (("submission_claim_id", ":claim"), ("claimed_at", ":claimed")):
                if f"{field}=:" in condition and item.get(field) != values.get(token):
                    raise FakeClientError("ConditionalCheckFailedException")
            for token in (":status", ":next", ":sent", ":failed", ":conflict", ":ambiguous", ":processing", ":retry", ":submitting", ":pending"):
                if token in values and token in UpdateExpression and ("#s" in UpdateExpression or "#status" in UpdateExpression):
                    item["status"] = values[token]
                    break
            mapping = {":error": "last_error", ":reason": "last_error", ":claimed": "claimed_at", ":now": "updated_at", ":sent_at": "sent_at", ":completed_at": "completed_at", ":claim": "submission_claim_id", ":claimed_epoch": "submission_claimed_at"}
            for token, attr in mapping.items():
                if token in values and attr in UpdateExpression:
                    item[attr] = values[token]
            if ":attempts" in values:
                item["attempts"] = values[":attempts"]
            if ":one" in values:
                item["attempts"] = int(item.get("attempts", 0)) + values[":one"]
            if "REMOVE submission_claim_id" in UpdateExpression:
                item.pop("submission_claim_id", None)
                item.pop("submission_claimed_at", None)
            if "REMOVE last_error" in UpdateExpression:
                item.pop("last_error", None)
            return {"Attributes": item}

    def query(self, **kwargs):
        if kwargs.get("IndexName") == "NotificationStatusIndex":
            condition = kwargs.get("KeyConditionExpression")
            status = condition[2] if isinstance(condition, tuple) else None
            return {"Items": [item for item in self.items.values() if item.get("status") == status]}
        return self.query_result

    def scan(self, **kwargs):
        return {"Items": list(self.items.values())}


class FakeDynamo:
    def __init__(self):
        self.tables = {}
        self.meta = types.SimpleNamespace(client=types.SimpleNamespace(transact_write_items=self.transact_write_items))
        self.transactions = []

    def Table(self, name):
        return self.tables.setdefault(name, FakeTable())

    def transact_write_items(self, **kwargs):
        self.transactions.append(kwargs["TransactItems"])


class FakeSQS:
    def __init__(self):
        self.sent = []
        self.received = {"Messages": []}
        self.error = None
        self.on_send = None
        self.entered = None
        self.release = None

    def send_message(self, **kwargs):
        self.sent.append(kwargs)
        if self.on_send:
            self.on_send()
        if self.entered:
            self.entered.set()
        if self.release:
            self.release.wait(timeout=5)
        if self.error:
            raise self.error
        return {"MessageId": str(len(self.sent))}

    def receive_message(self, **kwargs):
        return self.received


class Condition:
    def __init__(self, field):
        self.field = field

    def eq(self, value):
        return ("eq", self.field, value)

    def gt(self, value):
        return ("gt", self.field, value)


FAKE_DYNAMO = FakeDynamo()
FAKE_SQS = FakeSQS()
class FakeSNS:
    def __init__(self):
        self.published = []
        self.error = None
        self.accept_then_raise = False

    def publish(self, **kwargs):
        self.published.append(kwargs)
        if self.error:
            raise self.error
        return {"MessageId": "test"}

    def put_metric_data(self, **kwargs):
        return {}


FAKE_SNS = FakeSNS()
CLIENT_CONFIGS = {}
SDK_CLIENT_CALLS = []
boto3 = types.ModuleType("boto3")
boto3.resource = lambda service: FAKE_DYNAMO
def fake_boto_client(service, **kwargs):
    CLIENT_CONFIGS[service] = kwargs
    SDK_CLIENT_CALLS.append((service, kwargs))
    if service == "sqs":
        return FAKE_SQS
    if service == "dynamodb":
        return FAKE_DYNAMO
    return FAKE_SNS
boto3.client = fake_boto_client
sys.modules["boto3"] = boto3
boto3_dynamodb = types.ModuleType("boto3.dynamodb")
boto3_conditions = types.ModuleType("boto3.dynamodb.conditions")
boto3_conditions.Key = Condition
boto3_conditions.Attr = Condition
sys.modules["boto3.dynamodb"] = boto3_dynamodb
sys.modules["boto3.dynamodb.conditions"] = boto3_conditions
botocore = types.ModuleType("botocore")
botocore.__path__ = []
botocore_config = types.ModuleType("botocore.config")
botocore_config.Config = lambda **kwargs: kwargs
botocore_exceptions = types.ModuleType("botocore.exceptions")
botocore_exceptions.ClientError = FakeClientError
sys.modules["botocore"] = botocore
sys.modules["botocore.config"] = botocore_config
sys.modules["botocore.exceptions"] = botocore_exceptions


def load_handler(module_name, filename):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "lambdas" / module_name.removesuffix("_lambda") / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


idempotency = load_handler("idempotency_lambda", "app.py")
writer = load_handler("write_lambda", "app.py")
reader = load_handler("read_lambda", "app.py")
notification_worker = load_handler("notification_worker_lambda", "app.py")


def api_event(method, path, body=None, key="retry-key-001", sub="user-1", groups=None):
    segments = path.strip("/").split("/")
    ticket_id = segments[1] if len(segments) > 1 and segments[0] == "tickets" else None
    operation_id = segments[1] if len(segments) > 1 and segments[0] == "requests" else None
    path_parameters = {"ticket_id": ticket_id} if ticket_id else {}
    if operation_id:
        path_parameters["operation_id"] = operation_id
    resource = "/requests/{operation_id}" if operation_id else path
    return {"httpMethod": method, "path": path, "resource": resource, "pathParameters": path_parameters,
            "headers": {"idempotency-key": key}, "body": json.dumps(body or {}),
            "requestContext": {"authorizer": {"claims": {"sub": sub, "cognito:groups": groups or ["SupportUsers"]}}}}


class LambdaHandlerTests(unittest.TestCase):
    def setUp(self):
        for table in FAKE_DYNAMO.tables.values():
            table.items.clear()
            table.query_result = {"Items": []}
        FAKE_DYNAMO.transactions.clear()
        FAKE_SQS.sent.clear()
        FAKE_SQS.received = {"Messages": []}
        FAKE_SQS.error = None
        FAKE_SQS.on_send = None
        FAKE_SQS.entered = None
        FAKE_SQS.release = None
        FAKE_SNS.published.clear()
        FAKE_SNS.error = None
        FAKE_SNS.accept_then_raise = False
        for table in FAKE_DYNAMO.tables.values():
            table.fail_status_updates = False

    def test_idempotency_post_retry_reuses_original_ticket_id(self):
        event = api_event("POST", "/tickets", {"title": "Issue", "description": "Details", "priority": "HIGH"})
        first = json.loads(idempotency.handler(event, None)["body"])
        second = json.loads(idempotency.handler(event, None)["body"])
        self.assertEqual(first["ticket_id"], second["ticket_id"])
        self.assertEqual(first["operation_id"], event["headers"]["idempotency-key"])
        self.assertEqual(len(FAKE_SQS.sent), 1)
        self.assertEqual(second["status"], "SENT")

    def test_idempotency_key_cannot_be_reused_for_different_request(self):
        one = api_event("POST", "/tickets", {"title": "One", "description": "Details", "priority": "HIGH"})
        two = api_event("POST", "/tickets", {"title": "Two", "description": "Details", "priority": "HIGH"})
        idempotency.handler(one, None)
        result = idempotency.handler(two, None)
        self.assertEqual(result["statusCode"], 409)

    def test_non_owner_write_is_rejected_before_enqueue(self):
        FAKE_DYNAMO.Table("tickets-test").items["ticket-1"] = {"ticket_id": "ticket-1", "created_by": "other-user", "status": "OPEN"}
        event = api_event("PUT", "/tickets/ticket-1", {"title": "x", "description": "y", "priority": "HIGH",
                                                          "status": "OPEN", "version": 1})
        result = idempotency.handler(event, None)
        self.assertEqual(result["statusCode"], 404)
        self.assertEqual(FAKE_SQS.sent, [])
        self.assertEqual(FAKE_DYNAMO.Table("idempotency-test").items, {})

    def test_ambiguous_sqs_send_is_quarantined_and_not_resent(self):
        event = api_event("POST", "/tickets", {"title": "Issue", "description": "Details", "priority": "HIGH"})
        FAKE_SQS.error = TimeoutError("send response timed out")
        result = idempotency.handler(event, None)
        self.assertEqual(result["statusCode"], 503)
        stored = FAKE_DYNAMO.Table("idempotency-test").items[event["headers"]["idempotency-key"]]
        self.assertEqual(stored["status"], "AMBIGUOUS")
        FAKE_SQS.error = None
        retry = idempotency.handler(event, None)
        self.assertEqual(json.loads(retry["body"])["status"], "AMBIGUOUS")
        self.assertEqual(len(FAKE_SQS.sent), 1)

    def test_sqs_client_error_5xx_is_ambiguous_not_retryable(self):
        event = api_event("POST", "/tickets", {"title": "Issue", "description": "Details", "priority": "HIGH"})
        FAKE_SQS.error = FakeClientError("InternalError", status=500)
        result = idempotency.handler(event, None)
        self.assertEqual(result["statusCode"], 503)
        self.assertEqual(FAKE_DYNAMO.Table("idempotency-test").items[event["headers"]["idempotency-key"]]["status"], "AMBIGUOUS")

    def test_sqs_http_408_is_ambiguous_and_never_resubmitted(self):
        event = api_event("POST", "/tickets", {"title": "Issue", "description": "Details", "priority": "HIGH"})
        FAKE_SQS.error = FakeClientError("RequestTimeout", status=408)
        self.assertEqual(idempotency.handler(event, None)["statusCode"], 503)
        FAKE_SQS.error = None
        self.assertEqual(json.loads(idempotency.handler(event, None)["body"])["status"], "AMBIGUOUS")
        self.assertEqual(len(FAKE_SQS.sent), 1)

    def test_sqs_transport_timeout_is_ambiguous_and_never_resubmitted(self):
        event = api_event("POST", "/tickets", {"title": "Issue", "description": "Details", "priority": "HIGH"})
        FAKE_SQS.error = TimeoutError("send response timed out")
        self.assertEqual(idempotency.handler(event, None)["statusCode"], 503)
        FAKE_SQS.error = None
        self.assertEqual(json.loads(idempotency.handler(event, None)["body"])["status"], "AMBIGUOUS")
        self.assertEqual(len(FAKE_SQS.sent), 1)

    def test_concurrent_same_key_submission_has_single_conditional_claim(self):
        event = api_event("POST", "/tickets", {"title": "Issue", "description": "Details", "priority": "HIGH"})
        FAKE_SQS.entered = threading.Event()
        FAKE_SQS.release = threading.Event()
        first_result = {}
        thread = threading.Thread(target=lambda: first_result.setdefault("result", idempotency.handler(event, None)))
        thread.start()
        self.assertTrue(FAKE_SQS.entered.wait(timeout=2))
        second = idempotency.handler(event, None)
        self.assertEqual(json.loads(second["body"])["status"], "SUBMITTING")
        self.assertEqual(len(FAKE_SQS.sent), 1)
        FAKE_SQS.release.set()
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(FAKE_DYNAMO.Table("idempotency-test").items[event["headers"]["idempotency-key"]]["status"], "SENT")

    def test_accepted_sqs_message_with_failed_status_writes_stays_non_retryable(self):
        event = api_event("POST", "/tickets", {"title": "Issue", "description": "Details", "priority": "HIGH"})
        table = FAKE_DYNAMO.Table("idempotency-test")
        FAKE_SQS.on_send = lambda: setattr(table, "fail_status_updates", True)
        result = idempotency.handler(event, None)
        key = event["headers"]["idempotency-key"]
        self.assertEqual(result["statusCode"], 202)
        self.assertEqual(table.items[key]["status"], "SUBMITTING")
        FAKE_SQS.on_send = None
        table.fail_status_updates = False
        retry = idempotency.handler(event, None)
        self.assertEqual(json.loads(retry["body"])["status"], "SUBMITTING")
        self.assertEqual(len(FAKE_SQS.sent), 1)
        table.items[key]["submission_claimed_at"] = int(time.time()) - 301
        status = reader.handler(api_event("GET", f"/requests/{key}"), None)
        self.assertEqual(json.loads(status["body"])["status"], "AMBIGUOUS")
        self.assertEqual(len(FAKE_SQS.sent), 1)

    def test_sqs_and_sns_clients_disable_implicit_sdk_retries(self):
        for service in ("sqs", "sns"):
            configured = [kwargs["config"]["retries"]["total_max_attempts"]
                          for called_service, kwargs in SDK_CLIENT_CALLS
                          if called_service == service and "config" in kwargs]
            self.assertTrue(configured)
            self.assertEqual(configured[0], 1)

    def test_definite_sqs_rejection_can_retry_same_key(self):
        event = api_event("POST", "/tickets", {"title": "Issue", "description": "Details", "priority": "HIGH"})
        FAKE_SQS.error = FakeClientError("ThrottlingException")
        self.assertEqual(idempotency.handler(event, None)["statusCode"], 500)
        key = event["headers"]["idempotency-key"]
        self.assertTrue(FAKE_DYNAMO.Table("idempotency-test").items[key]["last_error"].startswith("SQS_REJECTED:"))
        FAKE_SQS.error = None
        retried = json.loads(idempotency.handler(event, None)["body"])
        self.assertEqual(retried["status"], "SENT")
        self.assertEqual(len(FAKE_SQS.sent), 2)

    def test_submission_claim_clears_retry_marker_while_resubmission_is_in_flight(self):
        event = api_event("POST", "/tickets", {"title": "Issue", "description": "Details", "priority": "HIGH"})
        FAKE_SQS.error = FakeClientError("ThrottlingException", status=429)
        idempotency.handler(event, None)
        FAKE_SQS.error = None
        key = event["headers"]["idempotency-key"]
        claimed = {}
        def inspect_claim():
            claimed.update(FAKE_DYNAMO.Table("idempotency-test").items[key])
        FAKE_SQS.on_send = inspect_claim
        idempotency.handler(event, None)
        self.assertEqual(claimed["status"], "SUBMITTING")
        self.assertNotIn("last_error", claimed)

    def test_writer_creation_transacts_ticket_audit_and_completion(self):
        writer.process({"method": "POST", "ticket_id": "ticket-1", "body": {"title": "Issue", "description": "Details", "priority": "HIGH"},
                        "user": {"sub": "user-1", "groups": ["SupportUsers"]}, "operation_id": "retry-key-001"})
        txn = FAKE_DYNAMO.transactions[-1]
        table_names = [next(iter(item.values()))["TableName"] for item in txn]
        self.assertEqual(table_names, ["tickets-test", "audit-test", "idempotency-test"])
        ticket = txn[0]["Put"]["Item"]
        self.assertEqual(ticket["created_by"], {"S": "user-1"})
        self.assertEqual(ticket["status"], {"S": "OPEN"})

    def test_writer_update_checks_version_and_writes_audit(self):
        FAKE_DYNAMO.Table("tickets-test").items["ticket-1"] = {
            "ticket_id": "ticket-1", "created_by": "user-1", "version": 2, "title": "Old", "description": "Issue",
            "priority": "LOW", "status": "OPEN", "created_at": "then", "updated_at": "then",
            "admin_partition": "ALL_TICKETS", "created_sort": "then#ticket-1"}
        writer.process({"method": "PUT", "ticket_id": "ticket-1", "body": {"title": "New", "description": "Fixed", "priority": "HIGH", "status": "IN_PROGRESS", "version": 2},
                        "user": {"sub": "user-1", "groups": ["SupportUsers"]}, "operation_id": "retry-key-002"})
        txn = FAKE_DYNAMO.transactions[-1]
        self.assertEqual(txn[0]["Put"]["ConditionExpression"], "version = :v AND created_by = :owner")
        self.assertEqual(txn[0]["Put"]["Item"]["version"], {"N": "3"})
        self.assertEqual(txn[1]["Put"]["Item"]["action"], {"S": "UPDATE"})

    def test_writer_soft_delete_and_duplicate_message(self):
        FAKE_DYNAMO.Table("tickets-test").items["ticket-1"] = {
            "ticket_id": "ticket-1", "created_by": "user-1", "version": 1, "title": "Issue", "description": "Details",
            "priority": "HIGH", "status": "OPEN", "created_at": "then", "updated_at": "then",
            "admin_partition": "ALL_TICKETS", "created_sort": "then#ticket-1"}
        writer.process({"method": "DELETE", "ticket_id": "ticket-1", "body": {"version": 1},
                        "user": {"sub": "user-1", "groups": ["SupportUsers"]}, "operation_id": "retry-key-003"})
        self.assertEqual(FAKE_DYNAMO.transactions[-1][0]["Put"]["Item"]["status"], {"S": "DELETED"})
        FAKE_DYNAMO.Table("idempotency-test").items["retry-key-004"] = {"idempotency_key": "retry-key-004", "status": "COMPLETED"}
        with mock.patch.object(writer, "process", side_effect=AssertionError("duplicate must not execute")):
            result = writer.handler({"Records": [{"messageId": "duplicate", "body": json.dumps({"operation_id": "retry-key-004"})}]}, None)
        self.assertEqual(result["batchItemFailures"], [])

    def test_critical_create_transacts_pending_notification_outbox_record(self):
        writer.process({"method": "POST", "ticket_id": "ticket-critical", "body": {"title": "Urgent", "description": "Down", "priority": "CRITICAL"},
                        "user": {"sub": "user-1", "groups": ["SupportUsers"]}, "operation_id": "retry-key-005"})
        txn = FAKE_DYNAMO.transactions[-1]
        self.assertEqual(len(txn), 4)
        self.assertEqual(txn[3]["Put"]["Item"]["status"], {"S": "PENDING"})
        self.assertEqual(FAKE_SNS.published, [])

    def test_notification_worker_retries_definite_rejections_three_times(self):
        table = FAKE_DYNAMO.Table("notifications-test")
        notification_id = "ticket-critical#op-definite"
        table.items[notification_id] = {"notification_id": notification_id, "ticket_id": "ticket-critical", "status": "PENDING"}
        FAKE_SNS.error = FakeClientError("ThrottlingException")
        for expected in ("RETRY", "RETRY", "FAILED"):
            result = notification_worker.process_item(dict(table.items[notification_id]))
            self.assertEqual(result, expected)
        self.assertEqual(table.items[notification_id]["attempts"], 3)
        self.assertEqual(len(FAKE_SNS.published), 3)

    def test_notification_worker_marks_success_sent_and_does_not_duplicate(self):
        table = FAKE_DYNAMO.Table("notifications-test")
        notification_id = "ticket-critical#op-success"
        table.items[notification_id] = {"notification_id": notification_id, "ticket_id": "ticket-critical", "status": "PENDING"}
        self.assertEqual(notification_worker.process_item(dict(table.items[notification_id])), "SENT")
        self.assertEqual(notification_worker.process_item(dict(table.items[notification_id])), "SENT")
        self.assertEqual(len(FAKE_SNS.published), 1)

    def test_notification_worker_quarantines_ambiguous_publish_without_republishing(self):
        table = FAKE_DYNAMO.Table("notifications-test")
        notification_id = "ticket-critical#op-ambiguous"
        table.items[notification_id] = {"notification_id": notification_id, "ticket_id": "ticket-critical", "status": "PENDING"}
        FAKE_SNS.error = TimeoutError("response timed out after publish")
        self.assertEqual(notification_worker.process_item(dict(table.items[notification_id])), "AMBIGUOUS")
        FAKE_SNS.error = None
        self.assertEqual(notification_worker.process_item(dict(table.items[notification_id])), "AMBIGUOUS")
        self.assertEqual(len(FAKE_SNS.published), 1)
        self.assertEqual(table.items[notification_id]["status"], "AMBIGUOUS")

    def test_notification_worker_classifies_sns_5xx_as_ambiguous(self):
        table = FAKE_DYNAMO.Table("notifications-test")
        notification_id = "ticket-critical#op-5xx"
        table.items[notification_id] = {"notification_id": notification_id, "ticket_id": "ticket-critical", "status": "PENDING"}
        FAKE_SNS.error = FakeClientError("InternalError", status=500)
        self.assertEqual(notification_worker.process_item(dict(table.items[notification_id])), "AMBIGUOUS")
        FAKE_SNS.error = None
        self.assertEqual(notification_worker.process_item(dict(table.items[notification_id])), "AMBIGUOUS")
        self.assertEqual(len(FAKE_SNS.published), 1)

    def test_notification_worker_classifies_sns_http_408_as_ambiguous(self):
        table = FAKE_DYNAMO.Table("notifications-test")
        notification_id = "ticket-critical#op-408"
        table.items[notification_id] = {"notification_id": notification_id, "ticket_id": "ticket-critical", "status": "PENDING"}
        FAKE_SNS.error = FakeClientError("RequestTimeout", status=408)
        self.assertEqual(notification_worker.process_item(dict(table.items[notification_id])), "AMBIGUOUS")
        FAKE_SNS.error = None
        self.assertEqual(notification_worker.process_item(dict(table.items[notification_id])), "AMBIGUOUS")
        self.assertEqual(len(FAKE_SNS.published), 1)

    def test_notification_worker_retries_representative_sns_4xx_rejection(self):
        table = FAKE_DYNAMO.Table("notifications-test")
        notification_id = "ticket-critical#op-403"
        table.items[notification_id] = {"notification_id": notification_id, "ticket_id": "ticket-critical", "status": "PENDING"}
        FAKE_SNS.error = FakeClientError("AuthorizationError", status=403)
        self.assertEqual(notification_worker.process_item(dict(table.items[notification_id])), "RETRY")
        self.assertEqual(table.items[notification_id]["status"], "RETRY")
        self.assertEqual(table.items[notification_id]["attempts"], 1)
        self.assertEqual(len(FAKE_SNS.published), 1)

    def test_completed_operation_cannot_be_overwritten_by_terminal_failure(self):
        table = FAKE_DYNAMO.Table("idempotency-test")
        table.items["completed-key"] = {"idempotency_key": "completed-key", "status": "COMPLETED"}
        self.assertFalse(writer._set_terminal_status("completed-key", "FAILED", "late failure"))
        self.assertEqual(table.items["completed-key"]["status"], "COMPLETED")
        txn_update = writer._complete("active-key", "ticket", "now")["Update"]
        self.assertIn("#s IN (:pending, :submitting, :sent, :ambiguous, :failed)", txn_update["ConditionExpression"])
        self.assertNotIn("#s <> :done", txn_update["ConditionExpression"])

    def test_concurrent_terminal_transitions_use_a_single_allowed_source_state(self):
        table = FAKE_DYNAMO.Table("idempotency-test")
        table.items["race-key"] = {"idempotency_key": "race-key", "status": "SENT"}
        barrier = threading.Barrier(3)
        outcomes = []
        def transition(status):
            barrier.wait()
            outcomes.append(writer._set_terminal_status("race-key", status, "concurrent result"))
        workers = [threading.Thread(target=transition, args=(state,)) for state in ("FAILED", "CONFLICT")]
        for worker_thread in workers: worker_thread.start()
        barrier.wait()
        for worker_thread in workers: worker_thread.join(timeout=2)
        self.assertEqual(outcomes.count(True), 1)
        self.assertEqual(outcomes.count(False), 1)
        self.assertIn(table.items["race-key"]["status"], {"FAILED", "CONFLICT"})

    def test_notification_worker_marks_stale_claim_ambiguous_without_publish(self):
        table = FAKE_DYNAMO.Table("notifications-test")
        notification_id = "ticket-critical#stale"
        table.items[notification_id] = {"notification_id": notification_id, "ticket_id": "ticket-critical",
                                        "status": "PROCESSING", "claimed_at": "2020-01-01T00:00:00+00:00"}
        notification_worker.process_item(dict(table.items[notification_id]))
        self.assertEqual(table.items[notification_id]["status"], "AMBIGUOUS")
        self.assertEqual(FAKE_SNS.published, [])

    def test_read_hides_other_users_ticket_and_returns_own_list(self):
        FAKE_DYNAMO.Table("tickets-test").items["ticket-1"] = {"ticket_id": "ticket-1", "created_by": "someone-else", "status": "OPEN"}
        event = api_event("GET", "/tickets/ticket-1")
        result = reader.handler(event, None)
        self.assertEqual(result["statusCode"], 404)
        FAKE_DYNAMO.Table("tickets-test").query_result = {"Items": [{"ticket_id": "ticket-2", "created_by": "user-1", "status": "OPEN"}]}
        result = reader.handler(api_event("GET", "/tickets"), None)
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(json.loads(result["body"])["tickets"][0]["ticket_id"], "ticket-2")

    def test_read_owned_ticket_and_missing_ticket(self):
        FAKE_DYNAMO.Table("tickets-test").items["ticket-3"] = {"ticket_id": "ticket-3", "created_by": "user-1", "status": "OPEN"}
        self.assertEqual(reader.handler(api_event("GET", "/tickets/ticket-3"), None)["statusCode"], 200)
        self.assertEqual(reader.handler(api_event("GET", "/tickets/missing"), None)["statusCode"], 404)

    def test_exact_operation_status_is_available_to_ticket_owner(self):
        FAKE_DYNAMO.Table("idempotency-test").items["operation-6"] = {
            "idempotency_key": "operation-6", "ticket_id": "ticket-6", "created_by": "admin-user",
            "ticket_owner": "user-1", "expires_at": 9999999999, "status": "COMPLETED"}
        result = reader.handler(api_event("GET", "/requests/operation-6"), None)
        self.assertEqual(result["statusCode"], 200)
        payload = json.loads(result["body"])
        self.assertEqual(payload["operation_id"], "operation-6")
        self.assertEqual(payload["status"], "COMPLETED")
        self.assertNotIn("created_by", payload)
        self.assertNotIn("ticket_owner", payload)
        self.assertEqual(reader.handler(api_event("GET", "/requests/operation-6", sub="other-user"), None)["statusCode"], 404)
        self.assertEqual(reader.handler(api_event("GET", "/requests/operation-6", sub="admin", groups=["Admins"]), None)["statusCode"], 200)

    def test_admin_audit_and_dlq_inspection(self):
        FAKE_DYNAMO.Table("tickets-test").items["ticket-4"] = {"ticket_id": "ticket-4", "created_by": "user-1", "status": "DELETED"}
        FAKE_DYNAMO.Table("audit-test").query_result = {"Items": [{"ticket_id": "ticket-4", "action": "DELETE"}]}
        audit_result = reader.handler(api_event("GET", "/tickets/ticket-4/audit", groups=["Admins"]), None)
        self.assertEqual(audit_result["statusCode"], 200)
        FAKE_DYNAMO.Table("idempotency-test").items["retry-key-dlq"] = {
            "idempotency_key": "retry-key-dlq", "status": "SENT", "ticket_id": "ticket-5"}
        FAKE_SQS.received = {"Messages": [{"MessageId": "dead-1", "Body": json.dumps({"operation_id": "retry-key-dlq"}),
                                           "Attributes": {"ApproximateReceiveCount": "3"}}]}
        dlq_result = reader.handler(api_event("GET", "/admin/dlq", groups=["Admins"]), None)
        self.assertEqual(dlq_result["statusCode"], 200)
        self.assertEqual(len(json.loads(dlq_result["body"])["messages"]), 1)
        self.assertEqual(FAKE_DYNAMO.Table("idempotency-test").items["retry-key-dlq"]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
