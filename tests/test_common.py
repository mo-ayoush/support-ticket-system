import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "lambdas" / "shared"))
from common import (
    ApiError,
    apply_soft_delete,
    can_access_ticket,
    identity,
    new_ticket_record,
    notification_required,
    pagination_key,
    pagination_token,
    parse_body,
    request_fingerprint,
    should_process_operation,
    update_ticket_record,
    validate_idempotency_key,
    validate_write,
)


class CommonTests(unittest.TestCase):
    def test_create_validation_accepts_supported_values(self):
        validate_write({"title": "Issue", "description": "Details", "priority": "HIGH"}, "POST")

    def test_create_validation_rejects_invalid_body(self):
        for body in (
            {"title": "", "description": "Details", "priority": "HIGH"},
            {"title": "Issue", "description": "Details", "priority": "URGENT"},
        ):
            with self.assertRaises(ApiError):
                validate_write(body, "POST")

    def test_update_requires_version_and_status(self):
        with self.assertRaises(ApiError):
            validate_write({"title": "x", "description": "y", "priority": "LOW", "status": "OPEN"}, "PUT")

    def test_pagination_round_trip(self):
        key = {"ticket_id": "abc", "created_by": "user", "created_sort": "now#abc"}
        self.assertEqual(pagination_key(pagination_token(key)), key)

    def test_idempotency_key_format(self):
        self.assertTrue(validate_idempotency_key("retry-key-123"))
        self.assertFalse(validate_idempotency_key("short"))
        self.assertFalse(validate_idempotency_key("bad key value"))

    def test_post_retry_fingerprint_ignores_generated_ticket_id(self):
        body = {"title": "Issue", "description": "Details", "priority": "HIGH"}
        self.assertEqual(
            request_fingerprint("user", "POST", "first-id", body),
            request_fingerprint("user", "POST", "retry-id", body),
        )
        self.assertNotEqual(
            request_fingerprint("user", "PUT", "ticket-1", body),
            request_fingerprint("user", "PUT", "ticket-2", body),
        )

    def test_authorization_is_owner_or_admin(self):
        ticket = {"created_by": "user-a"}
        self.assertTrue(can_access_ticket({"sub": "user-a", "groups": ["SupportUsers"]}, ticket))
        self.assertFalse(can_access_ticket({"sub": "user-b", "groups": ["SupportUsers"]}, ticket))
        self.assertTrue(can_access_ticket({"sub": "admin", "groups": ["Admins"]}, ticket))

    def test_identity_requires_an_authorized_group(self):
        event = {"requestContext": {"authorizer": {"claims": {"sub": "a", "cognito:groups": "Admins"}}}}
        self.assertEqual(identity(event)["groups"], ["Admins"])
        event["requestContext"]["authorizer"]["claims"]["cognito:groups"] = "Other"
        with self.assertRaises(ApiError) as err:
            identity(event)
        self.assertEqual(err.exception.status, 403)

    def test_invalid_base64_body_is_a_client_error(self):
        with self.assertRaises(ApiError) as err:
            parse_body({"body": "%%%", "isBase64Encoded": True})
        self.assertEqual(err.exception.status, 400)

    def test_critical_notification_transition_rules(self):
        self.assertTrue(notification_required("POST", None, "CRITICAL"))
        self.assertTrue(notification_required("PUT", "HIGH", "CRITICAL"))
        self.assertFalse(notification_required("PUT", "CRITICAL", "CRITICAL"))
        self.assertFalse(notification_required("DELETE", "CRITICAL", "CRITICAL"))

    def test_soft_delete_and_version_conflict(self):
        updated = apply_soft_delete({"version": 2, "status": "OPEN"}, 2, "2026-01-01T00:00:00Z")
        self.assertEqual(updated["status"], "DELETED")
        self.assertEqual(updated["version"], 3)
        with self.assertRaises(ApiError) as err:
            apply_soft_delete({"version": 3}, 2, "now")
        self.assertEqual(err.exception.status, 409)

    def test_ticket_creation_defaults_and_fields(self):
        ticket = new_ticket_record(
            "ticket-1", {"title": " Issue ", "description": " Details ", "priority": "HIGH"},
            "user-1", "2026-01-01T00:00:00Z",
        )
        self.assertEqual(ticket["created_by"], "user-1")
        self.assertEqual(ticket["status"], "OPEN")
        self.assertEqual(ticket["version"], 1)
        self.assertEqual(ticket["created_sort"], "2026-01-01T00:00:00Z#ticket-1")

    def test_ticket_update_and_ownership(self):
        ticket = {"created_by": "user-1", "version": 1, "title": "old", "description": "old",
                  "priority": "LOW", "status": "OPEN"}
        body = {"version": 1, "title": "new", "description": "details", "priority": "HIGH", "status": "IN_PROGRESS"}
        updated, action = update_ticket_record(ticket, body, {"sub": "user-1", "groups": []}, "now", "PUT")
        self.assertEqual(action, "UPDATE")
        self.assertEqual(updated["version"], 2)
        self.assertEqual(updated["title"], "new")
        with self.assertRaises(ApiError) as err:
            update_ticket_record(ticket, body, {"sub": "user-2", "groups": []}, "now", "PUT")
        self.assertEqual(err.exception.status, 403)

    def test_duplicate_message_completion_check(self):
        self.assertTrue(should_process_operation("SENT"))
        self.assertFalse(should_process_operation("COMPLETED"))
