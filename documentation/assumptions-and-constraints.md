# Assumptions and Constraints

## Assumptions

- Small educational workload: approximately 5–50 users and 10 requests per user per day; these are planning estimates.
- Users and Admins are provisioned and assigned Cognito groups by an operator. Terraform creates the pool and groups but does not provision accounts.
- Clients use Cognito access tokens with the API Gateway REST API's API-specific `support-ticket-api/tickets` OAuth scope.
- The browser uses Cognito managed login with OAuth authorization code + PKCE, and keeps auth tokens in session storage.
- Frontend callback/logout URLs and API CORS origins are set to the exact browser origin used by the deployment.
- Ticket ownership is the authenticated user's `sub`; trusted identity/group claims are forwarded to the asynchronous writer.
- AWS resources are deployed in one Region, `eu-central-1`.
- Client retries reuse a key for the same operation. Idempotency records are retained for 30 days before TTL expiration, exceeding the combined queue/DLQ retention window.

## Constraints

- Use serverless managed AWS components and avoid continuously running compute.
- All AWS resources and operating costs must be reviewed before deployment; budgets are alerts and do not stop resources.
- Local review must not deploy resources. An operator must inspect the Terraform plan and state-management choices.
- Lambda request processing and SQS are asynchronous for write operations; HTTP 202 means accepted by SQS, not committed to the ticket table.
- The browser frontend is local-buildable but is not hosted or deployed by this Terraform configuration.

## Security considerations

- API Gateway validates Cognito tokens. Lambdas require `sub` plus membership in `SupportUsers` or `Admins`.
- Never trust a client-supplied `created_by`; perform ownership checks again in the asynchronous write path.
- Keep IAM scoped to required tables, queues, SNS, API routes, and log groups.
- Do not commit credentials, `.tfvars`, or Terraform state. Avoid logging tokens and ticket bodies.

## Operational limitations

- A PENDING idempotency operation can be retried with the same key only when `last_error` identifies a definite SQS 4xx rejection. A `SUBMITTING` claim that survives five minutes is quarantined as AMBIGUOUS; inspect the operation, SQS queue/DLQ, ticket, and logs before manual recovery. Never create a new key or redrive blindly while the original acceptance is uncertain.
- SNS and SQS SDK clients make one attempt to avoid hidden republishing. SNS 408/5xx, timeouts, connection errors, and stale claims are AMBIGUOUS and require evidence review. A worker crash after claim but before SNS publish may lose an email; a crash after publish may leave a delivered email marked AMBIGUOUS. The design prefers avoiding duplicates, and does not promise exactly-once or guaranteed delivery.
- API Gateway `DEFAULT_4XX` and `DEFAULT_5XX` GatewayResponse CORS uses one static origin because response-parameter mapping cannot conditionally compare the incoming Origin against an allow-list. Terraform requires exactly one `frontend_allowed_origins` entry. Supporting multiple origins requires routing gateway errors through a component that can safely evaluate the allow-list.
- DLQ message inspection increments receive count; message redrive/removal is an operator action.
- Multi-Region disaster recovery and automated incident response are out of scope. Browser end-to-end tests against deployed AWS services are not implemented.

## Cleanup

After an approved deployment, review and run `terraform destroy`, export data that must be retained, verify resources are removed, and check AWS Billing for charges already incurred.
