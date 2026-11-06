# ADR-002: Selection of Amazon DynamoDB

## Status

Accepted

## Date

2026-11-06

## Context

The Support Ticket Management System needs persistent storage for support tickets.

Each ticket contains the following attributes:

- `ticket_id`
- `title`
- `description`
- `priority`
- `status`
- `created_by`
- `created_timestamp`
- `updated_timestamp`

The application must support creating, listing, retrieving, updating, and deleting tickets.

Two database services were considered: Amazon DynamoDB and Amazon RDS.

## Decision

Amazon DynamoDB was selected as the database service.

A DynamoDB table will store support tickets. Each ticket will be stored as an individual item, and `ticket_id` will be the partition key.

### DynamoDB Data Model

DynamoDB is a NoSQL database.

- Data is stored in tables.
- Each table contains items.
- Each item contains attributes.
- Each item represents one support ticket in this project.
- The `ticket_id` attribute uniquely identifies a ticket and is used as the partition key.

Example:

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

## Alternatives Considered

### Option A – Amazon DynamoDB

Advantages:

- Managed NoSQL database without database server management.
- Suitable for key-based access using `ticket_id`.
- Integrates directly with AWS Lambda through the AWS SDK.
- Supports on-demand capacity mode.
- Fits the project's simple ticket CRUD access patterns.

Disadvantages:

- Does not provide the same relational model and SQL join capabilities as RDS.
- Query patterns should be considered when designing the table.
- A Scan operation can become inefficient and costly as the table grows.

### Option B – Amazon RDS

Amazon RDS is a managed relational database service.

Data is organized into tables, rows, and columns, and applications use SQL to query and modify data.

Advantages:

- Supports SQL queries.
- Supports relationships between tables and relational joins.
- Suitable for complex relational data models.

Disadvantages:

- Requires database engine and connection configuration.
- Database capacity and connection management must be considered.
- More than the project currently needs for simple ticket-based CRUD operations.

## CRUD Operation Mapping

The application will use the following DynamoDB operations:

| Application operation | DynamoDB operation |
|---|---|
| Create ticket | `PutItem` |
| List tickets | `Scan` |
| Retrieve ticket by ID | `GetItem` |
| Update ticket | `UpdateItem` |
| Delete ticket | `DeleteItem` |

The `Scan` operation is acceptable for the initial small educational workload. If the application grows, more efficient access patterns using `Query` and suitable indexes can be considered.

## Consequences

### Positive Consequences

- Simple data model for individual support tickets.
- Direct access using the `ticket_id` partition key.
- No relational joins are required for the current scope.
- Good integration with the selected serverless architecture.
- Reduced database server management.

### Negative Consequences

- Less suitable for complex relational queries.
- Future filtering and access patterns may require secondary indexes.
- Scan operations should not be relied on for large datasets.

## Rationale

The current application primarily works with individual tickets identified by a unique `ticket_id`.

It does not require complex relationships, multiple related tables, or SQL joins.

DynamoDB therefore provides a suitable and straightforward storage solution for the project's current requirements.

Amazon RDS remains a possible alternative if future requirements introduce complex relational data or SQL-based reporting.
