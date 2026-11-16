# Architecture Decision: Serverless Ticket API

## Decision summary

Use API Gateway REST API, Cognito, Lambda, DynamoDB, SQS FIFO with DLQ, SNS, CloudWatch, AWS Budgets, and Terraform in `eu-central-1`. This is an event-driven serverless design; no continuously running application server is required. The required React + TypeScript + Vite frontend uses Cognito hosted login and the API; frontend hosting is outside this Terraform stack.

## Request flows

Reads: Client → API Gateway Cognito authorizer → Read Lambda → DynamoDB Query/GetItem.

Writes: Client → API Gateway Cognito authorizer → Idempotency Lambda → IdempotencyRecords → SQS FIFO → Write Lambda → DynamoDB transactional writes. The writer creates audit entries and notification intents; a scheduled outbox worker publishes eligible critical-ticket notifications to SNS.

## Rationale and trade-offs

The original architecture comparison selected serverless instead of ALB/ECS Fargate because the projected educational workload is small and cost sensitive. The implementation extends the original direct CRUD design with Cognito role checks, FIFO ordering, idempotency, audit history, and notifications. These managed services reduce server operations but increase integration and recovery complexity.

DynamoDB uses `ticket_id` as the ticket partition key. `UserTicketsIndex` and `AdminTicketsIndex` support required list access patterns with Query rather than Scan. Exact request status uses the operation's idempotency key as the primary key. On-demand billing and point-in-time recovery are enabled for tickets. The trade-offs include eventual consistency for GSIs, an Admin index partition key that concentrates writes (acceptable only for the stated small workload), and no relational joins.

## Security

API Gateway validates Cognito access tokens with the API-specific `support-ticket-api/tickets` OAuth scope. Lambdas continue to require a Cognito `sub` and the `SupportUsers` or `Admins` group. Ownership is verified before queue submission, at write processing, and when an exact operation ID is queried. Terraform defines per-function IAM roles and scoped resource access. Email addresses and deployment values are Terraform variables; credentials are not in source.

## Reliability and operations

FIFO ordering is per ticket; different ticket groups process in parallel. Ticket, audit, request-completion, and notification-intent changes are committed with DynamoDB transactions. A scheduled SNS outbox worker uses a conditional claim and one SDK attempt per publish. Clear 4xx rejections can retry; timeouts, 408/5xx responses, and stale claims are quarantined and never automatically republished. This chooses duplicate avoidance over guaranteed delivery: a crash after claim but before publication can lose an email, while a crash after publication can leave its outcome ambiguous. SQS submission uses a conditional `PENDING → SUBMITTING` claim, a one-attempt client, and five-minute stale-claim quarantine. Operation terminal updates are conditional and cannot replace `COMPLETED`. API Gateway emits access logs without credentials, request bodies, query values, or identity claims; method metrics are enabled, and a CloudWatch alarm monitors API Gateway 5XX errors. Integration latency is recorded in access logs but has no dedicated alarm. SQS failures retry and redrive to a DLQ; Admins can inspect DLQ messages while redrive/removal remains an operator action. Idempotency records expire after 30 days, beyond configured queue plus DLQ retention.

API Gateway GatewayResponse header mappings are static or directly mapped from request parameters; they do not support conditional allow-list evaluation in VTL. The configuration therefore uses one static configured frontend origin for `DEFAULT_4XX` and `DEFAULT_5XX`, and Terraform rejects multiple CORS origins. This keeps errors readable from the configured browser origin while responses from another origin fail browser CORS checks. Multi-origin support requires a different error-response architecture.

The browser persists operation records under separate local-storage keys so concurrent tabs creating different operations cannot lose one another through a shared index rewrite. It reads the prior array index format during migration. Retry bodies remain scoped to the originating tab in `sessionStorage`; simultaneous stale updates to the same operation across tabs are not coordinated, so the exact server operation status remains authoritative.

## Alternative

ALB, ECS Fargate, and ECR remain a valid alternative if future requirements need long-running processes, container-level runtime control, or portability. They add networking and ongoing service cost and are not implemented.

## Current status

Infrastructure code and Lambda code are present. Local tests and packaging can run without AWS. Terraform formatting is available locally; provider schema validation and planning require a working Terraform Registry/provider install. No AWS resources have been deployed.
