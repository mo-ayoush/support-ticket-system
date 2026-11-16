# ADR-003: Selection of Amazon API Gateway

## Status

Accepted

## Date

2026-11-06

## Context

The Support Ticket Management System requires a REST API that allows clients to create, list, retrieve, update, and delete support tickets.

The API must also support authentication, authorization, request validation, asynchronous write processing, and administrative operations.

Two API entry-point approaches were considered:

- Amazon API Gateway in the serverless architecture.
- Application Load Balancer (ALB) in the container-based architecture.

## Decision

Amazon API Gateway was selected as the API entry point for Architecture A.

API Gateway receives HTTP requests, matches configured routes and methods, applies the configured authorization and request validation, and invokes the appropriate AWS Lambda integration.

The implementation uses an **Amazon API Gateway REST API** with:

- Regional endpoint type.
- `v1` deployment stage.
- Lambda proxy integrations.
- Cognito User Pool authorization.
- Terraform-managed routes, methods, integrations, and responses.

## API Endpoints

The implemented API includes the following routes:

| HTTP Method | Endpoint | Purpose |
|---|---|---|
| POST | `/tickets` | Submit a ticket creation request |
| GET | `/tickets` | List tickets |
| GET | `/tickets/{ticket_id}` | Retrieve a ticket by ID |
| PUT | `/tickets/{ticket_id}` | Submit a ticket update request |
| DELETE | `/tickets/{ticket_id}` | Submit a ticket deletion request |
| GET | `/tickets/{ticket_id}/audit` | Retrieve ticket audit history (Admin only) |
| GET | `/requests/{operation_id}` | Retrieve the status of a write operation |
| GET | `/admin/dlq` | Inspect dead-letter queue messages (Admin only) |

The routes are connected to the application as follows:

| Route type | Lambda integration |
|---|---|
| POST `/tickets` | Idempotency Lambda |
| PUT `/tickets/{ticket_id}` | Idempotency Lambda |
| DELETE `/tickets/{ticket_id}` | Idempotency Lambda |
| GET ticket and listing routes | Read Lambda |
| GET audit route | Read Lambda |
| GET operation-status route | Read Lambda |
| GET administrative DLQ route | Read Lambda |

The Idempotency Lambda handles write-request acceptance and queue submission. The Write Lambda processes accepted messages from SQS FIFO asynchronously; it is not directly invoked by API Gateway.

## Authentication and Authorization

The API uses an Amazon Cognito User Pool authorizer.

Clients provide a Cognito access token in the HTTP `Authorization` header.

API Gateway is configured with:

- `COGNITO_USER_POOLS` authorization.
- The API-specific OAuth scope `support-ticket-api/tickets`.
- The `Authorization` header as the authorizer identity source.
- The configured authorization scope on the API methods.

Authentication and authorization are separate responsibilities:

- Cognito validates the user's access token and the required API scope.
- Application Lambda functions perform additional authorization checks, such as ticket ownership and administrative group membership.

This distinction is important because a successfully authenticated user must not automatically be allowed to access every ticket or administrative operation.

## Request Validation

Terraform configures API Gateway request validators for request bodies and parameters.

The API uses request models to validate create and update requests before they reach the application integration.

### Create Request Model

The create request model:

- Requires `title`.
- Requires `description`.
- Requires `priority`.
- Allows optional `status`.
- Restricts `title` to 1–200 characters.
- Restricts `description` to 1–5000 characters.
- Restricts `priority` to `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`.
- Restricts an explicitly supplied status to `OPEN`, `IN_PROGRESS`, or `RESOLVED`.
- Does not allow additional properties.

### Update Request Model

The update request model:

- Requires `title`.
- Requires `description`.
- Requires `priority`.
- Requires `status`.
- Requires `version`.
- Uses the same title, description, priority, and status constraints.
- Requires `version` to be an integer with a minimum value of 1.
- Does not allow additional properties.

Request validation at API Gateway provides an early validation layer. Application-level validation and authorization remain necessary for business rules and access control.

## Integration and Request Processing

The API uses Lambda proxy integration (`AWS_PROXY`).

With proxy integration, API Gateway forwards the request context and request data to the Lambda function. The Lambda function is responsible for generating the application response, including the HTTP status code and response body.

### Read Request Flow

1. The client sends an authenticated GET request.
2. API Gateway checks the Cognito authorizer and configured authorization scope.
3. API Gateway invokes the Read Lambda.
4. The Read Lambda performs the required DynamoDB operation.
5. The Lambda returns its response through API Gateway.

### Write Request Flow

1. The client sends an authenticated POST, PUT, or DELETE request.
2. API Gateway applies the configured authorization and request validation.
3. API Gateway invokes the Idempotency Lambda.
4. The Idempotency Lambda handles the request and submits the accepted operation to SQS FIFO.
5. The API returns an HTTP `202 Accepted` response after queue acceptance.
6. The Write Lambda processes the message asynchronously.
7. The client can use `GET /requests/{operation_id}` to retrieve the operation status.

This asynchronous design avoids requiring the client to wait for the complete write-processing workflow during the initial HTTP request.

## CORS Configuration

The API includes CORS configuration to allow the frontend application to communicate with API Gateway from configured origins.

The allowed origins are controlled through the Terraform variable `frontend_allowed_origins`.

The configuration includes:

- Allowed methods: `GET`, `POST`, `PUT`, `DELETE`, and `OPTIONS`.
- Allowed headers: `Authorization`, `Content-Type`, and `Idempotency-Key`.
- An OPTIONS preflight method using a mock integration.
- `Vary: Origin` response header.
- CORS headers on the configured default API Gateway 4XX and 5XX responses.

The gateway error responses use a configured frontend origin.

CORS controls browser cross-origin access; it is not a replacement for authentication or authorization.

## Error Handling

Error handling is divided between API Gateway and the Lambda application.

### API Gateway Errors

Terraform configures default 4XX and 5XX gateway responses.

These responses use JSON error templates and include configured CORS headers so that browser clients can receive gateway error responses.

### Application Errors

The Lambda application handles application-level validation, authorization, missing-ticket, and processing errors.

With Lambda proxy integration, the application is responsible for returning the appropriate response status and body.

This separation helps distinguish errors rejected at the API entry point from errors generated by application processing.

## Logging and Monitoring

The API uses API Gateway access logging with structured JSON fields.

The access log format includes:

- `requestId`
- `requestTime`
- `httpMethod`
- `resourcePath`
- `status`
- `responseLength`
- `integrationLatency`

API access logs have a configured retention period of seven days.

API Gateway method metrics are enabled.

The implementation also configures:

- API Gateway execution logging level: `OFF`.
- API Gateway data tracing: disabled.
- A CloudWatch alarm for API Gateway 5XX errors.
- An operational CloudWatch dashboard for selected Lambda, SQS, and DynamoDB metrics.

The 5XX alarm monitors the `AWS/ApiGateway` metric `5XXError`.

The implementation does not configure a separate API Gateway latency alarm. Integration latency is available in the access log fields, but this should not be confused with a dedicated latency alarm.

Request bodies and authorization tokens are not included in the configured access log format.

## Alternatives Considered

### Option A – Amazon API Gateway

Advantages:

- Managed API entry point.
- Supports HTTP routes and methods.
- Integrates directly with AWS Lambda.
- Supports Cognito User Pool authorization.
- Supports request validation and Lambda proxy integration.
- Fits the selected serverless architecture.
- Avoids managing an application load balancer for the API.

Disadvantages:

- Requires route and integration configuration.
- API type and features must be selected appropriately.
- API authentication and authorization must be configured explicitly.
- Request pricing must be considered.

### Option B – Application Load Balancer (ALB)

ALB was considered for Architecture B.

It receives incoming traffic and forwards requests to registered targets, such as ECS tasks running the Python API.

Advantages:

- Supports traffic distribution across registered targets.
- Provides health checks for registered targets.
- Integrates with ECS services.
- Suitable for container-based applications.

Disadvantages:

- Does not replace all API management capabilities of API Gateway.
- Requires additional networking and target configuration.
- Can introduce ongoing costs.
- The Python application must implement its own API routing and HTTP method handling.

## Responsibilities in Both Architectures

### Architecture A

- API Gateway handles the API entry point, HTTP routes, methods, authorization integration, and configured request validation.
- Cognito handles access-token authentication and API scope validation.
- Lambda contains the Python business logic and request handling.
- DynamoDB stores ticket and operational records.

### Architecture B

- ALB receives and forwards incoming traffic.
- The Python API running inside the ECS container implements the routes, HTTP methods, validation, and business logic.
- The application must integrate its own authentication and authorization approach.
- DynamoDB stores ticket records.

## Consequences

### Positive Consequences

- Clear separation between API routing and application business logic.
- Direct integration with Lambda.
- Built-in integration with Cognito authorization.
- Request validation can reject invalid requests before application processing.
- CORS and default gateway error responses are managed through Terraform.
- Structured access logs provide request and integration visibility.
- Fewer infrastructure components than the ALB and ECS approach.
- Suitable for the project's required CRUD and administrative endpoints.

### Negative Consequences

- API routes and Lambda integrations must be configured correctly.
- API authentication and application authorization must both be addressed.
- Asynchronous write processing requires operation-status handling.
- API Gateway introduces an additional managed service whose request pricing must be considered.
- Troubleshooting requires correlating API Gateway requests with asynchronous Lambda and SQS processing.

## Implementation Evidence

The API Gateway REST API was deployed through Terraform.

The deployed configuration includes:

- Regional endpoint type and `v1` stage.
- Cognito User Pool authorizer.
- API-specific OAuth authorization scope.
- Eight application routes.
- Lambda proxy integrations.
- Request validators and create/update request models.
- OPTIONS preflight handling.
- Configured CORS headers and default gateway error responses.
- Structured JSON access logs with seven-day retention.
- API Gateway method metrics.
- A CloudWatch API 5XX error alarm.

Manual end-to-end testing confirmed successful ticket creation, listing/retrieval, update, and deletion through the frontend connected to the deployed API.

These results demonstrate the core CRUD request flow. They do not by themselves establish that every administrative route, validation failure, or authorization failure has been independently tested.

## Rationale

API Gateway is the best fit for the selected serverless architecture because it provides the required HTTP API entry point and integrates with Lambda without requiring a continuously running application container.

Its Cognito authorizer, request validation, proxy integration, CORS configuration, and access logging provide useful API capabilities while keeping application business logic inside Lambda.

ALB remains a suitable entry point for the container-based alternative, where the Python API itself handles routing and business logic.
