# ADR-004: Selection of Python on AWS Lambda

## Status

Accepted

## Date

2026-11-06

## Context

The Support Ticket Management System requires application code to handle HTTP requests, validate ticket data, perform CRUD operations, communicate with DynamoDB, and return meaningful responses.

The project requires a programming language and compute service that are suitable for a small serverless REST API.

## Decision

Python was selected as the application programming language, and AWS Lambda was selected as the compute service.

The Python application will run inside Lambda and handle:

- Processing incoming API Gateway events.
- Validating request data.
- Implementing ticket business logic.
- Calling DynamoDB operations using the AWS SDK for Python (Boto3).
- Handling application errors.
- Returning appropriate HTTP status codes and JSON responses.

## Alternatives Considered

### Option A – Python on AWS Lambda

Advantages:

- Python is suitable for REST API and CRUD application development.
- Readable syntax supports maintainable code.
- Boto3 provides integration with AWS services such as DynamoDB.
- Lambda executes code in response to incoming events.
- No application server needs to be managed.
- Pay-per-use pricing is suitable for irregular workloads.

Disadvantages:

- Lambda has execution duration, memory, and deployment package limits.
- Cold starts may affect initial response latency.
- Application code must follow the Lambda event and response model.
- Local testing should account for the Lambda execution environment.

### Option B – Python API in an ECS Fargate Container

The same Python application could run inside a Docker container managed by ECS Fargate.

Advantages:

- More control over the runtime and dependencies.
- Suitable for long-running processes.
- Container environment can be packaged and reused.

Disadvantages:

- Requires Docker image creation and maintenance.
- Requires ECR and ECS configuration.
- Requires additional deployment and infrastructure management.
- Fargate and ALB can introduce ongoing costs.

## Consequences

### Positive Consequences

- A straightforward Python implementation.
- Direct DynamoDB integration through Boto3.
- No need to manage a continuously running application server.
- Suitable for the project's small CRUD API.
- Reduced infrastructure complexity.

### Negative Consequences

- The application must be compatible with Lambda's execution model.
- Runtime and resource limits must be considered.
- Cold starts and AWS service integration errors must be handled and tested.

## Rationale

Python on AWS Lambda provides a simple and suitable implementation approach for the project's REST API.

It supports the required ticket operations and integrates with DynamoDB while avoiding the additional container infrastructure required by the ECS Fargate alternative.
