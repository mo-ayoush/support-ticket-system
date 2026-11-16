"""Source-level checks for security settings that are otherwise provider resources."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
MAIN = (ROOT / "terraform" / "main.tf").read_text()
VARIABLES = (ROOT / "terraform" / "variables.tf").read_text()
WORKER = (ROOT / "lambdas" / "notification_worker" / "app.py").read_text()


class TerraformSecurityConfigTests(unittest.TestCase):
    @staticmethod
    def url_validation_patterns(variable):
        block = VARIABLES.split(f'variable "{variable}"', 1)[1].split("\n}", 1)[0]
        encoded = re.findall(r'can\(regex\("((?:\\.|[^"])*)",\s*(?:url|origin)\)\)', block)
        return [json.loads(f'"{pattern}"') for pattern in encoded]

    def test_outbox_worker_is_scheduled_and_ambiguous_records_are_not_claimed(self):
        self.assertIn('resource "aws_cloudwatch_event_rule" "notification_worker"', MAIN)
        self.assertIn('schedule_expression = "rate(1 minute)"', MAIN)
        self.assertIn('status not in ("PENDING", "RETRY")', WORKER)
        self.assertIn('":status": "AMBIGUOUS"', WORKER)

    def test_default_gateway_errors_have_cors_headers(self):
        self.assertIn('gateway_error_origin = var.frontend_allowed_origins[0]', MAIN)
        for response in ("default_4xx", "default_5xx"):
            block = re.search(rf'resource "aws_api_gateway_gateway_response" "{response}" \{{(.*?)\n\}}', MAIN, re.S)
            self.assertIsNotNone(block)
            self.assertIn("Access-Control-Allow-Origin", block.group(1))
            self.assertIn("Access-Control-Allow-Headers", block.group(1))
            self.assertIn("'${local.gateway_error_origin}'", block.group(1))
            self.assertNotIn("'*'", block.group(1))
        self.assertIn("length(var.frontend_allowed_origins) == 1", VARIABLES)

    def test_gateway_and_preflight_cors_use_the_configured_allow_list(self):
        self.assertIn('gateway_error_origin = var.frontend_allowed_origins[0]', MAIN)
        self.assertIn('cors_origin_condition = join(" || ", [for origin in var.frontend_allowed_origins : "$origin == \\"${origin}\\""])', MAIN)
        self.assertIn('responseOverride.header.Access-Control-Allow-Origin = $origin', MAIN)
        self.assertIn('length(var.frontend_allowed_origins) == 1', VARIABLES)
        allowed = "https://support.example.test"
        self.assertEqual(allowed, "https://support.example.test")
        self.assertNotEqual(allowed, "https://attacker.example.test")

    def test_api_access_log_omits_tokens_headers_and_bodies_and_metrics_are_enabled(self):
        stage = MAIN.split('resource "aws_api_gateway_stage" "live" {', 1)[1].split('resource "aws_cloudwatch_log_group" "api_access"', 1)[0]
        self.assertIn("access_log_settings", stage)
        self.assertIn("$context.resourcePath", stage)
        self.assertIn("$context.integrationLatency", stage)
        self.assertNotIn("Authorization", stage)
        for sensitive in ("$context.requestBody", "$context.identity", "$context.authorizer", "$context.requestHeader"):
            self.assertNotIn(sensitive, stage)
        self.assertRegex(MAIN, r'metrics_enabled\s*=\s*true')
        self.assertIn('resource "aws_cloudwatch_metric_alarm" "api_5xx"', MAIN)
        self.assertNotIn('resource "aws_cloudwatch_metric_alarm" "api_4xx"', MAIN)

    def test_cognito_methods_require_custom_api_scope(self):
        self.assertIn('resource "aws_cognito_resource_server" "api"', MAIN)
        self.assertIn('authorization_scopes = [local.api_scope]', MAIN)
        self.assertIn('aws_cognito_resource_server.api.scope_identifiers[0]', MAIN)

    def test_http_is_permitted_only_for_loopback_frontend_urls(self):
        self.assertEqual(VARIABLES.count('regex("^https://'), 3)
        self.assertEqual(VARIABLES.count('regex("^http://(localhost|127\\\\.0\\\\.0\\\\.1)'), 3)
        self.assertNotIn('regex("^https?://', VARIABLES)

    def test_frontend_urls_reject_malformed_hosts_and_out_of_range_ports(self):
        for variable, accepts_path in (("frontend_callback_urls", True), ("frontend_logout_urls", True),
                                       ("frontend_allowed_origins", False)):
            https_pattern, localhost_pattern = self.url_validation_patterns(variable)
            valid_https = "https://support.example.test:65535/callback" if accepts_path else "https://support.example.test:65535"
            invalid_hostnames = [
                "https://-support.example.test",
                "https://support-.example.test",
                "https://support..example.test",
            ]
            self.assertIsNotNone(re.fullmatch(https_pattern, valid_https), variable)
            for url in invalid_hostnames:
                candidate = url + ("/callback" if accepts_path else "")
                self.assertIsNone(re.fullmatch(https_pattern, candidate), (variable, candidate))
            invalid_port = "https://support.example.test:65536" + ("/callback" if accepts_path else "")
            zero_port = "https://support.example.test:0" + ("/callback" if accepts_path else "")
            self.assertIsNone(re.fullmatch(https_pattern, invalid_port), (variable, invalid_port))
            self.assertIsNone(re.fullmatch(https_pattern, zero_port), (variable, zero_port))
            self.assertIsNotNone(re.fullmatch(localhost_pattern, "http://localhost:5173" + ("/callback" if accepts_path else "")))
            self.assertIsNotNone(re.fullmatch(localhost_pattern, "http://127.0.0.1:65535" + ("/callback" if accepts_path else "")))
            self.assertIsNone(re.fullmatch(localhost_pattern, "http://localhost:65536" + ("/callback" if accepts_path else "")))
            self.assertIsNone(re.fullmatch(localhost_pattern, "http://remote.example.test" + ("/callback" if accepts_path else "")))

    def test_lambda_and_api_gateway_logging_roles_are_least_privilege(self):
        write_policy = MAIN.split("    write = [", 1)[1].split("    notification_worker = [", 1)[0]
        read_policy = MAIN.split("    read = [", 1)[1].split("    write = [", 1)[0]
        self.assertNotIn('"sns:Publish"', write_policy)
        self.assertIn("aws_dynamodb_table.idempotency.arn", read_policy.split('"dynamodb:GetItem"', 1)[1].split("}", 1)[0])

        api_role = re.search(r'resource "aws_iam_role" "api_gateway_cloudwatch" \{(.*?)\n\}', MAIN, re.S)
        self.assertIsNotNone(api_role)
        self.assertIn("apigateway.amazonaws.com", api_role.group(1))

        api_attachment = re.search(r'resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" \{(.*?)\n\}', MAIN, re.S)
        self.assertIsNotNone(api_attachment)
        self.assertIn("aws_iam_role.api_gateway_cloudwatch.name", api_attachment.group(1))
        self.assertIn("AmazonAPIGatewayPushToCloudWatchLogs", api_attachment.group(1))

        worker_policy = MAIN.split('resource "aws_iam_role_policy" "notification_worker"', 1)[1].split('resource "aws_cloudwatch_log_group" "notification_worker"', 1)[0]
        self.assertIn('"sns:Publish"', worker_policy)
        self.assertIn('aws_sns_topic.alerts.arn', worker_policy)
        lambda_policy = MAIN.split('resource "aws_iam_role_policy" "lambda"', 1)[1].split('resource "aws_lambda_function" "app"', 1)[0]
        self.assertIn('aws_cloudwatch_log_group.lambda[each.key].arn', lambda_policy)
        self.assertNotIn('"logs:DescribeLogGroups"', lambda_policy)

    def test_cloudwatch_alarm_metrics_have_expected_namespace_and_dimensions(self):
        api_alarm = re.search(r'resource "aws_cloudwatch_metric_alarm" "api_5xx" \{(.*?)\n\}', MAIN, re.S)
        self.assertIsNotNone(api_alarm)
        block = api_alarm.group(1)
        self.assertIn('namespace           = "AWS/ApiGateway"', block)
        self.assertIn('metric_name         = "5XXError"', block)
        self.assertIn('ApiName = aws_api_gateway_rest_api.api.name, Stage = local.api_stage', block)
        self.assertIn('evaluation_periods  = 1', block)
        self.assertIn('period              = 300', block)
        self.assertIn('threshold           = 1', block)
        self.assertNotIn('resource "aws_cloudwatch_metric_alarm" "api_latency"', MAIN)


if __name__ == "__main__":
    unittest.main()
