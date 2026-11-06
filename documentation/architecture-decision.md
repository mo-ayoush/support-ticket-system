# Architecture Decision – AWS Support Ticket Management System

## 1. Decision Summary

**Selected Architecture: Architecture A – Serverless**

The project will use the following AWS services:

- Amazon API Gateway
- AWS Lambda
- Amazon DynamoDB
- AWS IAM
- Amazon CloudWatch
- Terraform for Infrastructure as Code

Architecture A was selected after comparing the serverless and container-based alternatives against the project's functional and non-functional requirements.

## 2. Business and Technical Context

TechAssist GmbH requires a cloud-based Support Ticket Management System to replace manual ticket handling through emails, chats, and spreadsheets.

The system must support:

- Creating support tickets.
- Listing all tickets.
- Retrieving a ticket by its ID.
- Updating existing tickets.
- Deleting tickets.
- Persisting ticket data.
- Returning meaningful errors.
- Logging application activity and errors.
- Secure and reproducible infrastructure deployment.

The expected initial workload is relatively small and is suitable for an educational cloud engineering project with cost constraints.

## 3. Alternatives Considered

### Option A – Serverless Architecture

Components:

- API Gateway as the API entry point.
- Lambda running the Python application logic.
- DynamoDB for persistent ticket storage.
- IAM for access control.
- CloudWatch for logging and monitoring.

Advantages:

- No application container or continuously running application server is required.
- Automatic scaling according to incoming requests.
- Pay-per-use pricing model.
- Fewer infrastructure components.
- Direct integration between API Gateway, Lambda, and DynamoDB.
- Suitable for a small CRUD REST API.

Disadvantages:

- Requires knowledge of event-driven serverless architecture.
- Lambda execution limits and possible cold starts must be considered.
- Debugging requires monitoring multiple AWS services.

### Option B – Container-Based Architecture

Components:

- Application Load Balancer as the application entry point.
- ECS with AWS Fargate to run the Python API container.
- ECR to store the Docker image.
- DynamoDB for persistent ticket storage.
- IAM for access control.
- CloudWatch for logging and monitoring.

Advantages:

- Greater control over the application runtime.
- Docker provides a consistent application environment.
- Suitable for long-running processes.
- ALB supports health checks and traffic distribution.
- Multiple ECS tasks can be introduced for scaling and improved task-level availability.

Disadvantages:

- Requires Docker image creation and management.
- Requires configuration of ECR, ECS, Fargate, ALB, and networking.
- More infrastructure components increase operational complexity.
- Fargate and ALB can introduce ongoing costs.

One ECS task running one container is sufficient for the project's initial CRUD requirements. Multiple containers are optional and may be introduced in the future if higher traffic, redundancy, or additional availability is required.

## 4. Decision Rationale

Architecture A was selected for the following reasons:

1. **Requirement fit:** API Gateway and Lambda provide the required HTTP API functionality and application logic.
2. **Database suitability:** DynamoDB supports the required ticket operations using `ticket_id` as the partition key.
3. **Cost awareness:** Pay-per-use services are appropriate for the expected small and irregular workload.
4. **Operational simplicity:** No Docker image, ECR repository, ECS cluster, Fargate task, or ALB is required.
5. **Scalability:** Lambda can scale with incoming requests within AWS service limits.
6. **Maintainability:** The initial application can be implemented and maintained with a relatively small Python codebase.
7. **Infrastructure reproducibility:** Terraform can define and manage the required AWS resources.

## 5. DynamoDB Selection

DynamoDB was selected instead of Amazon RDS because the initial application uses simple ticket-based access patterns.

Each ticket is represented as an item in a DynamoDB table, with `ticket_id` as the partition key.

The required operations map to:

- Create: `PutItem`
- List: `Scan`
- Retrieve by ID: `GetItem`
- Update: `UpdateItem`
- Delete: `DeleteItem`

The initial scope does not require relational joins or complex SQL queries.

RDS remains a possible alternative if future requirements introduce complex relationships or relational queries.

## 6. API Design Decision

API Gateway is selected as the entry point for Architecture A.

It defines the HTTP routes and methods and forwards requests to Lambda.

The Python Lambda application handles:

- Request validation.
- Business logic.
- DynamoDB operations.
- Error handling.
- HTTP response generation.

This separates API routing from application business logic.

## 7. Security Considerations

The implementation should follow these security principles:

- Use IAM roles and least-privilege permissions.
- Grant Lambda only the DynamoDB permissions it requires.
- Restrict DynamoDB access to the project table.
- Avoid hardcoded AWS credentials and secrets.
- Validate all incoming request data.
- Avoid logging sensitive information.
- Define and implement an appropriate API authentication mechanism before treating the system as production-ready.

The Lambda execution role and API authentication solve different security problems. Protecting Lambda's access to DynamoDB does not automatically authenticate API clients.

## 8. Cost Considerations

Architecture A avoids the need for continuously running ECS Fargate tasks and an Application Load Balancer.

However, API Gateway, Lambda, DynamoDB, and CloudWatch may still generate charges depending on usage, region, configuration, and available credits.

The project will monitor AWS usage and remove resources after testing when they are no longer needed.

## 9. Trade-offs and Limitations

The selected architecture has some limitations:

- Lambda has execution duration and resource limits.
- Cold starts may affect initial response latency.
- DynamoDB is less suitable for complex relational queries.
- The application depends on AWS-managed services and their event-driven integration model.
- API authentication must be implemented explicitly.

These trade-offs are acceptable for the current project scope.

## 10. Future Improvements

Possible future improvements include:

- Adding stronger API authentication and authorization.
- Introducing DynamoDB indexes if new access patterns require them.
- Adding automated functional and infrastructure tests.
- Improving monitoring with CloudWatch metrics and alarms.
- Introducing a container-based deployment if runtime control or portability becomes more important.
- Supporting multiple ECS tasks if Architecture B is adopted and higher availability or scaling is required.

## 11. Final Decision

Architecture A – API Gateway, AWS Lambda, DynamoDB, IAM, and CloudWatch – is the selected architecture for the AWS Support Ticket Management System.

It provides the best balance for the current project between functional requirements, scalability, cost awareness, security, maintainability, and operational simplicity.
