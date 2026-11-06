# ADR-005: Selection of Terraform for Infrastructure as Code

## Status

Accepted

## Date

2026-11-06

## Context

The Support Ticket Management System requires several AWS resources, including:

- Amazon API Gateway.
- AWS Lambda.
- Amazon DynamoDB.
- AWS IAM roles and policies.
- Amazon CloudWatch logging configuration.

These resources must be deployed in a reproducible and maintainable way.

Manual resource creation through the AWS Management Console could make the infrastructure difficult to reproduce, review, and maintain.

## Decision

Terraform was selected as the Infrastructure as Code (IaC) tool.

Terraform configuration files will define and manage the AWS infrastructure.

The project will use Terraform to:

- Define AWS resources as code.
- Configure relationships between AWS services.
- Reproduce the infrastructure consistently.
- Review planned infrastructure changes before deployment.
- Update infrastructure through controlled configuration changes.
- Remove project resources when they are no longer required.

## Alternatives Considered

### Option A – Terraform

Advantages:

- Declarative Infrastructure as Code.
- Supports AWS resource provisioning.
- Provides reusable and maintainable configuration.
- `terraform plan` previews proposed changes.
- `terraform apply` creates or updates infrastructure.
- `terraform destroy` removes managed resources.
- Infrastructure definitions can be version-controlled in Git.

Disadvantages:

- Requires understanding Terraform syntax and state management.
- Incorrect configuration can create unwanted resources or costs.
- Terraform state must be protected because it may contain sensitive infrastructure information.

### Option B – Manual AWS Console Configuration

Advantages:

- Easy to explore AWS services initially.
- Useful for learning individual service settings.

Disadvantages:

- Difficult to reproduce consistently.
- Manual steps are more likely to be missed.
- Changes are harder to review and track.
- Infrastructure is not fully documented as code.

## Consequences

### Positive Consequences

- Reproducible AWS infrastructure.
- Easier review of infrastructure changes.
- Better project maintainability.
- Infrastructure configuration can be stored in Git.
- Resources can be managed through consistent Terraform commands.

### Negative Consequences

- Terraform state requires careful handling.
- AWS credentials and permissions must be configured correctly.
- Terraform configuration must be tested before deployment.
- Terraform itself does not prevent incorrect or costly infrastructure configurations.

## State and Security Considerations

- Terraform state must not be committed to a public Git repository.
- Local state may be used initially for this individual educational project.
- `.gitignore` must exclude Terraform state files and sensitive variable files.
- AWS credentials must never be hardcoded in Terraform files.
- A remote state backend with appropriate access control and locking can be considered in a future improvement.

## Basic Terraform Workflow

The project will follow this workflow:

1. `terraform init` – Initialize the Terraform working directory and providers.
2. `terraform validate` – Check the Terraform configuration syntax and consistency.
3. `terraform plan` – Review the infrastructure changes Terraform proposes.
4. `terraform apply` – Create or update the AWS infrastructure after reviewing the plan.
5. `terraform destroy` – Remove the managed resources when they are no longer needed.

## Rationale

Terraform was selected because it allows the AWS infrastructure to be defined, reviewed, reproduced, and managed as code.

This supports the project's requirements for reproducibility, maintainability, and controlled infrastructure deployment.
