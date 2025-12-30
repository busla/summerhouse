# Gateway-v2 Module Outputs

output "api_gateway_url" {
  description = "API Gateway invoke URL"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "api_gateway_id" {
  description = "API Gateway ID"
  value       = aws_apigatewayv2_api.main.id
}

output "api_gateway_arn" {
  description = "API Gateway execution ARN"
  value       = aws_apigatewayv2_api.main.execution_arn
}

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

# OAuth2 callback URL (for Cognito configuration)
output "oauth2_callback_url" {
  description = "Full OAuth2 callback URL for Cognito"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/api/auth/callback"
}
