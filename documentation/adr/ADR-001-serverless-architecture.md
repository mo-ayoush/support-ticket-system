# ADR-001: Selection of Serverless Architecture

## Status

Accepted

## Date

2026-11-06

## Context

The Support Ticket Management System requires a REST API that supports creating, listing, retrieving, updating, and deleting support tickets.

Two AWS architecture options were evaluated:

- Architecture A: API Gateway, AWS Lambda, and DynamoDB.
- Architecture B: Application Load Balancer, ECS Fargate, ECR, and DynamoDB.

The project has a relatively small expected workload and limited educational project resources and budget.

## Decision

Architecture A – Serverless – was selected.

The application will use:

- Amazon API Gateway as the API entry point.
- AWS Lambda to execute the Python application logic.
- Amazon DynamoDB for persistent ticket storage.
- AWS IAM for permissions and access control.
- Amazon CloudWatch for logging and monitoring.

Terraform will be used to define and manage the AWS infrastructure.

## Alternatives Considered

### Architecture A – Serverless

API Gateway receives HTTP requests and forwards them to Lambda. Lambda executes the Python business logic and communicates with DynamoDB.

Advantages:
- No application container or continuously running application server is required.
- Automatic scaling according to incoming requests.
- Pay-per-use pricing model.
- Fewer infrastructure components.
- Suitable for the project's CRUD requirements.

Disadvantages:
- Lambda execution limits and cold starts must be considered.
- Requires understanding event-driven application design.

### Architecture B – Container-Based

ALB forwards requests to a Python API running in an ECS Fargate container. ECR stores the Docker image.

Advantages:
- More control over the application runtime.
- Container portability.
- Support for long-running processes.
- Health checks and load balancing through ALB.

Disadvantages:
- More infrastructure components and configuration.
- Docker image and container deployment management.
- Potential ongoing Fargate and ALB costs.

One ECS task with one container would be sufficient for the initial project. Multiple tasks are optional and could be introduced later for scaling and improved task-level availability.

## Consequences

### Positive Consequences

- Reduced infrastructure and operational complexity.
- No need to manage Docker containers or an ECS service.
- Suitable for a small REST API.
- Cost-conscious architecture for irregular workloads.
- Direct integration between API Gateway and Lambda.

### Negative Consequences

- Dependence on AWS serverless services.
- Lambda execution limits and possible cold starts.
- Application logic must follow Lambda's event-driven execution model.
- Monitoring and troubleshooting require appropriate CloudWatch logging.

## Rationale

Serverless architecture provides the best balance between project requirements, scalability, cost awareness, and operational simplicity.

Architecture B remains a valid alternative if future requirements need greater runtime control, container portability, or long-running processes.
