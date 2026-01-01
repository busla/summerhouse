# Gateway-v2 Module Outputs
# Updated for REST API (T019-T023)

# -----------------------------------------------------------------------------
# API Gateway Outputs (T019-T021)
# -----------------------------------------------------------------------------

output "api_gateway_url" {
  description = "API Gateway invoke URL (from stage)"
  value       = aws_api_gateway_stage.main.invoke_url
}

output "api_gateway_id" {
  description = "API Gateway REST API ID"
  value       = aws_api_gateway_rest_api.main.id
}

output "api_gateway_arn" {
  description = "API Gateway execution ARN"
  value       = aws_api_gateway_rest_api.main.execution_arn
}

# T023: New output for REST API stage name
output "api_gateway_stage_name" {
  description = "API Gateway stage name"
  value       = aws_api_gateway_stage.main.stage_name
}

# -----------------------------------------------------------------------------
# Lambda Outputs
# -----------------------------------------------------------------------------

output "lambda_function_name" {
  description = "Lambda function name"
  value       = module.lambda.lambda_function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = module.lambda.lambda_function_arn
}

output "lambda_role_name" {
  description = "Lambda IAM role name"
  value       = module.lambda.lambda_role_name
}

output "lambda_role_arn" {
  description = "Lambda IAM role ARN"
  value       = module.lambda.lambda_role_arn
}

output "lambda_layer_arn" {
  description = "Lambda layer ARN with dependencies"
  value       = module.lambda_layer.lambda_layer_arn
}

# -----------------------------------------------------------------------------
# OAuth2 Callback URL (T022)
# -----------------------------------------------------------------------------
# REST API stage invoke_url already includes the stage name, so no need to add /api prefix
# Example: https://abc123.execute-api.eu-west-1.amazonaws.com/api/auth/callback

output "oauth2_callback_url" {
  description = "Full OAuth2 callback URL for Cognito"
  value       = "${aws_api_gateway_stage.main.invoke_url}/auth/callback"
}
