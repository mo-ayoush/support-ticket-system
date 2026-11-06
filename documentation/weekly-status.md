# Weekly Project Status

## Project

**AWS Serverless Support Ticket Management System**

## Week 1 – Requirements and Architecture Research

**Status: Completed**

Completed activities:

- Defined the project requirements and scope.
- Documented functional and non-functional requirements.
- Identified project assumptions and constraints.
- Analyzed relevant AWS services.
- Designed two alternative architectures:
  - Architecture A: API Gateway, AWS Lambda, and DynamoDB.
  - Architecture B: Application Load Balancer, ECS Fargate, ECR, and DynamoDB.
- Created architecture diagrams for both alternatives.

## Week 2 – Architecture Decision and Initial Terraform Setup

**Status: Completed**

### Architecture Evaluation

- Compared both architectures based on requirement fit, availability, scalability, security, cost, operational complexity, maintainability, and extensibility.
- Selected Architecture A (Serverless) as the preferred solution.
- Documented the reasons for the decision and its trade-offs.

### Architecture Decision Records

Created five Architecture Decision Records (ADRs):

1. ADR-001: Serverless Architecture
2. ADR-002: DynamoDB as the Database
3. ADR-003: API Gateway as the API Entry Point
4. ADR-004: Python and AWS Lambda
5. ADR-005: Terraform for Infrastructure as Code

### API Design

- Defined CRUD endpoints for support tickets.
- Documented request fields and ticket data structure.
- Specified validation rules and allowed priority/status values.
- Documented HTTP response codes and error handling.
- Mapped API operations to DynamoDB operations.
- Documented initial security and logging considerations.

### Initial Terraform Configuration

Created the initial Terraform project structure:

- `versions.tf`: Terraform and AWS provider version constraints.
- `provider.tf`: AWS provider configuration.
- `variables.tf`: Configurable project variables.
- `main.tf`: Common resource tags.
- `outputs.tf`: Configuration outputs.
- `.terraform.lock.hcl`: Locked AWS provider version.

Additional completed activities:

- Created a root `.gitignore` to exclude Terraform state, local provider files, and sensitive variable files.
- Installed and initialized the AWS provider.
- Ran `terraform fmt` successfully.
- Ran `terraform validate` successfully.
- Ran `terraform plan` successfully.

**Infrastructure deployment status:** No AWS resources have been created or deployed yet.

## Week 3 – Infrastructure and Application Implementation

**Status: Not Started**

Planned activities:

- Implement AWS infrastructure using Terraform.
- Create the DynamoDB table.
- Configure API Gateway and Lambda.
- Implement Python CRUD operations using Boto3.
- Configure IAM permissions following least-privilege principles.
- Implement input validation and error handling.
- Configure CloudWatch logging.
- Add functional and infrastructure tests.
- Test successful CRUD operations and failure scenarios.

## Week 4 – Testing, Evaluation, and Final Delivery

**Status: Not Started**

Planned activities:

- Perform final application and infrastructure testing.
- Evaluate the solution using AWS Well-Architected principles.
- Review security, reliability, and cost considerations.
- Document limitations and possible improvements.
- Complete the README and final architecture documentation.
- Prepare the final presentation.
- Destroy AWS resources after testing to avoid unnecessary costs.

## Current Overall Progress

**Week 1:** Completed

**Week 2:** Completed

**Week 3:** Not Started

**Week 4:** Not Started

The project currently has its architecture decisions, API design, and initial Terraform configuration documented. Application implementation and AWS infrastructure deployment remain future tasks.
