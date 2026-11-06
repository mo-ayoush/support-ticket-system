variable "aws_region" {
  description = "AWS region where the infrastructure will be deployed"
  type        = string
  default     = "eu-central-1"
}

variable "project_name" {
  description = "Name of the support ticket project"
  type        = string
  default     = "support-ticket-system"
}

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
  type        = string
  default     = "support-tickets"
}
