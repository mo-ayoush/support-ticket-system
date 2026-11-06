# Architecture Comparison – AWS Support Ticket Management System

## 1. Overview

This document compares two possible AWS architectures for the Support Ticket Management System.

- **Architecture A:** Serverless architecture using Amazon API Gateway, AWS Lambda, and Amazon DynamoDB.
- **Architecture B:** Container-based architecture using Application Load Balancer (ALB), Amazon ECS with AWS Fargate, Amazon ECR, and Amazon DynamoDB.

Both architectures can implement the required CRUD operations for support tickets. The comparison considers functional requirements, availability, scalability, security, cost, operational complexity, maintainability, and extensibility.

## 2. Architecture A – Serverless

### AWS Services

- **Amazon API Gateway:** Provides the API entry point and defines HTTP routes and methods.
- **AWS Lambda:** Runs the Python application code and handles business logic.
- **Amazon DynamoDB:** Stores ticket records.
- **AWS IAM:** Controls permissions between AWS services.
- **Amazon CloudWatch:** Collects application logs and monitoring information.

### Request Flow

1. The client sends an HTTP request.
2. API Gateway receives the request and matches the configured route and HTTP method.
3. API Gateway invokes the appropriate Lambda function.
4. The Python code validates the request and executes the business logic.
5. Lambda communicates with DynamoDB to read or modify ticket data.
6. Lambda returns the result, and API Gateway sends the HTTP response to the client.

### Separation of Responsibilities

- API Gateway handles the API entry point, routes, and HTTP methods.
- Lambda contains the Python application logic, including validation, CRUD handling, and error handling.
- DynamoDB provides persistent storage.

### Advantages

- No application servers or containers need to be managed.
- Automatically scales according to incoming requests.
- Pay-per-use pricing can be cost-effective for small or irregular workloads.
- Direct integration between API Gateway and Lambda.
- Less infrastructure configuration than the container-based option.
- Suitable for a small REST API with CRUD operations.

### Disadvantages

- Requires understanding serverless concepts and event-driven execution.
- Lambda cold starts may affect initial response latency.
- Execution duration, memory, and service limits must be considered.
- Debugging across multiple managed services requires appropriate logging and monitoring.
- IAM permissions and service integration must be configured correctly.

## 3. Architecture B – Container-Based

### AWS Services

- **Application Load Balancer (ALB):** Provides the application entry point and distributes incoming traffic to registered targets.
- **Amazon ECS with AWS Fargate:** Runs and manages the Python API container without requiring the user to manage the underlying servers.
- **Amazon ECR:** Stores the Docker container image.
- **Amazon DynamoDB:** Stores ticket records.
- **AWS IAM:** Controls permissions for the application and AWS services.
- **Amazon CloudWatch:** Collects application logs and monitoring information.

### Request Flow

1. The client sends an HTTP request.
2. The ALB receives the request and forwards it to a healthy registered ECS task.
3. The Python API application running inside the container receives the request.
4. The application handles the API route, HTTP method, validation, and business logic.
5. The application communicates with DynamoDB to read or modify ticket data.
6. The application returns the HTTP response through the ALB to the client.

### Separation of Responsibilities

- ALB acts as the entry point and distributes incoming traffic to registered targets.
- The Python API running inside the ECS container handles API routes, HTTP methods, validation, business logic, and error handling.
- DynamoDB provides persistent storage.
- ECR stores the container image used by ECS.

Unlike Architecture A, the API routes and application logic are both implemented inside the Python API application. The ALB forwards incoming traffic to that application.

### Container Requirements

For the initial deployment, **one ECS task running one container is sufficient** for the project's current CRUD requirements and expected small workload.

Running multiple containers is not mandatory.

Multiple ECS tasks could be introduced in the future if the application requires:

- Higher traffic capacity.
- Distribution of requests across multiple running tasks.
- Better task-level availability and redundancy.
- Horizontal scaling.

With only one ECS task, there is no additional task-level redundancy. If that task becomes unavailable, the API may experience temporary downtime while ECS replaces or restarts it.

The ALB can perform health checks even when only one task is running. However, health checks alone do not guarantee high availability.

### Advantages

- Docker provides a consistent and portable application environment.
- Greater control over the runtime environment and application dependencies.
- Suitable for applications requiring long-running processes.
- ALB supports traffic distribution and health checks.
- Multiple ECS tasks can be used for scaling and improved task-level availability.
- Container images can be reused across different compatible environments.

### Disadvantages

- Requires Docker image creation and management.
- Requires configuration of ECR, ECS, Fargate, ALB, and networking.
- More infrastructure components increase operational complexity.
- ALB and Fargate can introduce ongoing costs, even for a small application.
- Container deployment and updates require additional steps.
- A single ECS task does not provide task-level redundancy.

## 4. DynamoDB vs. Amazon RDS

Both services provide persistent data storage, but they use different database models.

### Amazon DynamoDB – NoSQL

- DynamoDB is a managed NoSQL database.
- Data is stored as tables containing items and attributes.
- Each item represents one ticket in this project.
- The `ticket_id` attribute is used as the partition key.
- DynamoDB does not require the project to manage a database server.
- It supports key-based operations suitable for the project's CRUD requirements.

Example ticket item:

```json
{
  "ticket_id": "TICKET-001",
  "title": "Login problem",
  "description": "Unable to log in",
  "priority": "HIGH",
  "status": "OPEN",
  "created_by": "student",
  "created_timestamp": "2026-11-06T10:00:00Z",
  "updated_timestamp": "2026-11-06T10:00:00Z"
}
```

### Amazon RDS – Relational SQL Database

- RDS provides managed relational database engines.
- Data is organized into tables, rows, and columns.
- Applications use SQL to query and manage data.
- Relational databases are suitable for structured relationships and complex queries involving multiple tables.
- Database engine, connection, and capacity configuration must be considered.

### Comparison

| Criterion | DynamoDB | Amazon RDS |
|---|---|---|
| Database model | NoSQL | Relational SQL |
| Data structure | Items and attributes | Tables, rows, columns |
| Queries | Key-based operations and supported queries | SQL queries |
| Relationships | Not designed primarily for relational joins | Supports relationships and joins |
| Server management | No database server management | Managed database engine and configuration |
| Integration | Directly accessible from Lambda using AWS SDK | Requires database connectivity and connection management |
| Suitable use case | Key-based access and scalable application workloads | Relational data and complex SQL queries |

### Why DynamoDB Was Selected

DynamoDB was selected because:

- The project mainly requires creating, retrieving, updating, and deleting tickets.
- Every ticket has a unique `ticket_id`, which can be used as the partition key.
- The initial requirements do not require complex relationships or SQL joins.
- DynamoDB integrates well with AWS Lambda.
- On-demand capacity is an option for a small or unpredictable workload.
- It supports the serverless design and reduces database server management.

### Trade-offs

DynamoDB is not always better than RDS. If the system later requires complex relational queries, multiple related tables, or extensive SQL functionality, Amazon RDS may be a better choice.

For the initial project, DynamoDB provides a simpler fit for the required ticket access patterns.

## 5. CRUD Operations and DynamoDB Mapping

The application exposes the following REST API endpoints:

| Operation | HTTP Method | Endpoint | DynamoDB Operation |
|---|---|---|---|
| Create ticket | POST | `/tickets` | `PutItem` |
| List tickets | GET | `/tickets` | `Scan` |
| Get ticket by ID | GET | `/tickets/{ticket_id}` | `GetItem` |
| Update ticket | PUT | `/tickets/{ticket_id}` | `UpdateItem` |
| Delete ticket | DELETE | `/tickets/{ticket_id}` | `DeleteItem` |

In Architecture A, API Gateway routes the request to Lambda, and Lambda performs the corresponding DynamoDB operation.

In Architecture B, the Python API running inside the ECS container handles the route and performs the corresponding DynamoDB operation.

**Note:** `Scan` reads items across a DynamoDB table and is acceptable as a simple initial approach for a small educational project. For larger datasets, it can become less efficient and more expensive. A suitable `Query` access pattern or secondary index can be considered if future requirements need it.

## 6. HTTP Status Codes

The REST API should return meaningful HTTP status codes.

| Status Code | Meaning | Example |
|---|---|---|
| 200 OK | Request completed successfully | Ticket retrieved or updated |
| 201 Created | Resource created successfully | New ticket created |
| 400 Bad Request | Invalid request data | Invalid priority or missing required field |
| 401 Unauthorized | Authentication is missing or invalid | Request fails an implemented authentication requirement |
| 404 Not Found | Requested resource does not exist | Ticket ID not found |
| 500 Internal Server Error | Unexpected server-side error | Unhandled application or service error |

The presence of a documented `401` response does not mean authentication is automatically implemented. The authentication mechanism must be selected and configured separately.

## 7. Architecture Comparison

The following table compares both architectures against the required evaluation criteria.

| Criterion | Architecture A – Serverless | Architecture B – Containers |
|---|---|---|
| Requirement fit | Well suited for a small CRUD REST API | Also supports the required CRUD API |
| Availability | Uses managed API Gateway and Lambda services; availability depends on service configuration and application design | ALB health checks and multiple ECS tasks can improve task-level availability; one task provides limited redundancy |
| Scalability | Lambda scales with incoming requests within service limits | ECS service can scale the number of running tasks |
| Security | IAM roles and policies control access between services; API authentication must also be considered | IAM roles and policies, container security, network configuration, and API authentication must be considered |
| Cost | Pay-per-use model can be economical for small workloads | Fargate and ALB can introduce ongoing costs, even with one task |
| Operational complexity | Lower infrastructure and deployment complexity | Higher complexity due to Docker, ECR, ECS, Fargate, ALB, and networking |
| Maintainability | Small Python Lambda application with fewer infrastructure components | Containerized Python application, but image building and deployment add operational steps |
| Extensibility | Can integrate additional AWS services and serverless components | Can extend the container application and scale the ECS service |

## 8. Cost Considerations

### Architecture A

- API Gateway costs depend on API type, request volume, and region.
- Lambda costs depend on invocation count, execution duration, and allocated memory.
- DynamoDB costs depend on reads, writes, storage, and selected capacity mode.
- CloudWatch costs depend on log ingestion, retention, and monitoring usage.

### Architecture B

- ALB can introduce ongoing hourly and usage-related charges.
- Fargate costs depend on allocated CPU, memory, and runtime.
- ECR storage may introduce additional costs.
- DynamoDB and CloudWatch costs also apply.

Actual costs depend on AWS region, configuration, usage, and available credits. Serverless services are not automatically free.

## 9. Final Comparison and Selection

Both architectures can meet the functional requirements of the Support Ticket Management System.

However, Architecture A is selected because:

1. The project requires a relatively small REST API with CRUD functionality.
2. API Gateway and Lambda provide a direct serverless solution.
3. DynamoDB is suitable for storing and retrieving tickets using `ticket_id`.
4. No continuously running application container is required.
5. It has fewer infrastructure components and lower operational complexity.
6. Its pay-per-use model is suitable for an educational project with limited and potentially irregular usage.
7. Terraform can manage the infrastructure in a reproducible way.

Architecture B remains a valid alternative, especially if the application later needs greater runtime control, long-running processes, or container portability.

Even though one container is sufficient for the initial Architecture B deployment, it still requires additional container and load-balancer infrastructure that is not necessary for the current project.

## 10. Conclusion

Architecture A – Serverless using API Gateway, Lambda, DynamoDB, IAM, and CloudWatch – is the selected solution for the current project scope.

The decision prioritizes simplicity, cost awareness, scalability, and reduced operational effort while satisfying the required CRUD operations.

Architecture B is documented as an alternative that could be more appropriate for future requirements involving container-based deployment and greater runtime control.
