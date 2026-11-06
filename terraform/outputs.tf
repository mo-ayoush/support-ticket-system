output "aws_region" {
  description = "AWS region used by the project"
  value       = var.aws_region
}

output "project_name" {
  description = "Project name"
  value       = var.project_name
}

output "dynamodb_table_name" {
  description = "Configured DynamoDB table name"
  value       = var.dynamodb_table_name
}
