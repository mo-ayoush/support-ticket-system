# TechAssist Ticket Management System

Serverless support-ticket system for TechAssist GmbH, built with a React, TypeScript, and Vite browser application plus AWS, Python 3.12, and Terraform in `eu-central-1` (Frankfurt). Capacity planning assumes 5–50 users and around 10 requests per user per day; this is an estimate, not an AWS quota or performance guarantee.

## Architecture

API Gateway REST API uses a Cognito User Pool authorizer and Lambda proxy integrations. Reads go directly to the Read Lambda and DynamoDB. Writes go through the Idempotency Lambda, DynamoDB idempotency records, an SQS FIFO queue, and the Write Lambda. The writer transactionally updates tickets, audit entries, notification intent, and request state. A scheduled outbox worker sends critical-ticket email through SNS. CloudWatch stores logs, metrics, alarms, and the operations dashboard. AWS Budgets sends monthly cost alerts.

```text
Client -> API Gateway + Cognito -> Read Lambda -> DynamoDB (read)
Client -> API Gateway + Cognito -> Idempotency Lambda -> IdempotencyRecords -> SQS FIFO
                                                              SQS FIFO -> Write Lambda -> DynamoDB transaction
Notification outbox -> scheduled worker -> SNS critical email
CloudWatch alarms and AWS Budget notifications -> SNS email subscription
React + TypeScript + Vite -> Cognito managed login (authorization code + PKCE)
React API client -> API Gateway (Cognito access token; configured CORS origins)
```

## Authentication and authorization

Cognito groups are `SupportUsers` and `Admins`. API methods use a Cognito User Pool authorizer and require the API-specific `support-ticket-api/tickets` OAuth scope on a valid **access token** sent as the raw value of `Authorization`. The browser uses authorization code with PKCE and requests that scope. API Gateway validates the token and scope; Lambdas still check `sub`, groups, and ticket ownership from the verified authorizer context. [AWS documentation](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-enable-cognito-user-pool.html).

Support users can create, read, update, and delete only their own tickets. Admins can access all tickets, including deleted ones. Admin-only routes expose audit history and DLQ message inspection. The request body cannot set `created_by`; the trusted identity and groups are forwarded into SQS and checked again by the Write Lambda.

## Tickets and business rules

Ticket attributes include `ticket_id`, `title`, `description`, `priority`, `status`, `created_by`, `created_at`, `updated_at`, `version`, `admin_partition`, and `created_sort`. The creator is the authenticated Cognito `sub`. Ticket IDs are UUIDs. Sort keys use `created_at#ticket_id`; `admin_partition` is `ALL_TICKETS`.

Priorities: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. User-settable statuses: `OPEN`, `IN_PROGRESS`, `RESOLVED`. Deletion is soft (`status = DELETED`); support-user list and detail reads hide deleted tickets, while Admin reads include them. Admin lists and support-user lists are newest first. Updates and deletes require the last-read `version`; successful mutations increment it. Conflicts are recorded as `CONFLICT` and never overwrite a newer version.

## API endpoints

All routes require a valid Cognito access token with the configured API-specific OAuth scope.

The browser app uses Cognito managed login with OAuth authorization code flow and PKCE. Amplify stores user-pool tokens in `sessionStorage`; authenticated requests send the Cognito access token required by the API authorizer scope. API Gateway CORS and Cognito callback/logout URLs are configured from Terraform variables; the configured browser origin must match the frontend URL exactly.

| Method | Route | Description |
|---|---|---|
| POST | `/tickets` | Queue a ticket create; returns 202 and stable ticket ID |
| GET | `/tickets` | List own tickets or all tickets as Admin; supports `limit` and `next_token` |
| GET | `/tickets/{ticket_id}` | Retrieve a ticket with ownership enforcement |
| PUT | `/tickets/{ticket_id}` | Queue a full update with `version` |
| DELETE | `/tickets/{ticket_id}` | Queue soft deletion with JSON body `{"version": 1}` |
| GET | `/requests/{operation_id}` | Check the exact operation status; available to its actor, ticket owner, or Admin |
| GET | `/tickets/{ticket_id}/audit` | Admin-only paginated ticket audit history |
| GET | `/admin/dlq` | Admin-only inspection of up to 10 failed SQS messages |

POST body example:

```json
{"title":"Cannot access email","description":"Login is failing","priority":"HIGH"}
```

POST may include `status`; otherwise it defaults to `OPEN`. PUT requires `title`, `description`, `priority`, `status`, and `version`. The client cannot set the owner, ID, timestamps, or version on create. `application/api-design.md` contains full examples and response behavior.

## Idempotency and asynchronous writes

POST, PUT, and DELETE require an `Idempotency-Key` of 8–128 characters from letters, digits, `. _ : -`. Reuse the same key for retries and use a new key for each new operation. A key bound to a different user or operation returns 409. For POST retries, the original generated ticket ID is recovered from the idempotency record.

Every accepted write returns its stable `operation_id`, which is the idempotency key. `GET /requests/{operation_id}` returns only that operation. The actor, ticket owner, or Admin may read it. A conditional `PENDING → SUBMITTING` claim allows only one request to call SQS for a key. A clear SQS 4xx rejection releases the claim to retryable `PENDING`; timeouts, connection failures, and 5xx responses become `AMBIGUOUS`. SDK retries are limited to one attempt. A claim still in `SUBMITTING` after five minutes is conditionally quarantined as `AMBIGUOUS`, never automatically resent. `SENT`, `COMPLETED`, `FAILED`, `CONFLICT`, and `AMBIGUOUS` operations are not automatically enqueued again.

The Idempotency Lambda creates a `PENDING` record, conditionally claims it as `SUBMITTING`, sends the operation to FIFO SQS with `MessageGroupId = ticket_id` and `MessageDeduplicationId = operation_id`, then marks it `SENT`. HTTP 202 means SQS accepted or is currently submitting the request; it does not mean the ticket write completed. Poll `/requests/{operation_id}` for its exact state, including `SUBMITTING`. Records expire after 30 days, longer than main-queue plus DLQ retention; application logic checks expiry because DynamoDB TTL removal is asynchronous. For an ambiguous submission, inspect the operation record, queue/DLQ, ticket, and logs before any manual recovery. Do not retry with a new key or redrive blindly: SQS may already have accepted the message.

The frontend stores each operation ID and idempotency key in its own local-storage record, so concurrent tabs adding different operations do not overwrite a shared index; it also reads and migrates the previous index format. Retry payloads remain in tab-scoped session storage. Its global operation panel resumes polling after navigation or reload, prevents overlapping polls, and keeps all pending operations when trimming completed history. Pending operations poll automatically; ambiguous operations stop polling and offer a manual status refresh. A definite SQS rejection can be retried with the same stored key. Logout clears saved request bodies while retaining nonsensitive operation status history. Browser storage does not provide a cross-tab lock for simultaneous updates to the same operation, so server-side operation status remains authoritative.

## DynamoDB, audit, and notifications

Four on-demand DynamoDB tables store tickets, idempotency records, audit events, and notification outbox records. Tickets use `UserTicketsIndex` (`created_by`, `created_sort`) and `AdminTicketsIndex` (`admin_partition`, `created_sort`). Exact operation status uses a consistent primary-key lookup. Normal ticket lists use Query, not Scan. Tickets have point-in-time recovery enabled; all tables use server-side encryption.

Every successful CREATE, UPDATE, and DELETE writes an audit event in the same transaction as the ticket mutation and idempotency completion. Terminal failure transitions use conditional status checks, and `COMPLETED` cannot be replaced by a later failure or conflict. Admins can query `/tickets/{ticket_id}/audit`. Critical-ticket notification intent is written as a DynamoDB outbox record in the same transaction. A scheduled Lambda dispatches PENDING records and retries only clear SNS 4xx rejections up to three attempts. SDK retries are limited to one attempt; timeouts, connection failures, and 5xx outcomes become `AMBIGUOUS` and are never republished automatically. A crash after claiming but before publishing is indistinguishable from a crash after SNS accepted the email: the system chooses duplicate avoidance, so an email may be lost and the record requires manual evidence review. Definite records that exhaust retries become `FAILED` for operator review.

SNS sends email when a ticket is created as CRITICAL or changes from non-CRITICAL to CRITICAL. Other edits to an already critical ticket, reads, priority changes away from CRITICAL, and deletes do not notify. DynamoDB and SNS cannot provide exactly-once delivery. Ambiguous notifications are held for operator review and must never be blindly republished.

## Queues and failed messages

The main FIFO queue uses batch size 1, a 180-second visibility timeout, four-day retention, SSE-SQS, and a three-receive redrive threshold. Its FIFO DLQ retains messages for 14 days and also uses SSE-SQS. Same-ticket writes remain ordered; different ticket groups can run concurrently (maximum event-source concurrency 10). Repeated failures move to the DLQ. Admins can inspect up to 10 messages at `/admin/dlq`; inspection marks matching non-completed request records `FAILED` but does not delete the SQS messages. Use the AWS console/CLI to redrive or remove messages after review.

## Monitoring and costs

Lambda log groups retain 14 days; API Gateway access logs retain 30 days. Access logs contain request ID, timestamp, method, templated resource path, status, response length, and integration latency; they omit authorization headers, query values, request/response bodies, and identity claims. API Gateway method metrics are enabled with execution data tracing disabled. CloudWatch alarms cover Lambda errors/throttles, API 4XX/5XX/latency, outbox worker errors, and visible DLQ messages. The dashboard displays Lambda activity, queue depth, and DynamoDB capacity. Lambda roles are scoped by table, queue, topic, and log group; the API Gateway logging role omits log-event read actions and retains only the `DescribeLogGroups` metadata permission required by the service. API Gateway’s managed GatewayResponse supports static CORS header mapping, so Terraform requires exactly one frontend origin and uses that value for gateway-generated errors. Multi-origin deployments need a different error-response architecture to preserve per-origin allow-list checks.

The monthly AWS Budget defaults to USD 100 with actual-cost alerts at USD 10, 25, and 50. Budget notifications are alerts only: they do not stop resources or prevent additional charges. Email subscription confirmation is required after deployment.

## Repository structure

```text
application/api-design.md          API behavior and examples
architecture/                      Architecture diagrams
documentation/                     Requirements, decisions, assumptions, status
frontend/                          React + TypeScript + Vite client and tests
lambdas/idempotency/app.py          Authenticated write intake and idempotency
lambdas/write/app.py                FIFO consumer, transactions, notification intent
lambdas/read/app.py                 Ticket, request, audit, and DLQ reads
lambdas/notification_worker/app.py  Scheduled SNS outbox dispatcher and recovery states
lambdas/shared/common.py            Shared parsing, validation, auth, response helpers
terraform/                          AWS infrastructure and example tfvars
scripts/package_lambdas.sh          Creates build/lambdas/*.zip
tests/                              Local unit tests
requirements.txt                    Local Lambda/runtime SDK dependency
requirements-dev.txt                Test and development dependencies
```

## Frontend

`frontend/` contains the React + TypeScript + Vite application. It provides Cognito login/logout, protected routes, a role-aware sidebar, a dashboard, searchable/filterable paginated tickets, create/edit/detail/delete workflows, request-status polling for asynchronous writes, admin ticket visibility, audit history, and DLQ inspection. The dashboard derives totals and priority/status summaries from real API pages (up to 5,000 tickets); it displays that cap when reached. The ticket list paginates through the API cursor and filters/sorts each loaded page using the backend's newest-first order.

The API layer is centralized in `frontend/src/services/api.ts` and uses typed request/response interfaces. Create/update/delete requests generate UUID idempotency keys, reuse the key when retrying the unchanged operation, attach the current Cognito access token, handle 202 and 409 responses, and do not report successful mutation until request status is `COMPLETED`. Edit includes the loaded version and surfaces conflicts. Delete confirms the action and explains soft deletion. Admin navigation is driven by the Cognito group claim, while backend authorization remains authoritative.

Configure `frontend/.env.local` from `frontend/.env.example` using Terraform outputs for API URL, user pool, client, hosted UI domain, and API OAuth scope. Cognito callback/logout URL defaults target `http://localhost:5173/`; Terraform permits HTTP only for localhost/127.0.0.1 and requires HTTPS for all other callback, logout, and CORS URLs. Set matching production URLs before deployment. `cognito_domain_prefix` must be globally unique. No frontend hosting or deployment is configured.

## Setup, test, and infrastructure review

Prerequisites: Python 3.12, pip, Node.js >= 20.19 (or >= 22.12), npm, Terraform >= 1.5, `zip`, and network access to npm and Terraform Registry. AWS credentials are only needed for a later plan against AWS; this project review does not deploy anything.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
./scripts/package_lambdas.sh
cd terraform
terraform init
terraform fmt -check -recursive
terraform validate
cp terraform.tfvars.example terraform.tfvars
# Set monitored email addresses and a globally unique Cognito domain prefix.
terraform plan
cd ../frontend
npm ci
cp .env.example .env.local
# Set the Cognito and API output values in .env.local before using sign-in.
npm test
npm run build
npm run dev
```

Terraform planning needs the Lambda ZIPs because Terraform calculates their hashes. Review the plan and IAM policies before any deployment. No `terraform apply` has been run. To clean up an approved deployment, inspect and then run `terraform destroy` with the same variable values; export any data to retain first.

## Known limits and human review

- No load test, live AWS integration test, or production deployment has been performed. The frontend is implemented, but end-to-end browser testing against a deployed Cognito pool/API has not been performed.
- AMBIGUOUS SNS records require manual review after checking CloudWatch and SNS evidence. The worker never automatically republishes them; manually changing an ambiguous record to retryable could duplicate an email.
- DLQ inspection through the API performs SQS ReceiveMessage with visibility timeout zero; it leaves messages available but increments their receive count. Redrive/removal remains an operator action.
- Request status and audit pagination tokens are base64-encoded cursors, not cryptographic signatures. Handlers validate that cursor partition keys match the authorized user/ticket.
- Admin group membership is managed outside this Terraform configuration. Email subscriptions must be confirmed. Review Cognito token use, IAM permissions, cost estimates, quotas, API behavior, and recovery runbooks before deployment.
