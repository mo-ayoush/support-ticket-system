# Project Status

## Week 1 – Requirements and Architecture Design

Completed:
- Defined project requirements and assumptions.
- Analyzed AWS services and architectural options.
- Compared serverless architecture with ECS Fargate.
- Selected the serverless architecture.
- Created architecture diagrams and documented design decisions.

## Week 2 – Architecture Decisions and Infrastructure Design

Completed:
- Created five Architecture Decision Records (ADRs).
- Defined the Terraform project structure.
- Designed API routes, authentication, database tables, and supporting AWS services.
- Documented the architecture comparison and selected solution.

## Week 3 – Implementation and AWS Deployment

Completed:
- Implemented the Python 3.12 Lambda functions.
- Implemented ticket creation, listing, retrieval, updating, and soft deletion.
- Implemented idempotency and asynchronous write processing using SQS FIFO.
- Implemented DynamoDB persistence and transactional audit records.
- Integrated Cognito authentication and API Gateway authorization.
- Configured SNS notifications, CloudWatch monitoring resources, and AWS Budgets through Terraform.
- Deployed the infrastructure using Terraform.
- Published the project frontend and connected it to the deployed AWS API.
- Completed manual end-to-end tests for create, read, update, and delete operations.

Automated testing:
- 43 selected Python application tests passed.
- Tests use mocked AWS clients and do not represent live AWS integration tests.

## Week 4 – Evaluation and Final Documentation

Completed:
- Reviewed the five Architecture Decision Records.
- Created a security evaluation.
- Created a cost evaluation.
- Created an AWS Well-Architected Framework review covering five pillars.
- Documented automated and manual testing results.
- Published the project source code and documentation to GitHub.

## Remaining Work

- Review and verify CloudWatch log evidence.
- Review the final architecture diagrams against the deployed implementation.
- Complete the final README and presentation.
- Review remaining security, reliability, and cost limitations.
- Perform the final project demonstration.
- Run Terraform destroy after the demonstration and verify that project resources have been removed.

## Current Project Repository

https://github.com/mo-ayoush/support-ticket-system

## Important Notes

- Ticket deletion is implemented as soft deletion. Tickets are marked as Deleted rather than physically removed from DynamoDB.
- Automated tests use mocked AWS clients.
- Live end-to-end CRUD operations were tested through the deployed application.
- CloudWatch log evidence and final AWS resource cleanup remain pending verification.
