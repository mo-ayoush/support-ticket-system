locals {
  prefix               = var.project_name
  api_stage            = "v1"
  api_scope            = "${aws_cognito_resource_server.api.identifier}/tickets"
  gateway_error_origin = var.frontend_allowed_origins[0]
  common_tags          = merge({ Project = var.project_name, ManagedBy = "Terraform" }, var.tags)
  functions            = toset(["idempotency", "write", "read"])
  ticket_resource      = aws_api_gateway_resource.ticket_id.id
  api_permissions = {
    idempotency_create = { function = "idempotency", pattern = "POST/tickets" }
    idempotency_update = { function = "idempotency", pattern = "PUT/tickets/*" }
    idempotency_delete = { function = "idempotency", pattern = "DELETE/tickets/*" }
    read_list          = { function = "read", pattern = "GET/tickets" }
    read_ticket        = { function = "read", pattern = "GET/tickets/*" }
    read_requests      = { function = "read", pattern = "GET/requests/*" }
    read_dlq           = { function = "read", pattern = "GET/admin/dlq" }
  }
  function_policy_statements = {
    idempotency = [
      { Effect = "Allow", Action = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem"], Resource = [aws_dynamodb_table.idempotency.arn] },
      { Effect = "Allow", Action = ["dynamodb:GetItem"], Resource = [aws_dynamodb_table.tickets.arn] },
      { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = [aws_sqs_queue.writes.arn] }
    ]
    read = [
      { Effect = "Allow", Action = ["dynamodb:GetItem"], Resource = [aws_dynamodb_table.tickets.arn, aws_dynamodb_table.idempotency.arn] },
      { Effect = "Allow", Action = ["dynamodb:Query"], Resource = [aws_dynamodb_table.tickets.arn, "${aws_dynamodb_table.tickets.arn}/index/UserTicketsIndex", "${aws_dynamodb_table.tickets.arn}/index/AdminTicketsIndex", aws_dynamodb_table.audit.arn] },
      { Effect = "Allow", Action = ["dynamodb:UpdateItem"], Resource = [aws_dynamodb_table.idempotency.arn] },
      { Effect = "Allow", Action = ["sqs:ReceiveMessage"], Resource = [aws_sqs_queue.dlq.arn] }
    ]
    write = [
      { Effect = "Allow", Action = ["dynamodb:GetItem"], Resource = [aws_dynamodb_table.tickets.arn, aws_dynamodb_table.idempotency.arn] },
      { Effect = "Allow", Action = ["dynamodb:PutItem"], Resource = [aws_dynamodb_table.tickets.arn, aws_dynamodb_table.audit.arn, aws_dynamodb_table.notifications.arn] },
      { Effect = "Allow", Action = ["dynamodb:UpdateItem"], Resource = [aws_dynamodb_table.tickets.arn, aws_dynamodb_table.idempotency.arn] },
      { Effect = "Allow", Action = ["dynamodb:TransactWriteItems"], Resource = [aws_dynamodb_table.tickets.arn, aws_dynamodb_table.idempotency.arn, aws_dynamodb_table.audit.arn, aws_dynamodb_table.notifications.arn] },
      { Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility"], Resource = [aws_sqs_queue.writes.arn] }
    ]
    notification_worker = [
      { Effect = "Allow", Action = ["dynamodb:Query"], Resource = [aws_dynamodb_table.notifications.arn, "${aws_dynamodb_table.notifications.arn}/index/NotificationStatusIndex"] },
      { Effect = "Allow", Action = ["dynamodb:UpdateItem"], Resource = [aws_dynamodb_table.notifications.arn] },
      { Effect = "Allow", Action = ["sns:Publish"], Resource = [aws_sns_topic.alerts.arn] }
    ]
  }
  methods = {
    "POST /tickets"                  = { resource = aws_api_gateway_resource.tickets.id, method = "POST", function = "idempotency", body = true }
    "GET /tickets"                   = { resource = aws_api_gateway_resource.tickets.id, method = "GET", function = "read", body = false }
    "GET /tickets/{ticket_id}"       = { resource = local.ticket_resource, method = "GET", function = "read", body = false }
    "GET /tickets/{ticket_id}/audit" = { resource = aws_api_gateway_resource.ticket_audit.id, method = "GET", function = "read", body = false }
    "PUT /tickets/{ticket_id}"       = { resource = local.ticket_resource, method = "PUT", function = "idempotency", body = true }
    "DELETE /tickets/{ticket_id}"    = { resource = local.ticket_resource, method = "DELETE", function = "idempotency", body = false }
    "GET /requests/{operation_id}"   = { resource = aws_api_gateway_resource.request_id.id, method = "GET", function = "read", body = false }
    "GET /admin/dlq"                 = { resource = aws_api_gateway_resource.admin_dlq.id, method = "GET", function = "read", body = false }
  }
  options = {
    tickets      = aws_api_gateway_resource.tickets.id
    ticket_id    = aws_api_gateway_resource.ticket_id.id
    ticket_audit = aws_api_gateway_resource.ticket_audit.id
    requests     = aws_api_gateway_resource.requests.id
    request_id   = aws_api_gateway_resource.request_id.id
    admin_dlq    = aws_api_gateway_resource.admin_dlq.id
  }
  cors_origin_condition = join(" || ", [for origin in var.frontend_allowed_origins : "$origin == \"${origin}\""])
}

resource "aws_dynamodb_table" "tickets" {
  name         = "${local.prefix}-tickets"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "ticket_id"
  attribute {
    name = "ticket_id"
    type = "S"
  }
  attribute {
    name = "created_by"
    type = "S"
  }
  attribute {
    name = "created_sort"
    type = "S"
  }
  attribute {
    name = "admin_partition"
    type = "S"
  }
  global_secondary_index {
    name            = "UserTicketsIndex"
    projection_type = "ALL"
    key_schema {
      attribute_name = "created_by"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "created_sort"
      key_type       = "RANGE"
    }
  }
  global_secondary_index {
    name            = "AdminTicketsIndex"
    projection_type = "ALL"
    key_schema {
      attribute_name = "admin_partition"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "created_sort"
      key_type       = "RANGE"
    }
  }
  point_in_time_recovery {
    enabled = false
  }
  server_side_encryption {
    enabled = true
  }
  tags = local.common_tags
}
resource "aws_dynamodb_table" "idempotency" {
  name         = "${local.prefix}-idempotency"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "idempotency_key"
  attribute {
    name = "idempotency_key"
    type = "S"
  }
  attribute {
    name = "ticket_id"
    type = "S"
  }
  global_secondary_index {
    name            = "TicketIdIndex"
    projection_type = "ALL"
    key_schema {
      attribute_name = "ticket_id"
      key_type       = "HASH"
    }
  }
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
  server_side_encryption {
    enabled = true
  }
  tags = local.common_tags
}
resource "aws_dynamodb_table" "audit" {
  name         = "${local.prefix}-audit"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "ticket_id"
  range_key    = "event_sort"
  attribute {
    name = "ticket_id"
    type = "S"
  }
  attribute {
    name = "event_sort"
    type = "S"
  }
  server_side_encryption {
    enabled = true
  }
  tags = local.common_tags
}
resource "aws_dynamodb_table" "notifications" {
  name         = "${local.prefix}-notifications"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "notification_id"
  attribute {
    name = "notification_id"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }
  attribute {
    name = "created_at"
    type = "S"
  }
  global_secondary_index {
    name            = "NotificationStatusIndex"
    projection_type = "ALL"
    key_schema {
      attribute_name = "status"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "created_at"
      key_type       = "RANGE"
    }
  }
  server_side_encryption {
    enabled = true
  }
  tags = local.common_tags
}
resource "aws_sqs_queue" "dlq" {
  name                      = "${local.prefix}-writes-dlq.fifo"
  fifo_queue                = true
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  tags                      = local.common_tags
}
resource "aws_sqs_queue" "writes" {
  name                        = "${local.prefix}-writes.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  visibility_timeout_seconds  = 180
  message_retention_seconds   = 345600
  sqs_managed_sse_enabled     = true
  redrive_policy              = jsonencode({ deadLetterTargetArn = aws_sqs_queue.dlq.arn, maxReceiveCount = 3 })
  tags                        = local.common_tags
}
resource "aws_sns_topic" "alerts" {
  name = "support-ticket-alerts"
  tags = local.common_tags
}
resource "aws_sns_topic_subscription" "admin" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.admin_email
}
resource "aws_cognito_user_pool" "users" {
  name                     = "${local.prefix}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }
  tags = local.common_tags
}
resource "aws_cognito_user_pool_client" "api" {
  name                                 = "${local.prefix}-api"
  user_pool_id                         = aws_cognito_user_pool.users.id
  generate_secret                      = false
  explicit_auth_flows                  = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = var.frontend_callback_urls
  logout_urls                          = var.frontend_logout_urls
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid", "profile", "aws.cognito.signin.user.admin", aws_cognito_resource_server.api.scope_identifiers[0]]
  allowed_oauth_flows_user_pool_client = true
}
resource "aws_cognito_resource_server" "api" {
  identifier   = var.api_scope_identifier
  name         = "${local.prefix} API"
  user_pool_id = aws_cognito_user_pool.users.id
  scope {
    scope_name        = "tickets"
    scope_description = "Access the support ticket API"
  }
}
resource "aws_cognito_user_pool_domain" "frontend" {
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.users.id
}
resource "aws_cognito_user_group" "support" {
  name         = "SupportUsers"
  user_pool_id = aws_cognito_user_pool.users.id
  description  = "Support ticket users"
}
resource "aws_cognito_user_group" "admins" {
  name         = "Admins"
  user_pool_id = aws_cognito_user_pool.users.id
  description  = "Support system administrators"
}
resource "aws_iam_role" "lambda" {
  for_each           = local.functions
  name               = "${local.prefix}-${each.key}-role"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" } }] })
  tags               = local.common_tags
}
resource "aws_iam_role_policy" "lambda" {
  for_each = local.functions
  name     = "${local.prefix}-${each.key}-access"
  role     = aws_iam_role.lambda[each.key].id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = concat(
      [{ Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = ["${aws_cloudwatch_log_group.lambda[each.key].arn}:*"] }],
      local.function_policy_statements[each.key]
    )
  })
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each          = local.functions
  name              = "/aws/lambda/${local.prefix}-${each.key}"
  retention_in_days = 7
  tags              = local.common_tags
}
resource "aws_lambda_function" "app" {
  for_each         = local.functions
  function_name    = "${local.prefix}-${each.key}"
  role             = aws_iam_role.lambda[each.key].arn
  runtime          = "python3.12"
  handler          = "app.handler"
  filename         = "${path.module}/${var.lambda_zip_dir}/${each.key}.zip"
  source_code_hash = filebase64sha256("${path.module}/${var.lambda_zip_dir}/${each.key}.zip")
  timeout          = each.key == "write" ? 30 : 15
  memory_size      = 256
  environment { variables = {
    TICKETS_TABLE            = aws_dynamodb_table.tickets.name
    IDEMPOTENCY_TABLE        = aws_dynamodb_table.idempotency.name
    AUDIT_TABLE              = aws_dynamodb_table.audit.name
    NOTIFICATION_TABLE       = aws_dynamodb_table.notifications.name
    DLQ_QUEUE_URL            = aws_sqs_queue.dlq.url
    API_STAGE_NAME           = local.api_stage
    WRITE_QUEUE_URL          = aws_sqs_queue.writes.url
    ALERT_TOPIC_ARN          = aws_sns_topic.alerts.arn
    FRONTEND_ALLOWED_ORIGINS = jsonencode(var.frontend_allowed_origins)
  } }
  depends_on = [aws_cloudwatch_log_group.lambda, aws_iam_role_policy.lambda]
  tags       = local.common_tags
}
resource "aws_lambda_event_source_mapping" "writes" {
  event_source_arn        = aws_sqs_queue.writes.arn
  function_name           = aws_lambda_function.app["write"].arn
  batch_size              = 1
  function_response_types = ["ReportBatchItemFailures"]
  scaling_config {
    maximum_concurrency = 10
  }

}
resource "aws_iam_role" "notification_worker" {
  name               = "${local.prefix}-notification-worker-role"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" } }] })
  tags               = local.common_tags
}
resource "aws_iam_role_policy" "notification_worker" {
  name = "${local.prefix}-notification-worker-access"
  role = aws_iam_role.notification_worker.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = ["${aws_cloudwatch_log_group.notification_worker.arn}:*"] },
    { Effect = "Allow", Action = ["dynamodb:Query"], Resource = [aws_dynamodb_table.notifications.arn, "${aws_dynamodb_table.notifications.arn}/index/NotificationStatusIndex"] },
    { Effect = "Allow", Action = ["dynamodb:UpdateItem"], Resource = [aws_dynamodb_table.notifications.arn] },
    { Effect = "Allow", Action = ["sns:Publish"], Resource = [aws_sns_topic.alerts.arn] },
    { Effect = "Allow", Action = ["cloudwatch:PutMetricData"], Resource = ["*"], Condition = { StringEquals = { "cloudwatch:namespace" = "TechAssist/Notifications" } } }
  ] })
}
resource "aws_cloudwatch_log_group" "notification_worker" {
  name              = "/aws/lambda/${local.prefix}-notification-worker"
  retention_in_days = 7
  tags              = local.common_tags
}
resource "aws_lambda_function" "notification_worker" {
  function_name    = "${local.prefix}-notification-worker"
  role             = aws_iam_role.notification_worker.arn
  runtime          = "python3.12"
  handler          = "app.handler"
  filename         = "${path.module}/${var.lambda_zip_dir}/notification_worker.zip"
  source_code_hash = filebase64sha256("${path.module}/${var.lambda_zip_dir}/notification_worker.zip")
  timeout          = 30
  memory_size      = 256
  environment { variables = {
    NOTIFICATION_TABLE = aws_dynamodb_table.notifications.name
    ALERT_TOPIC_ARN    = aws_sns_topic.alerts.arn
  } }
  depends_on = [aws_cloudwatch_log_group.notification_worker, aws_iam_role_policy.notification_worker]
  tags       = local.common_tags
}
resource "aws_cloudwatch_event_rule" "notification_worker" {
  name                = "${local.prefix}-notification-outbox"
  description         = "Dispatch retryable notification outbox records and quarantine stale claims"
  schedule_expression = "rate(1 minute)"
  tags                = local.common_tags
}
resource "aws_cloudwatch_event_target" "notification_worker" {
  rule = aws_cloudwatch_event_rule.notification_worker.name
  arn  = aws_lambda_function.notification_worker.arn
}
resource "aws_lambda_permission" "notification_worker_schedule" {
  statement_id  = "AllowNotificationOutboxSchedule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.notification_worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.notification_worker.arn
}
resource "aws_api_gateway_rest_api" "api" {
  name = "${local.prefix}-api"
  endpoint_configuration { types = ["REGIONAL"] }
  tags = local.common_tags
}
resource "aws_api_gateway_authorizer" "cognito" {
  name            = "${local.prefix}-cognito"
  rest_api_id     = aws_api_gateway_rest_api.api.id
  type            = "COGNITO_USER_POOLS"
  provider_arns   = [aws_cognito_user_pool.users.arn]
  identity_source = "method.request.header.Authorization"
}
resource "aws_api_gateway_resource" "tickets" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "tickets"
}
resource "aws_api_gateway_resource" "ticket_id" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.tickets.id
  path_part   = "{ticket_id}"

}
resource "aws_api_gateway_resource" "ticket_audit" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.ticket_id.id
  path_part   = "audit"
}
resource "aws_api_gateway_resource" "requests" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "requests"
}
resource "aws_api_gateway_resource" "admin" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "admin"
}
resource "aws_api_gateway_resource" "admin_dlq" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.admin.id
  path_part   = "dlq"
}
resource "aws_api_gateway_resource" "request_id" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.requests.id
  path_part   = "{operation_id}"

}
resource "aws_api_gateway_request_validator" "body" {
  name                        = "validate-body-and-parameters"
  rest_api_id                 = aws_api_gateway_rest_api.api.id
  validate_request_body       = true
  validate_request_parameters = true
}
resource "aws_api_gateway_request_validator" "parameters" {
  name                        = "validate-request-parameters"
  rest_api_id                 = aws_api_gateway_rest_api.api.id
  validate_request_body       = false
  validate_request_parameters = true
}
resource "aws_api_gateway_model" "create_ticket" {
  rest_api_id  = aws_api_gateway_rest_api.api.id
  name         = "TicketCreate"
  content_type = "application/json"
  schema = jsonencode({
    "$schema" = "http://json-schema.org/draft-04/schema#", type = "object",
    required  = ["title", "description", "priority"],
    properties = { title = { type = "string", minLength = 1, maxLength = 200 }, description = { type = "string", minLength = 1, maxLength = 5000 },
    priority = { type = "string", enum = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] }, status = { type = "string", enum = ["OPEN", "IN_PROGRESS", "RESOLVED"] } },
    additionalProperties = false
  })
}
resource "aws_api_gateway_model" "update_ticket" {
  rest_api_id  = aws_api_gateway_rest_api.api.id
  name         = "TicketUpdate"
  content_type = "application/json"
  schema = jsonencode({
    "$schema" = "http://json-schema.org/draft-04/schema#", type = "object",
    required  = ["title", "description", "priority", "status", "version"],
    properties = { title = { type = "string", minLength = 1, maxLength = 200 }, description = { type = "string", minLength = 1, maxLength = 5000 },
      priority = { type = "string", enum = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] },
    status = { type = "string", enum = ["OPEN", "IN_PROGRESS", "RESOLVED"] }, version = { type = "integer", minimum = 1 } },
    additionalProperties = false
  })
}
resource "aws_api_gateway_method" "method" {
  for_each             = local.methods
  rest_api_id          = aws_api_gateway_rest_api.api.id
  resource_id          = each.value.resource
  http_method          = each.value.method
  authorization        = "COGNITO_USER_POOLS"
  authorizer_id        = aws_api_gateway_authorizer.cognito.id
  authorization_scopes = [local.api_scope]
  request_validator_id = each.value.body ? aws_api_gateway_request_validator.body.id : aws_api_gateway_request_validator.parameters.id
  request_models       = each.key == "POST /tickets" ? { "application/json" = aws_api_gateway_model.create_ticket.name } : (each.key == "PUT /tickets/{ticket_id}" ? { "application/json" = aws_api_gateway_model.update_ticket.name } : {})
  request_parameters   = contains(["GET /tickets/{ticket_id}", "GET /tickets/{ticket_id}/audit", "PUT /tickets/{ticket_id}", "DELETE /tickets/{ticket_id}"], each.key) ? { "method.request.path.ticket_id" = true } : (each.key == "GET /requests/{operation_id}" ? { "method.request.path.operation_id" = true } : {})
}
resource "aws_api_gateway_method" "options" {
  for_each      = local.options
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = each.value
  http_method   = "OPTIONS"
  authorization = "NONE"
}
resource "aws_api_gateway_integration" "options" {
  for_each             = local.options
  rest_api_id          = aws_api_gateway_rest_api.api.id
  resource_id          = each.value
  http_method          = aws_api_gateway_method.options[each.key].http_method
  type                 = "MOCK"
  request_templates    = { "application/json" = "{\"statusCode\": 200}" }
  passthrough_behavior = "NEVER"
}
resource "aws_api_gateway_method_response" "options" {
  for_each    = local.options
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = each.value
  http_method = aws_api_gateway_method.options[each.key].http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Vary"                         = true
  }
}
resource "aws_api_gateway_integration_response" "options" {
  for_each    = local.options
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = each.value
  http_method = aws_api_gateway_method.options[each.key].http_method
  status_code = aws_api_gateway_method_response.options[each.key].status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Authorization,Content-Type,Idempotency-Key'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
    "method.response.header.Vary"                         = "'Origin'"
  }
  response_templates = { "application/json" = "#set($origin = $input.params().header.get('Origin'))\n#if(${local.cors_origin_condition})\n#set($context.responseOverride.header.Access-Control-Allow-Origin = $origin)\n#end\n{}" }
  depends_on         = [aws_api_gateway_integration.options]
}
resource "aws_api_gateway_gateway_response" "default_4xx" {
  rest_api_id        = aws_api_gateway_rest_api.api.id
  response_type      = "DEFAULT_4XX"
  response_templates = { "application/json" = "{\"message\":$context.error.messageString}" }
  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'${local.gateway_error_origin}'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Authorization,Content-Type,Idempotency-Key'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
    "gatewayresponse.header.Vary"                         = "'Origin'"
  }
}
resource "aws_api_gateway_gateway_response" "default_5xx" {
  rest_api_id        = aws_api_gateway_rest_api.api.id
  response_type      = "DEFAULT_5XX"
  response_templates = { "application/json" = "{\"message\":$context.error.messageString}" }
  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'${local.gateway_error_origin}'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Authorization,Content-Type,Idempotency-Key'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
    "gatewayresponse.header.Vary"                         = "'Origin'"
  }
}
resource "aws_api_gateway_integration" "lambda" {
  for_each                = local.methods
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = each.value.resource
  http_method             = aws_api_gateway_method.method[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.app[each.value.function].invoke_arn
}
resource "aws_lambda_permission" "api" {
  for_each      = local.api_permissions
  statement_id  = "AllowApiGateway-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app[each.value.function].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/${local.api_stage}/${each.value.pattern}"
}
resource "aws_api_gateway_deployment" "api" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  triggers    = { redeployment = filesha1("${path.module}/main.tf") }
  lifecycle { create_before_destroy = true }
  depends_on = [
    aws_api_gateway_method.method,
    aws_api_gateway_integration.lambda,
    aws_api_gateway_method.options,
    aws_api_gateway_integration.options,
    aws_api_gateway_integration_response.options,
    aws_api_gateway_gateway_response.default_4xx,
    aws_api_gateway_gateway_response.default_5xx,
    aws_api_gateway_authorizer.cognito,
    aws_api_gateway_model.create_ticket,
    aws_api_gateway_model.update_ticket,
    aws_api_gateway_resource.tickets,
    aws_api_gateway_resource.ticket_id,
    aws_api_gateway_resource.ticket_audit,
    aws_api_gateway_resource.requests,
    aws_api_gateway_resource.request_id,
    aws_api_gateway_resource.admin,
    aws_api_gateway_resource.admin_dlq,
    aws_api_gateway_request_validator.body,
    aws_api_gateway_request_validator.parameters,
  ]
}
resource "aws_api_gateway_stage" "live" {
  deployment_id = aws_api_gateway_deployment.api.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = local.api_stage
  depends_on    = [aws_api_gateway_account.api, aws_iam_role_policy_attachment.api_gateway_cloudwatch]
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId          = "$context.requestId", requestTime = "$context.requestTime",
      httpMethod         = "$context.httpMethod", resourcePath = "$context.resourcePath",
      status             = "$context.status", responseLength = "$context.responseLength",
      integrationLatency = "$context.integrationLatency"
    })
  }
  tags = local.common_tags
}
resource "aws_cloudwatch_log_group" "api_access" {
  name              = "/aws/apigateway/${local.prefix}-access"
  retention_in_days = 7
  tags              = local.common_tags
}
resource "aws_iam_role" "api_gateway_cloudwatch" {
  name               = "${local.prefix}-apigateway-cloudwatch-role"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "apigateway.amazonaws.com" } }] })
  tags               = local.common_tags
}
resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  role       = aws_iam_role.api_gateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}
resource "aws_api_gateway_account" "api" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn
}
resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  stage_name  = aws_api_gateway_stage.live.stage_name
  method_path = "*/*"
  settings {
    metrics_enabled    = true
    logging_level      = "OFF"
    data_trace_enabled = false
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each            = local.functions
  alarm_name          = "${local.prefix}-${each.key}-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.app[each.key].function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
  tags                = local.common_tags
}
resource "aws_cloudwatch_metric_alarm" "dlq" {
  alarm_name          = "${local.prefix}-dlq-visible"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.dlq.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  tags                = local.common_tags
}
resource "aws_cloudwatch_metric_alarm" "notification_worker_errors" {
  alarm_name          = "${local.prefix}-notification-worker-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.notification_worker.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
  tags                = local.common_tags
}
resource "aws_cloudwatch_metric_alarm" "notification_outbox_ambiguous" {
  alarm_name          = "${local.prefix}-notification-outbox-ambiguous"
  namespace           = "TechAssist/Notifications"
  metric_name         = "Ambiguous"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
  tags                = local.common_tags
}
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${local.prefix}-api-5xx"
  namespace           = "AWS/ApiGateway"
  metric_name         = "5XXError"
  dimensions          = { ApiName = aws_api_gateway_rest_api.api.name, Stage = local.api_stage }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "notBreaching"
  tags                = local.common_tags
}
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.prefix}-operations"
  dashboard_body = jsonencode({ widgets = [
    { type = "metric", x = 0, y = 0, width = 12, height = 6, properties = { metrics = concat([for f in local.functions : ["AWS/Lambda", "Invocations", "FunctionName", "${local.prefix}-${f}"]], [for f in local.functions : ["AWS/Lambda", "Errors", "FunctionName", "${local.prefix}-${f}"]], [for f in local.functions : ["AWS/Lambda", "Duration", "FunctionName", "${local.prefix}-${f}"]]), period = 300, region = var.aws_region, title = "Lambda activity" } },
    { type = "metric", x = 12, y = 0, width = 12, height = 6, properties = { metrics = [["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.writes.name], [".", ".", ".", aws_sqs_queue.dlq.name]], period = 300, region = var.aws_region, title = "Queues" } },
    { type = "metric", x = 0, y = 6, width = 12, height = 6, properties = { metrics = [["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", aws_dynamodb_table.tickets.name], [".", "ConsumedWriteCapacityUnits", ".", "."]], period = 300, region = var.aws_region, title = "DynamoDB capacity" } },
    {
      type   = "metric"
      x      = 12
      y      = 6
      width  = 12
      height = 6
      properties = {
        title  = "Notification Worker"
        region = var.aws_region
        period = 300
        metrics = [
          ["AWS/Lambda", "Invocations", "FunctionName", "${local.prefix}-notification-worker", { stat = "Sum" }],
          ["AWS/Lambda", "Errors", "FunctionName", "${local.prefix}-notification-worker", { stat = "Sum" }],
          ["AWS/Lambda", "Duration", "FunctionName", "${local.prefix}-notification-worker", { stat = "Average" }]
        ]
      }
    },
    {
      type   = "metric"
      x      = 0
      y      = 12
      width  = 12
      height = 6
      properties = {
        title  = "API Gateway Errors"
        region = var.aws_region
        period = 300
        metrics = [
          ["AWS/ApiGateway", "4XXError", "ApiName", aws_api_gateway_rest_api.api.name, "Stage", local.api_stage, { stat = "Sum" }],
          ["AWS/ApiGateway", "5XXError", "ApiName", aws_api_gateway_rest_api.api.name, "Stage", local.api_stage, { stat = "Sum" }]
        ]
      }
    }
  ] })
}
resource "aws_budgets_budget" "monthly" {
  name         = "${local.prefix}-monthly"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_limit
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 5
    threshold_type             = "ABSOLUTE_VALUE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 8
    threshold_type             = "ABSOLUTE_VALUE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 10
    threshold_type             = "ABSOLUTE_VALUE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
}
