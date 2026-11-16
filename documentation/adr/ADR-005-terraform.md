# ADR-005: Selection of Terraform for Infrastructure as Code

## Status

Accepted

## Date

2026-11-06

## Context

The Support Ticket Management System requires multiple AWS resources to support its serverless architecture, including:

- Amazon API Gateway REST API.
- Amazon Cognito User Pool and authorizer configuration.
- AWS Lambda functions and execution roles.
- Amazon DynamoDB tables and indexes.
- Amazon SQS FIFO queues and dead-letter queue.
- Amazon SNS notification topic.
- Amazon CloudWatch log groups, alarms, and dashboard.
- AWS Budget configuration.

These resources must be deployed in a reproducible, maintainable, and reviewable way.

Manual resource creation through the AWS Management Console could make the infrastructure difficult to reproduce, review, and maintain. It could also introduce configuration inconsistencies between deployments.

## Decision

Terraform was selected as the Infrastructure as Code (IaC) tool.

Terraform configuration files define and manage the AWS infrastructure. The project uses Terraform to:

- Define AWS resources as code.
- Configure dependencies and relationships between AWS services.
- Reproduce the infrastructure consistently.
- Review planned infrastructure changes before deployment.
- Apply controlled infrastructure changes.
- Remove project-managed resources when they are no longer required.
- Keep infrastructure definitions under Git version control.

## Alternatives Considered

### Option A – Terraform

Advantages:

- Declarative Infrastructure as Code.
- Supports AWS resource provisioning.
- Provides maintainable configuration files.
- `terraform plan` previews proposed changes.
- `terraform apply` creates or updates infrastructure.
- `terraform destroy` removes managed resources.
- Infrastructure definitions can be version-controlled in Git.

Disadvantages:

- Requires understanding Terraform syntax and state management.
- Incorrect configuration can create unwanted resources or costs.
- Terraform state must be protected because it may contain sensitive infrastructure information.
- AWS provider configuration and permissions must be maintained.

### Option B – Manual AWS Console Configuration

Advantages:

- Easy to explore AWS services initially.
- Useful for learning individual service settings.

Disadvantages:

- Difficult to reproduce consistently.
- Manual steps are more likely to be missed.
- Changes are harder to review and track.
- Infrastructure is not fully documented as code.
- Recreating the environment requires repeating manual configuration steps.

## Implementation Design

### Configuration Organization

The Terraform configuration is organized into separate files:

- `main.tf` – Defines AWS resources and their relationships.
- `variables.tf` – Defines configurable input variables.
- `outputs.tf` – Exposes selected deployment outputs.

Lambda deployment packages are prepared as ZIP artifacts and referenced by the Terraform configuration. The Lambda resources use `source_code_hash` to detect changes in deployment package contents.

This keeps application packaging separate from infrastructure resource definitions.

### Infrastructure Managed by Terraform

Terraform manages the project's main infrastructure components:

- API Gateway REST API, routes, methods, integrations, request models, authorizer, and deployment stage.
- Cognito User Pool integration for API authentication and authorization.
- Four Lambda functions: Idempotency, Write, Read, and Notification Worker.
- Four DynamoDB tables for tickets, idempotency records, audit records, and notification outbox records.
- DynamoDB secondary indexes used by application access patterns.
- SQS FIFO write queue and FIFO dead-letter queue.
- SNS topic for operational notifications.
- IAM execution roles and policies for Lambda functions.
- CloudWatch log groups, alarms, and operations dashboard.
- EventBridge schedule for the notification worker.
- AWS Budget with configurable monthly spending limit and notification thresholds.

### Deployment Configuration

The deployment uses the AWS region `eu-central-1`.

Lambda deployment artifacts are packaged separately for each function. Terraform references these ZIP files and uses their content hashes to identify code package changes.

The infrastructure configuration also defines operational settings such as:

- Lambda runtime, memory, and timeout values.
- SQS event source mapping and partial batch failure handling.
- DynamoDB on-demand billing and server-side encryption.
- CloudWatch log retention.
- IAM permissions scoped to the resources and operations required by each function.
- Budget thresholds and notification destinations.

## State and Security Considerations

Terraform state is maintained locally for this individual educational project. No remote backend is configured in the current Terraform configuration.

The following safeguards are applied:

- Terraform state files are excluded from Git.
- Sensitive Terraform variable files are excluded from Git.
- Example variable files contain placeholders rather than actual credentials or secrets.
- AWS credentials are not hardcoded in Terraform configuration files.
- Lambda functions use dedicated IAM execution roles and resource-specific permissions.
- Infrastructure changes are reviewed with `terraform plan` before applying them.

A remote state backend with appropriate access controls and state locking is a possible future improvement, particularly if the project becomes a collaborative or production environment.

## Basic Terraform Workflow

The project follows this workflow:

1. `terraform init` – Initialize the Terraform working directory and providers.
2. `terraform validate` – Check Terraform configuration syntax and consistency.
3. `terraform plan` – Review the infrastructure changes Terraform proposes.
4. `terraform apply` – Create or update AWS infrastructure after reviewing the plan.
5. `terraform destroy` – Remove project-managed resources when the environment is no longer required.

The plan should be reviewed before applying changes, especially when modifying IAM permissions, public API configuration, or resources that may incur AWS charges.

## Consequences

### Positive Consequences

- Reproducible AWS infrastructure.
- Easier review of infrastructure changes.
- Better project maintainability.
- Infrastructure configuration can be stored in Git.
- Consistent deployment and resource management.
- Reduced reliance on undocumented manual AWS Console operations.

### Negative Consequences

- Terraform state requires careful handling.
- AWS credentials and permissions must be configured correctly.
- Terraform configuration must be validated and reviewed before deployment.
- Terraform itself does not prevent incorrect or costly infrastructure configurations.
- Local state is less suitable for collaboration and does not provide remote state locking.

## Rationale

Terraform was selected because it allows AWS infrastructure to be defined, reviewed, reproduced, and managed as code.

It supports the project's requirements for reproducibility, maintainability, controlled deployment, and infrastructure documentation. It also provides a consistent workflow for creating, updating, and eventually removing the project's AWS resources.

## Implementation Evidence

Terraform was used to initialize, validate, plan, and successfully apply the project's AWS infrastructure.

The deployed environment includes the API Gateway REST API, Cognito authorization, four Lambda functions, four DynamoDB tables, SQS FIFO queues, SNS notifications, CloudWatch monitoring resources, EventBridge scheduling, and AWS Budget configuration.

The Terraform configuration is organized into `main.tf`, `variables.tf`, and `outputs.tf`. Lambda deployment packages are provided as ZIP artifacts, with source code hashes used to detect package changes.

Terraform state and sensitive variable files are excluded from Git through `.gitignore`. The public repository contains an example Terraform variables file with placeholders rather than deployment secrets.

The infrastructure deployment was completed successfully. Final resource cleanup with `terraform destroy` remains pending and must be performed after the project demonstration, followed by verification that project-created resources have been removed.
