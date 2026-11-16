# Cost Evaluation

## 1. Overview

Cost optimization was an important consideration when designing the AWS Support Ticket Management System.

The project uses managed and serverless AWS services to avoid maintaining continuously running servers.

## 2. Cost-Conscious Architecture Decisions

- **AWS Lambda:** Charges are based on requests and execution duration, avoiding the cost of continuously running application servers.
- **Amazon API Gateway:** Provides managed API endpoints without requiring a self-managed server.
- **Amazon DynamoDB:** Uses on-demand billing (`PAY_PER_REQUEST`), which is suitable for workloads with variable or low traffic.
- **Amazon SQS:** Buffers write requests and supports asynchronous processing.
- **Amazon SNS:** Provides managed notification delivery.
- **Amazon Cognito:** Provides managed user authentication.
- **Amazon CloudWatch:** Provides logging, metrics, dashboards, and alarms.

## 3. Cost Controls

- Terraform makes infrastructure easier to review and manage.
- AWS Budgets is configured to help monitor spending against a monthly budget.
- DynamoDB on-demand billing avoids provisioning capacity in advance.
- Serverless services reduce the need for continuously running compute resources.
- Project resources should be destroyed after the final demonstration if they are no longer needed.

## 4. Potential Cost Risks

Some AWS services may generate charges even when application traffic is low.

Potential cost sources include:

- API Gateway requests.
- Lambda invocations and execution duration.
- DynamoDB read and write requests.
- SQS requests.
- SNS notifications.
- CloudWatch logs, metrics, and alarms.
- Cognito usage.
- Data transfer and other supporting AWS resources.

Actual costs depend on service usage, AWS pricing, and the selected region.

## 5. Limitations

- No verified final cost measurement is included in this evaluation.
- The project has not been tested under production traffic.
- Costs may increase with higher request volumes, longer Lambda execution times, or increased log retention.
- AWS Budgets provides alerts but does not automatically guarantee that spending will remain below the configured budget.

## 6. Future Cost Optimization

- Review AWS Cost Explorer regularly.
- Monitor AWS Budgets notifications.
- Set appropriate CloudWatch log retention periods.
- Review DynamoDB access patterns and indexes.
- Remove unused resources after testing.
- Consider reserved or committed-use pricing only if future workload patterns justify it.

## 7. Conclusion

The selected serverless architecture is designed to keep infrastructure costs manageable for a small or variable workload.

Pay-per-request services, managed infrastructure, and AWS Budgets support cost awareness.

Actual production costs would need to be measured and reviewed as usage increases.
