# ADR-004: Selection of Python on AWS Lambda

## Status

Accepted

## Date

2026-11-06

## Context

The Support Ticket Management System requires application code to handle HTTP requests, validate ticket data, perform CRUD operations, communicate with DynamoDB, process asynchronous messages, and return meaningful responses.

The project requires a programming language and compute service that are suitable for a small serverless REST API.

The implementation should also support separation of responsibilities, maintainability, error handling, and integration with other AWS services.

## Decision

Python was selected as the application programming language, and AWS Lambda was selected as the compute service.

Python 3.12 is used for all four Lambda functions.

The Python application handles:

- Processing API Gateway and SQS events.
- Validating request data.
- Implementing ticket business logic.
- Calling DynamoDB operations using the AWS SDK for Python (Boto3).
- Publishing notifications through SNS.
- Handling application and processing errors.
- Returning appropriate HTTP status codes and JSON responses.

## Lambda Function Architecture

The implementation uses four separate Python Lambda functions.

### 1. Idempotency Lambda

The Idempotency Lambda receives create, update, and delete requests from API Gateway.

Its responsibilities include:

- Validating incoming write requests.
- Handling idempotency keys.
- Checking and recording operation state.
- Submitting accepted write operations to SQS FIFO.
- Returning an accepted response to the API client.

This function separates request acceptance from actual ticket persistence.

### 2. Write Lambda

The Write Lambda processes messages from the SQS FIFO queue.

Its responsibilities include:

- Consuming queued write operations.
- Applying create, update, and delete operations.
- Performing transactional DynamoDB operations.
- Recording audit events.
- Updating operation completion records.
- Creating notification outbox records as part of the relevant transaction.

This design moves write processing outside the initial HTTP request lifecycle.

### 3. Read Lambda

The Read Lambda handles read-oriented API operations.

Its responsibilities include:

- Listing tickets for authorized users.
- Retrieving individual tickets.
- Retrieving write operation status.
- Retrieving ticket audit history.
- Handling administrative DLQ inspection requests.

Separating read operations from asynchronous write processing provides a clearer application responsibility boundary.

### 4. Notification Worker Lambda

The Notification Worker processes pending notification outbox records.

Its responsibilities include:

- Finding eligible notification records.
- Claiming records for processing.
- Publishing notifications through SNS.
- Updating notification processing state.
- Handling definite publication failures and ambiguous outcomes.

EventBridge triggers this function periodically using a one-minute schedule.

## Why Four Lambda Functions?

The application separates its execution responsibilities instead of placing all functionality in one large Lambda function.

The separation provides:

- Independent read and write processing.
- A dedicated entry point for idempotent write acceptance.
- Asynchronous processing through SQS FIFO.
- Independent notification processing.
- Separate IAM roles and permissions.
- Different timeout and resource configurations according to workload.

The additional functions introduce more deployment and monitoring configuration, but provide clearer boundaries between the application's responsibilities.

## Runtime and Resource Configuration

All four functions use:

- Runtime: Python 3.12.
- Handler: `app.handler`.
- Memory: 256 MB.

The configured timeouts differ by responsibility:

| Lambda function | Memory | Timeout |
|---|---:|---:|
| Idempotency | 256 MB | 15 seconds |
| Write | 256 MB | 30 seconds |
| Read | 256 MB | 15 seconds |
| Notification Worker | 256 MB | 30 seconds |

The longer timeout for the Write Lambda and Notification Worker provides additional execution time for asynchronous processing and AWS service interactions.

The read and idempotency functions use shorter timeouts because their primary responsibilities are request handling and operation submission.

These are initial project resource settings, not the result of a production performance benchmark.

## Shared Python Modules

The implementation uses shared Python modules to avoid duplicating common application functionality.

The shared code includes functionality for:

- Request and ticket validation.
- Authorization checks.
- Common response formatting.
- Reusable application utilities.

The shared module is located at:

`lambdas/shared/common.py`

This approach improves consistency between Lambda handlers and makes common behavior easier to maintain.

## SQS Integration and Failure Handling

The Write Lambda is triggered through an SQS event source mapping.

The configured event source mapping uses:

- Batch size: 1.
- Maximum concurrency: 10.
- `ReportBatchItemFailures` as the partial batch response mechanism.

A batch size of one keeps message processing isolated at the individual-message level.

The partial batch response mechanism allows the Lambda function to report failed messages without treating every message in a larger batch as failed.

The SQS queue uses a visibility timeout of 180 seconds.

A FIFO Dead-Letter Queue is configured to hold messages that exceed the configured receive attempts.

These settings provide a mechanism for handling failed asynchronous write processing. They do not eliminate the need for application-level error handling and operational monitoring.

## Deployment and Packaging

The Lambda functions are deployed as ZIP packages.

Terraform references a separate ZIP artifact for each function:

- `idempotency.zip`
- `write.zip`
- `read.zip`
- `notification_worker.zip`

The main application functions are configured through a shared Terraform `for_each` resource definition, while the Notification Worker has a separate Lambda resource.

Terraform uses `source_code_hash` with `filebase64sha256` to detect changes in the deployment package and identify when a Lambda function needs to be updated.

This approach keeps the application code packaged separately from the Terraform infrastructure configuration.

## IAM and Security

Each Lambda function has a dedicated IAM execution role and associated permissions policy.

The policies are scoped to the AWS resources and actions required by the corresponding function.

This follows the principle of least privilege:

- Functions receive only the permissions required for their responsibilities.
- DynamoDB permissions are scoped to the relevant tables and indexes.
- Queue permissions are assigned according to the function's SQS role.
- SNS permissions are provided where notification publishing is required.
- The Notification Worker has its own execution role and permissions.

Separate execution roles reduce unnecessary permission sharing between application components.

## Error Handling

The application handles errors at different layers.

- API-facing functions return appropriate HTTP responses for application-level errors.
- The Write Lambda handles failures during asynchronous ticket processing.
- SQS provides retry behavior and a Dead-Letter Queue for messages that cannot be processed successfully.
- The Notification Worker handles notification publication outcomes separately from ticket persistence.
- CloudWatch logs and alarms provide operational visibility into selected failures.

The separation of asynchronous write and notification processing prevents those workflows from being treated as part of a single synchronous HTTP execution.

## Testing Strategy

The application uses automated unit and handler tests.

The selected test suite includes:

- Shared validation and utility tests.
- Lambda handler tests.
- Mocked AWS service interactions.

The verified test command was:

`python -m pytest -q tests/test_common.py tests/test_lambda_handlers.py`

The selected test suite completed with 43 passing tests.

These tests use AWS service mocks and therefore do not replace live AWS integration testing.

Manual end-to-end testing was also performed through the frontend connected to the deployed AWS API. Ticket creation, listing/retrieval, update, and soft deletion were confirmed.

No load-testing result is claimed for this implementation.

## Alternatives Considered

### Option A – Python on AWS Lambda

Advantages:

- Python is suitable for REST API and CRUD application development.
- Readable syntax supports maintainable code.
- Boto3 provides integration with AWS services such as DynamoDB, SQS, and SNS.
- Lambda executes code in response to incoming events.
- No application server needs to be managed.
- Pay-per-use pricing is suitable for irregular workloads.
- Supports independent functions for different application responsibilities.

Disadvantages:

- Lambda has execution duration, memory, and deployment package limits.
- Cold starts may affect initial response latency.
- Application code must follow the Lambda event and response model.
- Local testing should account for the Lambda execution environment.
- Multiple functions require separate deployment and monitoring configuration.

### Option B – Python API in an ECS Fargate Container

The same Python application could run inside a Docker container managed by ECS Fargate.

Advantages:

- More control over the runtime and dependencies.
- Suitable for long-running processes.
- Container environment can be packaged and reused.
- A continuously running application process can handle multiple requests.

Disadvantages:

- Requires Docker image creation and maintenance.
- Requires ECR and ECS configuration.
- Requires additional deployment and infrastructure management.
- Fargate and ALB can introduce ongoing costs.
- Container health, networking, and task configuration require additional operational work.

## Consequences

### Positive Consequences

- A straightforward Python implementation.
- Direct AWS service integration through Boto3.
- No need to manage a continuously running application server.
- Clear separation between read, write, idempotency, and notification responsibilities.
- Independent IAM permissions for each function.
- Asynchronous write processing through SQS FIFO.
- Reusable common application code.
- Suitable for the project's serverless architecture.

### Negative Consequences

- The application must be compatible with Lambda's execution model.
- Runtime and resource limits must be considered.
- Cold starts and AWS service integration errors must be handled and tested.
- Multiple functions increase deployment and monitoring configuration.
- Asynchronous workflows require operation tracking and failure handling.
- ZIP packaging and deployment artifacts must be maintained for each function.

## Rationale

Python on AWS Lambda provides a suitable implementation approach for the project's REST API and asynchronous processing requirements.

Python 3.12 and Boto3 provide the required application runtime and AWS service integrations.

The four-function design separates request acceptance, write processing, read operations, and notification delivery. This improves responsibility boundaries and allows different resource settings and IAM permissions for each function.

The ECS Fargate alternative remains valid if future requirements need a continuously running application, greater runtime control, or long-running processes.
