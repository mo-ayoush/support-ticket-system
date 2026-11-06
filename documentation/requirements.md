# Project Requirements

## 1. Project Overview

The AWS Serverless Support Ticket Management System is designed
to manage IT support tickets through a REST API.

## 2. Functional Requirements

- FR-01: Create a support ticket with required fields.
- FR-02: Retrieve a list of tickets.
- FR-03: Retrieve one ticket by its unique Ticket ID.
- FR-04: Update ticket information and status.
- FR-05: Delete a ticket.
- FR-06: Persist ticket records between application invocations.
- FR-07: Return appropriate error responses for invalid requests and missing tickets.
- FR-08: Record application/runtime logs and provide basic operational visibility.

## 3. Ticket Data Model

Each ticket contains the following fields:

| Field | Description / allowed values |
|---|---|
| `ticket_id` | Unique identifier for a ticket. |
| `title` | Short summary of the problem. |
| `description` | Detailed description of the problem. |
| `priority` | `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`. |
| `status` | `OPEN`, `IN_PROGRESS`, or `RESOLVED`. |
| `created_by` | Identity or name of the ticket creator. |
| `created_timestamp` | Timestamp when the ticket was created. |
| `updated_timestamp` | Timestamp of the latest update. |

## 4. Allowed Values

### Status

- OPEN
- IN_PROGRESS
- RESOLVED

### Priority

- LOW
- MEDIUM
- HIGH
- CRITICAL

## 5. Non-Functional Requirements

The following non-functional requirements are from the original project brief:

- NFR-01 Cost-consciousness: Prefer services that fit a small project and avoid unnecessary always-on resources.
- NFR-02 Security: Use least-privilege IAM permissions; do not commit credentials or secrets.
- NFR-03 Scalability: Support variable request volume without manual server scaling where practical.
- NFR-04 Reliability: Store ticket data persistently and handle failures with meaningful responses.
- NFR-05 Observability: Capture logs and provide basic metrics for troubleshooting.
- NFR-06 Maintainability: Keep application code and Terraform organized and understandable.
- NFR-07 Reproducibility: Allow another person to provision the infrastructure from the repository.
- NFR-08 Testability: Support functional, error, and infrastructure lifecycle tests.

### Project-Specific Non-Functional Requirements

These additional requirements are specific to this project and are separate from the original brief's NFRs:

- PS-NFR-01: Provide secure API access.
- PS-NFR-02: Use Terraform as infrastructure as code.
- PS-NFR-03: Support repeatable deployment and testing.
- PS-NFR-04: Return clear error responses.

## 6. Testing Requirements

- Test ticket creation.
- Test listing tickets.
- Test retrieving a ticket by ID.
- Test updating a ticket.
- Test deleting a ticket.
- Test invalid input.
- Test retrieving a non-existing ticket.
