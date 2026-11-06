# AWS Service Analysis

## 1. Amazon API Gateway

**Purpose:** Provides HTTP endpoints for clients to create, retrieve, update, list, and delete support tickets.

**Why selected:** It provides a managed API entry point and integrates with AWS Lambda.

**Cost considerations:** Charges depend on the API type, request volume, Region, and applicable pricing or free-tier allowances.

## 2. AWS Lambda

**Purpose:** Executes the Python application logic for ticket operations.

**Why selected:** It avoids maintaining a continuously running application server and scales based on incoming requests.

**Cost considerations:** Charges can depend on invocation count, execution duration, allocated memory, and applicable free-tier or credit terms.

## 3. Amazon DynamoDB

**Purpose:** Stores ticket records persistently, using the ticket ID as the primary key.

**Why selected:** It provides managed NoSQL storage and integrates with Lambda.

**Cost considerations:** Charges depend on the selected capacity or billing mode, reads and writes, stored data, backups, and other enabled features.

## 4. Amazon CloudWatch

**Purpose:** Stores Lambda logs and supports troubleshooting and operational visibility.

**Why selected:** It helps identify application errors and review execution activity.

**Cost considerations:** Log ingestion, storage, metrics, alarms, and retention settings can affect cost. Log retention should be configured deliberately.

## 5. AWS IAM

**Purpose:** Controls which AWS resources and actions the application and deployment process can access.

**Why selected:** Least-privilege permissions help limit unnecessary access.

**Cost considerations:** IAM itself is generally available without an additional charge for standard functionality, but related AWS services may incur charges.

## 6. Terraform

**Purpose:** Defines and manages the infrastructure as code.

**Why selected:** It makes deployment repeatable and allows the infrastructure to be reviewed before changes are applied.

**Cost considerations:** Terraform is the infrastructure-management tool; AWS resources it creates may incur charges. Terraform state must be protected and managed carefully.

## 7. Cost Management Plan

- Use only the services required for the initial implementation.
- Avoid adding an Application Load Balancer, ECS, or Fargate to the selected serverless design.
- Review Terraform plans before applying changes.
- Monitor AWS credits, billing, and service usage.
- Configure log retention to avoid unnecessary storage.
- Destroy project resources after testing and the final demonstration.
- Verify that resources were removed; cleanup does not necessarily erase charges already incurred.

## 8. Pricing Disclaimer

This document identifies potential cost factors and is not a price quote. Actual costs depend on the AWS Region, service configuration, usage, current AWS pricing, and applicable account credits or free-tier terms. Credits do not guarantee that every resource or usage pattern is free.