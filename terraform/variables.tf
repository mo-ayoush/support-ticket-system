variable "aws_region" {
  type    = string
  default = "eu-central-1"
}
variable "project_name" {
  type    = string
  default = "techassist-ticket-system"
}
variable "admin_email" {
  type        = string
  description = "Email subscribed to alerts and budget notifications"
  validation {
    condition     = can(regex("^[^@ ]+@[^@ ]+\\.[^@ ]+$", var.admin_email))
    error_message = "admin_email must be a valid email address."
  }
}
variable "cognito_domain_prefix" {
  type        = string
  description = "Globally unique Cognito hosted UI domain prefix"
  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", var.cognito_domain_prefix))
    error_message = "cognito_domain_prefix must use lowercase letters, digits, and hyphens."
  }
}
variable "api_scope_identifier" {
  type        = string
  description = "Cognito resource server identifier used for API authorization"
  default     = "support-ticket-api"
  validation {
    condition     = can(regex("^[A-Za-z0-9._:/-]+$", var.api_scope_identifier))
    error_message = "api_scope_identifier must be a valid non-empty resource server identifier."
  }
}
variable "frontend_callback_urls" {
  type        = list(string)
  description = "Allowed Cognito sign-in callback URLs for the frontend"
  default     = ["http://localhost:5173/"]
  validation {
    condition     = length(var.frontend_callback_urls) > 0 && alltrue([for url in var.frontend_callback_urls : can(regex("^https://([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\\.)*[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(:([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?(/[^* ]*)?$", url)) || can(regex("^http://(localhost|127\\.0\\.0\\.1)(:([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?(/[^* ]*)?$", url))])
    error_message = "Frontend callbacks must use HTTPS, except localhost development URLs which may use HTTP."
  }
}
variable "frontend_logout_urls" {
  type        = list(string)
  description = "Allowed Cognito sign-out URLs for the frontend"
  default     = ["http://localhost:5173/"]
  validation {
    condition     = length(var.frontend_logout_urls) > 0 && alltrue([for url in var.frontend_logout_urls : can(regex("^https://([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\\.)*[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(:([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?(/[^* ]*)?$", url)) || can(regex("^http://(localhost|127\\.0\\.0\\.1)(:([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?(/[^* ]*)?$", url))])
    error_message = "Frontend logout URLs must use HTTPS, except localhost development URLs which may use HTTP."
  }
}
variable "frontend_allowed_origins" {
  type        = list(string)
  description = "Exact browser origin allowed by API responses; API Gateway gateway-generated errors require a single static origin"
  default     = ["http://localhost:5173"]
  validation {
    condition     = length(var.frontend_allowed_origins) == 1 && alltrue([for origin in var.frontend_allowed_origins : can(regex("^https://([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\\.)*[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(:([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?$", origin)) || can(regex("^http://(localhost|127\\.0\\.0\\.1)(:([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?$", origin))])
    error_message = "Configure exactly one frontend origin. It must use HTTPS, except localhost development origins which may use HTTP; API Gateway gateway-generated errors use a static origin mapping."
  }
}
variable "budget_email" {
  type        = string
  description = "Email for AWS Budget alerts"
  validation {
    condition     = can(regex("^[^@ ]+@[^@ ]+\\.[^@ ]+$", var.budget_email))
    error_message = "budget_email must be a valid email address."
  }
}
variable "monthly_budget_limit" {
  type    = string
  default = "10"
  validation {
    condition     = can(tonumber(var.monthly_budget_limit)) && tonumber(var.monthly_budget_limit) > 0
    error_message = "monthly_budget_limit must be a positive USD amount."
  }
}
variable "lambda_zip_dir" {
  type    = string
  default = "../build/lambdas"
}
variable "tags" {
  type    = map(string)
  default = {}
}
