output "api_base_url" {
  value       = aws_api_gateway_stage.live.invoke_url
  description = "Base URL for the deployed v1 API"
}
output "cognito_user_pool_id" {
  value       = aws_cognito_user_pool.users.id
  description = "Cognito User Pool ID"
}
output "cognito_client_id" {
  value       = aws_cognito_user_pool_client.api.id
  description = "Public Cognito app client ID"
}
output "cognito_hosted_ui_domain" {
  value       = "${aws_cognito_user_pool_domain.frontend.domain}.auth.${var.aws_region}.amazoncognito.com"
  description = "Cognito managed login domain for the frontend"
}
output "cognito_api_scope" {
  value       = aws_cognito_resource_server.api.scope_identifiers[0]
  description = "OAuth scope required by API Gateway methods"
}
output "write_queue_url" {
  value = aws_sqs_queue.writes.url
}
output "alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}
