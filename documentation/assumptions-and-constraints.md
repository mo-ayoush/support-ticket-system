# Assumptions and Constraints

## 1. Assumptions

- The system is intended for a small educational support-ticket workload.
- Clients will interact with the system through HTTP API requests.
- The application will be implemented in Python.
- Amazon DynamoDB will provide persistent ticket storage.
- AWS Lambda will execute the application logic.
- Amazon API Gateway will expose the API endpoints.
- Terraform will manage the cloud infrastructure.
- Ticket IDs will be unique.
- Ticket status and priority values must match the values defined in the project requirements.
- AWS credentials and permissions will be configured before deployment.
- The initial implementation will use a single AWS Region.

## 2. Constraints

- The project must remain cost-conscious.
- AWS usage must be monitored to avoid unexpected charges.
- Resources must be destroyed after testing and the final demonstration.
- The application must return clear errors for invalid input and missing tickets.
- The implementation must be reproducible from the GitHub repository.
- Secrets and private credentials must not be committed to Git.
- The application must not depend on a continuously running virtual machine.
- The project timeline and available AWS credits limit unnecessary infrastructure and service choices.

## 3. Security Considerations

- Use least-privilege IAM permissions where practical.
- Do not use AWS root credentials for routine deployment.
- Keep API access and authorization requirements explicit.
- Validate incoming request data.
- Avoid logging secrets or sensitive ticket contents.
- Keep Terraform state files and credential files out of public version control.

## 4. Out of Scope for the Initial Version

- User registration and full role-based access control.
- Email or SMS notifications.
- A graphical web interface.
- Advanced analytics and dashboards.
- Multi-Region disaster recovery.
- Automated incident response.

These features may be considered future improvements if time and budget permit.

## 5. Cost and Cleanup Plan

- Check the estimated cost and configuration before creating resources.
- Use only the AWS services required by the selected architecture.
- Avoid unnecessary NAT Gateways and other continuously billed resources.
- Review resources after testing.
- Run Terraform destroy when the environment is no longer needed.
- Verify that no project resources remain after cleanup.
- Review the AWS Billing console for any remaining charges or usage.