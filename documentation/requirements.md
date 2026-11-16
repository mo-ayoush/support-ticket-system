# TechAssist Project Requirements

This implementation baseline supersedes the original unauthenticated, direct CRUD API proposal. Detailed architecture and endpoint behavior are in `README.md` and `application/api-design.md`.

## Functional requirements

- FR-01 Create tickets with validated title, description, priority, and optional initial status.
- FR-02 List tickets newest first: SupportUsers see only their own; Admins see all, including deleted records.
- FR-03 Retrieve a ticket by ID with ownership enforcement; SupportUsers cannot see deleted tickets.
- FR-04 Replace mutable ticket fields, require the last-read version, and increment the version atomically.
- FR-05 Soft-delete tickets and preserve their audit history.
- FR-06 Persist tickets, idempotency state, audit events, and notification records in DynamoDB.
- FR-07 Return useful validation/authentication errors and asynchronously record write outcomes.
- FR-08 Capture Lambda logs and CloudWatch metrics/alarms.
- FR-09 Require Cognito authentication and enforce the `SupportUsers` and `Admins` groups.
- FR-10 Require idempotency keys on writes and process mutations asynchronously through FIFO SQS.
- FR-11 Keep each ticket mutation, audit event, and completion record consistent with DynamoDB transactions.
- FR-12 Send email only on CRITICAL ticket creation or transition into CRITICAL.
- FR-13 Allow Admins to inspect audit history and failed DLQ messages.
- FR-14 Provide a responsive React + TypeScript + Vite client with Cognito login/logout, protected routes, session handling, and role-aware navigation.
- FR-15 Provide dashboard summaries, searchable/filterable paginated tickets, ticket creation/detail/edit/soft-delete workflows, and an Admin interface.
- FR-16 Connect the frontend to the API through a typed centralized client, use OAuth authorization code + PKCE and access tokens, handle asynchronous 202 operation status and 409 version conflicts, and show loading/empty/error/success states.

## Ticket data

Required fields are `ticket_id`, `title`, `description`, `priority`, `status`, `created_by`, `created_at`, `updated_at`, `version`, `admin_partition`, and `created_sort`. `created_by` is the verified Cognito `sub` and cannot be supplied by the client. Priorities are `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`; writable statuses are `OPEN`, `IN_PROGRESS`, `RESOLVED`; `DELETED` is system managed.

## Non-functional requirements

- Cost-conscious, on-demand, managed services for the small educational workload.
- Least-privilege IAM, encrypted storage/queues, Cognito-protected API, no committed credentials.
- Scale without manually managed servers, with FIFO ordering per ticket and parallelism across tickets.
- Meaningful failure handling, idempotent retries, optimistic concurrency, a DLQ, and a documented manual notification-recovery policy.
- 7-day Lambda and API Gateway access log retention, with CloudWatch alarms and dashboard.
- Maintainable Python/Terraform code, repeatable packaging and planning, and local test support.

## Test requirements

Unit tests cover request validation, ticket record creation/update/delete, authorization, version conflicts, idempotency key reuse, duplicate completion behavior, notification transitions, read authorization, audit/DLQ reads, and mocked Lambda handler transactions. Frontend tests cover login/protected-route entry, a data-backed dashboard, accepted asynchronous creation, central API access-token/idempotency headers, and conflict handling. Local backend tests use in-memory AWS SDK doubles; browser end-to-end tests against deployed AWS, live AWS integration tests, and infrastructure lifecycle tests are not implemented and must be added before production use.

## Scope

The system includes a React + TypeScript + Vite frontend integrated with Cognito and the REST API. Notification recovery retries definite SNS rejections through a scheduled outbox worker; ambiguous publishes remain quarantined for operator review. Multi-Region recovery and automated incident response remain out of scope. AWS deployment is intentionally not part of local validation.
