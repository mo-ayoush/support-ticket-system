# TechAssist API Contract

The API is a Cognito-protected API Gateway REST API. Each method uses Lambda proxy integration and requires the API-specific `support-ticket-api/tickets` OAuth scope. Clients send a valid Cognito **access token** as the raw `Authorization` header value. Lambdas independently enforce group and ownership rules after API Gateway validates the token and scope. See the [API Gateway Cognito authorizer documentation](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-enable-cognito-user-pool.html).

All write methods require an `Idempotency-Key` header. Keys contain 8–128 characters from `[A-Za-z0-9._:-]`. PUT requires the version last read. DELETE requires a JSON body containing that version.

## Routes

| Method | Route | Access | Behavior |
|---|---|---|---|
| POST | `/tickets` | Authenticated | Enqueue create; returns 202 with stable `ticket_id` |
| GET | `/tickets` | Support user/Admin | Query own tickets or all tickets, newest first; `limit` and `next_token` |
| GET | `/tickets/{ticket_id}` | Owner/Admin | Read a ticket; support users do not see deleted tickets |
| PUT | `/tickets/{ticket_id}` | Owner/Admin | Enqueue complete mutable-field replacement; expected `version` required |
| DELETE | `/tickets/{ticket_id}` | Owner/Admin | Enqueue soft-delete; JSON `{"version": 1}` required |
| GET | `/requests/{operation_id}` | Operation actor, ticket owner, or Admin | Return one exact unexpired operation state |
| GET | `/tickets/{ticket_id}/audit` | Admin | Read audit events, newest first; paginated |
| GET | `/admin/dlq` | Admin | Inspect up to 10 DLQ operations without deleting them |

POST body:

```json
{"title":"Cannot access email","description":"Login is failing","priority":"HIGH"}
```

Optional POST `status` defaults to `OPEN`. `created_by`, IDs, timestamps, and version are server managed. PUT body:

```json
{"title":"Email restored","description":"Access works again","priority":"MEDIUM","status":"IN_PROGRESS","version":1}
```

Priorities are `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. User-editable statuses are `OPEN`, `IN_PROGRESS`, and `RESOLVED`; `DELETED` is system managed.

## Asynchronous writes and results

The Idempotency Lambda validates the request, checks update/delete ownership before enqueueing, records the trusted Cognito `sub` and group claims, conditionally saves the operation, and claims `PENDING → SUBMITTING` before sending to FIFO SQS. A conditional DynamoDB update ensures only one concurrent request submits a given key. SDK retries are limited to one attempt. A clear SQS 4xx rejection returns the operation to `PENDING` with `SQS_REJECTED:<code>`; 408, 5xx, connection failures, and timeouts become `AMBIGUOUS`. A `SUBMITTING` claim older than five minutes is conditionally changed to `AMBIGUOUS` by a same-key retry or status lookup and is never automatically sent again. The Write Lambda repeats ownership checks. Each request returns the stable operation ID, equal to its idempotency key. Poll `/requests/{operation_id}` for only that operation; statuses include `PENDING`, `SUBMITTING`, `SENT`, `COMPLETED`, `FAILED`, `CONFLICT`, and `AMBIGUOUS`. For ambiguity, inspect the operation, queue/DLQ, ticket, and logs before manual recovery; do not redrive or create a new key until acceptance is understood. Idempotency records expire after 30 days, beyond main-queue plus DLQ retention; TTL cleanup is asynchronous and expiry is checked by application code.

Critical notification intent is committed with ticket and audit changes in the DynamoDB outbox. A scheduled worker claims records conditionally and retries only SNS 4xx responses other than 408, at most three attempts. SNS SDK retries are limited to one attempt. 408/5xx outcomes, connection failures, timeouts, and stale claims are quarantined as `AMBIGUOUS` and never automatically republished. A crash after claim but before publish can lose a notification; a crash after publish but before state persistence can mean it was sent. The design chooses avoiding duplicate email over guaranteeing delivery, so manual evidence review is required.

The same key and same request reuse the original operation. Reusing a key for another operation returns 409. A retried POST recovers its first generated ticket ID. Only a conditionally claimed `PENDING` operation is submitted; other saved states are returned without another queue message. A corrected/new operation requires a new key. Same-ticket operations are ordered by FIFO message group. The writer checks ownership, validates expected version, and transactionally writes the ticket, audit event, and idempotency completion. Completion and terminal error updates use allowed-source-state conditions; `COMPLETED` cannot regress to `FAILED` or `CONFLICT`. Version conflicts become `CONFLICT` only if the operation is still in an active source state.

API Gateway-generated `DEFAULT_4XX` and `DEFAULT_5XX` responses use a static `Access-Control-Allow-Origin` value. Terraform therefore permits exactly one configured frontend origin. GatewayResponse does not provide a safe dynamic allow-list echo for arbitrary request origins through static response-parameter mappings; multi-origin deployments require a different gateway/error-response design. Disallowed browser origins receive a nonmatching allow-origin value and cannot read these responses.

## Persistence and access patterns

Tickets use `ticket_id` as the partition key, with `UserTicketsIndex` (`created_by`, `created_sort`) and `AdminTicketsIndex` (`admin_partition`, `created_sort`). Normal lists use DynamoDB Query; there is no application Scan for ticket lists. Audit events use `ticket_id` and `event_sort`. Exact operation status uses a consistent primary-key lookup on its stable ID.

API Gateway validates POST and PUT JSON body schemas and path parameters. Lambda code performs business validation, ownership enforcement, optimistic concurrency checks, and idempotency validation. Invalid inputs return 400; unauthorized operations return 403 or concealed 404 for another user's ticket; missing tickets return 404; write conflicts are reported asynchronously through request status.
