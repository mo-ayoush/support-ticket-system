# ADR-001: Selection of Serverless Architecture

## Status

Accepted

## Date

2026-11-06

## Context

The Support Ticket Management System requires a REST API that supports creating, listing, retrieving, updating, and deleting support tickets.

The system must provide persistent storage, request validation, authentication and authorization, operational visibility, and reliable handling of write operations and notifications.

Two AWS architecture options were evaluated:

- **Architecture A:** Amazon API Gateway, AWS Lambda, and Amazon DynamoDB.
- **Architecture B:** Application Load Balancer (ALB), Amazon ECS Fargate, Amazon ECR, and Amazon DynamoDB.

The project has a relatively small expected workload and limited educational project resources and budget. Therefore, operational simplicity, cost awareness, scalability, and maintainability were important decision factors.

## Decision Drivers

The architecture was evaluated against the following criteria:

- Functional suitability for the required ticket CRUD operations.
- Scalability for variable request volumes.
- Availability and operational complexity.
- Security and access control.
- Cost suitability for a small project.
- Maintainability and reproducibility.
- Extensibility for asynchronous processing and notifications.

## Decision

**Architecture A – Serverless – was selected.**

The initial architecture decision established API Gateway, Lambda, and DynamoDB as the main application components.

Terraform was selected to define and manage the AWS infrastructure.

The implementation was subsequently refined to include additional services for authentication, asynchronous processing, reliability, notifications, monitoring, and cost visibility. These refinements extend the original serverless decision without changing the selected architecture.

## Selected Architecture

The implemented architecture consists of the following components:

| Component | Responsibility |
|---|---|
| Amazon API Gateway REST API | Regional HTTP API entry point, routing, request validation, and Lambda integration |
| Amazon Cognito | User authentication through a User Pool and API authorization scope |
| Idempotency Lambda | Handles incoming write requests and submits accepted operations to SQS FIFO |
| Write Lambda | Processes queued write operations and performs transactional DynamoDB operations |
| Read Lambda | Handles ticket queries, operation status, audit history, and administrative DLQ inspection |
| Amazon SQS FIFO | Queues write operations for asynchronous processing |
| SQS Dead-Letter Queue | Holds messages that exceed the configured receive attempts |
| Amazon DynamoDB | Stores tickets, idempotency records, audit records, and notification outbox records |
| Notification Worker Lambda | Processes pending notification records and publishes notifications through SNS |
| Amazon EventBridge | Triggers the Notification Worker periodically |
| Amazon SNS | Delivers operational and notification alerts |
| Amazon CloudWatch | Provides logs, metrics, alarms, and an operational dashboard |
| AWS Budgets | Provides monthly cost monitoring and budget notifications |
| AWS IAM | Controls permissions for Lambda functions and AWS service integrations |
| Terraform | Defines and manages the infrastructure as code |

### Lambda Separation

The application uses four Python 3.12 Lambda functions:

1. **Idempotency Lambda:** Receives create, update, and delete requests, handles idempotency records, and sends accepted write operations to SQS FIFO.
2. **Write Lambda:** Consumes queued messages and performs the required ticket, audit, and operation updates using DynamoDB transactions.
3. **Read Lambda:** Handles read operations and selected administrative queries.
4. **Notification Worker Lambda:** Processes notification outbox records and publishes notifications through SNS.

Separating these responsibilities provides clearer boundaries between request acceptance, write processing, read operations, and notification delivery.

### Request and Data Flows

#### Read Operations

1. The client sends an authenticated HTTP request to API Gateway.
2. Cognito validates the supplied access token and API authorization scope.
3. API Gateway invokes the Read Lambda through Lambda proxy integration.
4. The Read Lambda performs the required DynamoDB query or retrieval.
5. The Lambda returns the response through API Gateway to the client.

#### Write Operations

1. The client submits a create, update, or delete request.
2. API Gateway authenticates and authorizes the API request through Cognito.
3. API Gateway invokes the Idempotency Lambda.
4. The Idempotency Lambda validates the request and handles the idempotency key.
5. The accepted operation is submitted to the SQS FIFO queue.
6. The API returns an accepted response while the operation is processed asynchronously.
7. The Write Lambda consumes the queued message.
8. The Write Lambda performs transactional DynamoDB operations, including the relevant ticket, audit, and operation records.
9. The client can retrieve operation status through the operation-status endpoint.

#### Notification Processing

1. Successful write processing creates a notification outbox record in DynamoDB.
2. EventBridge periodically triggers the Notification Worker.
3. The worker queries eligible notification records and attempts to publish notifications through SNS.
4. Notification records are updated according to the processing outcome.
5. Ambiguous notification outcomes are monitored through a custom CloudWatch metric and alarm.

This design separates the ticket write operation from notification delivery.

## Reliability and Failure Handling

The architecture includes several mechanisms to improve operational reliability:

- SQS FIFO provides an ordered message-processing mechanism for queued writes.
- The Write Lambda uses a batch size of one and reports failed messages through `ReportBatchItemFailures`.
- The SQS Dead-Letter Queue provides a place for messages that exceed the configured receive attempts.
- DynamoDB transactions help maintain consistency across related ticket, audit, idempotency, and notification records.
- The idempotency strategy helps prevent duplicate processing of repeated client write requests.
- The notification outbox separates notification intent from external SNS delivery.
- CloudWatch alarms provide visibility into selected application and infrastructure failures.

These mechanisms reduce the impact of individual processing failures, but they do not eliminate all possible failures or guarantee end-to-end delivery in every scenario.

## Security Considerations

Security is implemented through multiple layers:

- Cognito User Pool authentication protects the API entry point.
- API Gateway requires the configured Cognito authorization scope.
- Lambda functions perform application-level authorization checks, including ownership and administrative group checks where applicable.
- Each Lambda function has a dedicated IAM role and permissions scoped to the AWS resources and operations it requires.
- API access logs avoid recording request bodies and authorization tokens.
- DynamoDB tables use server-side encryption.
- Terraform state and sensitive variable files are excluded from the public Git repository.

Authentication at the API Gateway level does not replace application-level authorization. The application must still verify whether the authenticated user is allowed to access a particular ticket or administrative operation.

## Monitoring and Cost Awareness

The implementation uses Amazon CloudWatch for operational visibility.

The monitoring configuration includes:

- Lambda error alarms for the Idempotency, Write, and Read functions.
- A separate Notification Worker error alarm.
- An alarm for visible messages in the SQS Dead-Letter Queue.
- A custom alarm for ambiguous notification outcomes.
- An API Gateway 5XX error alarm.
- An operational dashboard showing Lambda activity, queue metrics, and Tickets table capacity metrics.
- Seven-day retention for the configured Lambda and API access log groups.

AWS Budgets provides a monthly cost budget. The default configured limit is USD 10, with actual-cost notifications at USD 5, USD 8, and USD 10.

These budget notifications provide cost visibility; they do not automatically stop or delete AWS resources.

## Alternatives Considered

### Architecture A – Serverless

API Gateway receives HTTP requests and forwards them to Lambda. Lambda executes the Python business logic and communicates with DynamoDB.

**Advantages:**

- No application container or continuously running application server is required.
- Lambda scales according to incoming event volume.
- Pay-per-use pricing is suitable for variable workloads.
- Fewer infrastructure components are required for the initial application.
- Direct integration between API Gateway and Lambda.
- Suitable for the project's CRUD requirements.
- Supports asynchronous processing through managed AWS services.

**Disadvantages:**

- Lambda execution duration, memory, and deployment package limits must be considered.
- Cold starts may affect initial request latency.
- Event-driven processing introduces additional design complexity.
- Troubleshooting requires appropriate logging, metrics, and correlation of asynchronous operations.
- Multiple managed services introduce service-specific configuration and permissions.

### Architecture B – Container-Based

ALB forwards requests to a Python API running in an ECS Fargate container. ECR stores the Docker image.

**Advantages:**

- More control over the application runtime.
- Container portability.
- Support for long-running processes.
- Health checks and load balancing through ALB.
- Suitable for applications requiring a continuously running service.

**Disadvantages:**

- More infrastructure components and configuration.
- Docker image and container deployment management.
- ECS networking, task configuration, and service management introduce additional operational work.
- Potential ongoing Fargate and ALB costs.
- Greater infrastructure complexity for the expected initial project workload.

One ECS task with one container would be sufficient for the initial project. Multiple tasks are optional and could be introduced later for scaling and improved task-level availability.

## Consequences

### Positive Consequences

- Reduced infrastructure and operational complexity compared with the container-based alternative.
- No need to manage Docker containers or an ECS service.
- Suitable for a small REST API with variable request volume.
- Cost-conscious architecture using managed AWS services.
- Clear separation between API routing, read operations, write processing, and notifications.
- Managed services support asynchronous processing and operational monitoring.
- Infrastructure can be reproduced and reviewed through Terraform.

### Negative Consequences

- Dependence on AWS serverless services.
- Lambda execution limits and possible cold starts.
- Application logic must follow Lambda's event-driven execution model.
- Asynchronous writes require operation-status handling and additional failure-management logic.
- More AWS services mean more IAM policies, configuration, and monitoring requirements.
- Actual costs depend on usage and service pricing; pay-per-use does not mean zero cost.

## Implementation Evidence

The selected serverless architecture was implemented using Terraform and deployed to AWS.

The implementation includes:

- A Regional API Gateway REST API with a `v1` stage.
- Cognito User Pool authorization.
- Four Python 3.12 Lambda functions.
- Three application Lambda functions defined through a shared Terraform `for_each` configuration, plus a separate Notification Worker.
- SQS FIFO write queue and FIFO Dead-Letter Queue.
- Four DynamoDB tables: Tickets, Idempotency, Audit, and Notifications.
- An EventBridge schedule that triggers the Notification Worker every minute.
- An SNS topic for notifications and operational alarms.
- CloudWatch log groups, alarms, and an operational dashboard.
- An AWS monthly cost budget.

Terraform initialization, validation, planning, and application were completed during deployment.

Manual end-to-end testing confirmed successful ticket creation, listing/retrieval, update, and deletion through the frontend connected to the deployed AWS API. Deletion uses soft-delete behavior.

Automated tests using AWS service mocks also passed for the selected application test suites. These tests are distinct from live AWS integration tests.

Final infrastructure destruction and verification that project-created AWS resources have been removed remain pending after the project demonstration.

## Rationale

Serverless architecture provides the best balance between project requirements, scalability, cost awareness, and operational simplicity.

The initial selection of API Gateway, Lambda, and DynamoDB provided a suitable foundation for the required REST API. The later addition of Cognito, SQS FIFO, a Dead-Letter Queue, an outbox-based notification worker, SNS, CloudWatch, and AWS Budgets addressed implementation requirements for authentication, asynchronous processing, failure handling, notifications, monitoring, and cost visibility.

Architecture B remains a valid alternative if future requirements need greater runtime control, container portability, or long-running processes.
