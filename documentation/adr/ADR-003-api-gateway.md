# ADR-003: Selection of Amazon API Gateway

## Status

Accepted

## Date

2026-11-06

## Context

The Support Ticket Management System requires a REST API that allows clients to create, list, retrieve, update, and delete support tickets.

Two API entry-point approaches were considered:

- Amazon API Gateway in the serverless architecture.
- Application Load Balancer (ALB) in the container-based architecture.

## Decision

Amazon API Gateway was selected as the API entry point for Architecture A.

API Gateway will receive HTTP requests, match the configured routes and methods, and invoke the appropriate AWS Lambda integration.

The planned API endpoints are:

| HTTP Method | Endpoint | Purpose |
|---|---|---|
| POST | `/tickets` | Create a ticket |
| GET | `/tickets` | List tickets |
| GET | `/tickets/{ticket_id}` | Retrieve a ticket by ID |
| PUT | `/tickets/{ticket_id}` | Update a ticket |
| DELETE | `/tickets/{ticket_id}` | Delete a ticket |

The Python Lambda application will handle request validation, business logic, DynamoDB operations, and response generation.

## Alternatives Considered

### Option A – Amazon API Gateway

Advantages:

- Managed API entry point.
- Supports HTTP routes and methods.
- Integrates directly with AWS Lambda.
- Fits the selected serverless architecture.
- Avoids managing an application load balancer for the API.

Disadvantages:

- Requires route and integration configuration.
- API type and features must be selected appropriately.
- API authentication and authorization must be configured explicitly.

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

- API Gateway handles the API entry point, HTTP routes, and methods.
- Lambda contains the Python business logic and request handling.
- DynamoDB stores ticket records.

### Architecture B

- ALB receives and forwards incoming traffic.
- The Python API running inside the ECS container implements the routes, HTTP methods, validation, and business logic.
- DynamoDB stores ticket records.

## Consequences

### Positive Consequences

- Clear separation between API routing and application business logic.
- Direct integration with Lambda.
- Fewer infrastructure components than the ALB and ECS approach.
- Suitable for the project's required CRUD endpoints.

### Negative Consequences

- API routes and Lambda integrations must be configured correctly.
- API authentication must be addressed separately.
- API Gateway introduces an additional managed service whose request pricing must be considered.

## Rationale

API Gateway is the best fit for the selected serverless architecture because it provides the required HTTP API entry point and integrates with Lambda without requiring a continuously running application container.

ALB remains a suitable entry point for the container-based alternative, where the Python API itself handles routing and business logic.
