"""Shared API, validation, and identity helpers for TechAssist Lambdas."""
import base64
import binascii
import hashlib
import json
import logging
import os
import re
from contextvars import ContextVar
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
STATUSES = {"OPEN", "IN_PROGRESS", "RESOLVED"}
_cors_origin = ContextVar("cors_origin", default=None)


def set_cors_origin(event):
    origin = next((value for key, value in (event.get("headers") or {}).items() if key.lower() == "origin"), None)
    try:
        allowed = json.loads(os.getenv("FRONTEND_ALLOWED_ORIGINS", "[]"))
    except ValueError:
        allowed = []
    _cors_origin.set(origin if origin in allowed else None)


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def log_event(name, **fields):
    logger.info(json.dumps({"event": name, **fields}, separators=(",", ":"), default=str))


def response(status, body, headers=None):
    cors = {"Access-Control-Allow-Origin": _cors_origin.get(), "Vary": "Origin"} if _cors_origin.get() else {}
    return {"statusCode": status, "headers": {"Content-Type": "application/json", **cors, **(headers or {})},
            "body": json.dumps(body, default=_json_default)}


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def parse_body(event):
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(raw, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            raise ApiError(400, "Request body is not valid base64-encoded JSON")
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        raise ApiError(400, "Request body must be valid JSON")
    if not isinstance(value, dict):
        raise ApiError(400, "Request body must be a JSON object")
    return value


def identity(event):
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
    subject = claims.get("sub")
    if not subject:
        raise ApiError(401, "Authenticated identity is missing")
    groups = claims.get("cognito:groups", [])
    if isinstance(groups, str):
        try:
            parsed_groups = json.loads(groups)
            groups = parsed_groups if isinstance(parsed_groups, list) else [parsed_groups] if isinstance(parsed_groups, str) else []
        except ValueError:
            groups = [group.strip() for group in re.split(r"[,\s]+", groups.replace("[", "").replace("]", "").replace('"', "")) if group.strip()]
    groups = groups if isinstance(groups, list) else []
    if not ({"Admins", "SupportUsers"} & set(groups)):
        raise ApiError(403, "User must belong to SupportUsers or Admins")
    return {"sub": subject, "groups": groups}


def is_admin(user):
    return "Admins" in user.get("groups", [])


def can_access_ticket(user, ticket):
    return is_admin(user) or ticket.get("created_by") == user.get("sub")


def notification_required(method, previous_priority, next_priority):
    return method == "POST" and next_priority == "CRITICAL" or (
        method == "PUT" and previous_priority != "CRITICAL" and next_priority == "CRITICAL"
    )


def apply_soft_delete(ticket, expected_version, timestamp):
    if int(ticket.get("version", 0)) != expected_version:
        raise ApiError(409, "Ticket version conflict; retrieve the latest ticket and retry")
    updated = dict(ticket)
    updated.update(status="DELETED", version=expected_version + 1, updated_at=timestamp)
    return updated


def new_ticket_record(ticket_id, body, actor, timestamp):
    return {"ticket_id": ticket_id, "title": body["title"].strip(), "description": body["description"].strip(),
            "priority": body["priority"], "status": body.get("status", "OPEN"), "created_by": actor,
            "created_at": timestamp, "updated_at": timestamp, "version": 1,
            "admin_partition": "ALL_TICKETS", "created_sort": f"{timestamp}#{ticket_id}"}


def update_ticket_record(ticket, body, user, timestamp, method):
    if not can_access_ticket(user, ticket):
        raise ApiError(403, "Ticket ownership check failed")
    if ticket.get("status") == "DELETED":
        raise ApiError(409, "Deleted tickets cannot be modified")
    expected = body.get("version")
    if not isinstance(expected, int) or int(ticket.get("version", 0)) != expected:
        raise ApiError(409, "Ticket version conflict; retrieve the latest ticket and retry")
    updated = dict(ticket)
    if method == "DELETE":
        return apply_soft_delete(updated, expected, timestamp), "DELETE"
    updated.update(title=body["title"].strip(), description=body["description"].strip(),
                   priority=body["priority"], status=body["status"], version=expected + 1, updated_at=timestamp)
    return updated, "UPDATE"


def should_process_operation(status):
    # FAILED messages may be explicitly redriven by an operator. Conflicts are
    # terminal and must not be replayed automatically.
    return status in {"PENDING", "SUBMITTING", "SENT", "AMBIGUOUS", "FAILED"}


def validate_idempotency_key(key):
    import re
    return isinstance(key, str) and re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", key) is not None


def request_fingerprint(user_id, method, ticket_id, body):
    # POST allocates its ticket ID on first receipt, so it must not affect retry identity.
    stable_ticket_id = None if method == "POST" else ticket_id
    canonical = json.dumps([user_id, method, stable_ticket_id, body], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def validate_write(body, method):
    allowed = {"title", "description", "priority", "status"} if method == "POST" else {
        "title", "description", "priority", "status", "version"
    }
    if set(body) - allowed:
        raise ApiError(400, "Request contains unsupported fields")
    required = {"title", "description", "priority"} if method == "POST" else {"title", "description", "priority", "status", "version"}
    missing = required - set(body)
    if missing:
        raise ApiError(400, f"Missing required fields: {', '.join(sorted(missing))}")
    for key in ("title", "description"):
        if key in body and (not isinstance(body[key], str) or not body[key].strip()):
            raise ApiError(400, f"{key} must be a non-empty string")
        max_length = 200 if key == "title" else 5000
        if key in body and len(body[key]) > max_length:
            raise ApiError(400, f"{key} must be at most {max_length} characters")
    if body.get("priority") not in PRIORITIES:
        raise ApiError(400, "priority must be LOW, MEDIUM, HIGH, or CRITICAL")
    if method == "PUT" and body.get("status") not in STATUSES:
        raise ApiError(400, "status must be OPEN, IN_PROGRESS, or RESOLVED")
    if method == "PUT" and (type(body.get("version")) is not int or body["version"] < 1):
        raise ApiError(400, "version must be a positive integer")
    if method == "POST" and body.get("status", "OPEN") not in STATUSES:
        raise ApiError(400, "status must be OPEN, IN_PROGRESS, or RESOLVED")


def pagination_key(token):
    if not token:
        return None
    if not isinstance(token, str) or len(token) > 4096:
        raise ApiError(400, "Invalid pagination token")
    try:
        value = json.loads(base64.urlsafe_b64decode(token.encode() + b"=" * (-len(token) % 4)))
        if not isinstance(value, dict):
            raise ValueError("pagination token must encode an object")
        return value
    except Exception:
        raise ApiError(400, "Invalid pagination token")


def pagination_token(key):
    if not key:
        return None
    raw = json.dumps(key, separators=(",", ":"), default=_json_default).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def handle_error(exc):
    if isinstance(exc, ApiError):
        return response(exc.status, {"error": exc.message})
    logger.exception("Unhandled API error")
    return response(500, {"error": "Internal server error"})
