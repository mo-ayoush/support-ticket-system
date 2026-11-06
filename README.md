# AWS Serverless Support Ticket Management System

A cloud engineering project that builds a serverless REST API for managing IT support tickets using AWS, Python, and Terraform.

## Project Overview

TechAssist GmbH needs a centralized cloud-based system to manage IT support tickets instead of relying on emails, chats, and spreadsheets.

The system will allow users to:

- Create support tickets.
- List all tickets.
- Retrieve a ticket by ID.
- Update existing tickets.
- Delete tickets.

## Selected Architecture

The selected architecture is serverless:

```text
Client
  |
  v
Amazon API Gateway
  |
  v
AWS Lambda (Python)
  |
  v
Amazon DynamoDB

Supporting Services:
- AWS IAM
- Amazon CloudWatch
- Terraform
```

### AWS Services

- **Amazon API Gateway** — exposes HTTP API endpoints and routes requests to Lambda.
- **AWS Lambda** — executes Python application logic, validation, and CRUD operations.
- **Amazon DynamoDB** — stores ticket records.
- **AWS IAM** — controls permissions using least-privilege principles.
- **Amazon CloudWatch** — collects application logs and supports monitoring.
- **Terraform** — defines and manages AWS infrastructure as code.

See the architecture diagrams in the `architecture/` directory.

## Ticket Data Model

Each ticket contains:

- `ticket_id`
- `title`
- `description`
- `priority`
- `status`
- `created_by`
- `created_timestamp`
- `updated_timestamp`

### Supported Status Values

- `OPEN`
- `IN_PROGRESS`
- `RESOLVED`

### Supported Priority Values

- `LOW`
- `MEDIUM`
- `HIGH`
- `CRITICAL`

The application generates unique ticket IDs and UTC timestamps.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/tickets` | Create a ticket |
| GET | `/tickets` | List all tickets |
| GET | `/tickets/{ticket_id}` | Retrieve a ticket |
| PUT | `/tickets/{ticket_id}` | Update a ticket |
| DELETE | `/tickets/{ticket_id}` | Delete a ticket |

See `application/api-design.md` for request and response examples, validation rules, error handling, and DynamoDB operation mapping.

## Repository Structure

```text
support-ticket-system/
├── README.md
├── .gitignore
├── application/
│   └── api-design.md
├── terraform/
│   ├── versions.tf
│   ├── provider.tf
│   ├── variables.tf
│   ├── main.tf
│   ├── outputs.tf
│   └── .terraform.lock.hcl
├── architecture/
│   ├── architecture_option_A_serverless.png
│   └── architecture_option_B_fargate.png
├── documentation/
│   ├── requirements.md
│   ├── assumptions-and-constraints.md
│   ├── aws-service-analysis.md
│   ├── architecture-comparison.md
│   ├── architecture-decision.md
│   ├── weekly-status.md
│   └── adr/
│       ├── ADR-001-serverless-architecture.md
│       ├── ADR-002-dynamodb.md
│       ├── ADR-003-api-gateway.md
│       ├── ADR-004-python-lambda.md
│       └── ADR-005-terraform.md
├── tests/
└── presentation/
```

## Project Documentation

### Requirements and Architecture

- `documentation/requirements.md` — functional and non-functional requirements.
- `documentation/assumptions-and-constraints.md` — project assumptions and constraints.
- `documentation/aws-service-analysis.md` — AWS service selection and cost considerations.
- `documentation/architecture-comparison.md` — comparison of the two proposed architectures.
- `documentation/architecture-decision.md` — final architecture selection and justification.

### Architecture Decision Records

- `documentation/adr/ADR-001-serverless-architecture.md` — serverless architecture decision.
- `documentation/adr/ADR-002-dynamodb.md` — DynamoDB database decision.
- `documentation/adr/ADR-003-api-gateway.md` — API Gateway decision.
- `documentation/adr/ADR-004-python-lambda.md` — Python and Lambda decision.
- `documentation/adr/ADR-005-terraform.md` — Terraform infrastructure management decision.

### Application and Progress

- `application/api-design.md` — API contract, endpoints, validation, and error handling.
- `documentation/weekly-status.md` — weekly project progress.

## Project Status

**Current phase: Week 2 – Architecture Decisions and Initial Terraform Configuration**

Completed:

- Project requirements and assumptions.
- AWS service analysis.
- Two alternative architecture designs.
- Architecture comparison and final selection.
- Five Architecture Decision Records.
- Initial API design and CRUD endpoint definitions.
- Initial Terraform configuration.
- Terraform formatting, initialization, and validation.
- Successful Terraform planning.

**Infrastructure deployment status:** No AWS resources have been created or deployed yet.

Application implementation, AWS infrastructure deployment, and testing are planned for Week 3.

## Cost and Security Considerations

- Monitor AWS usage and available credits.
- Use least-privilege IAM permissions.
- Avoid hardcoding credentials or secrets.
- Never commit private keys, credentials, Terraform state, or sensitive variable files.
- Keep the Terraform provider lock file under version control.
- Review Terraform plans before applying changes.
- Consider DynamoDB On-Demand capacity for the initial workload.
- Destroy project resources after testing and demonstration to avoid unnecessary costs.

## Technologies

- Python
- AWS API Gateway
- AWS Lambda
- Amazon DynamoDB
- AWS IAM
- Amazon CloudWatch
- Terraform
- Git and GitHub
