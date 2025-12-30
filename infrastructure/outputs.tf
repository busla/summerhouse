# Summerhouse Infrastructure Outputs

# DynamoDB Table Outputs
output "dynamodb_reservations_table_name" {
  description = "Name of the reservations DynamoDB table"
  value       = module.dynamodb.reservations_table_name
}

output "dynamodb_guests_table_name" {
  description = "Name of the guests DynamoDB table"
  value       = module.dynamodb.guests_table_name
}

output "dynamodb_availability_table_name" {
  description = "Name of the availability DynamoDB table"
  value       = module.dynamodb.availability_table_name
}

output "dynamodb_pricing_table_name" {
  description = "Name of the pricing DynamoDB table"
  value       = module.dynamodb.pricing_table_name
}

output "dynamodb_payments_table_name" {
  description = "Name of the payments DynamoDB table"
  value       = module.dynamodb.payments_table_name
}

output "dynamodb_verification_codes_table_name" {
  description = "Name of the verification codes DynamoDB table"
  value       = module.dynamodb.verification_codes_table_name
}

# Cognito Outputs
output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = module.cognito.user_pool_id
}

output "cognito_user_pool_arn" {
  description = "Cognito User Pool ARN"
  value       = module.cognito.user_pool_arn
}

output "cognito_client_id" {
  description = "Cognito User Pool Client ID"
  value       = module.cognito.client_id
}

output "cognito_issuer_url" {
  description = "JWT issuer URL for token validation"
  value       = module.cognito.issuer_url
}

output "cognito_identity_pool_id" {
  description = "Cognito Identity Pool ID for IAM-based auth"
  value       = module.cognito.identity_pool_id
}

output "cognito_identity_pool_arn" {
  description = "Cognito Identity Pool ARN"
  value       = module.cognito.identity_pool_arn
}

output "cognito_unauthenticated_role_arn" {
  description = "IAM Role ARN for unauthenticated Identity Pool users"
  value       = module.cognito.unauthenticated_role_arn
}

# AgentCore Outputs
output "agentcore_runtime_id" {
  description = "AgentCore Runtime ID"
  value       = module.agentcore.runtime["booking"].runtime_id
}

output "agentcore_runtime_arn" {
  description = "AgentCore Runtime ARN"
  value       = module.agentcore.runtime["booking"].runtime_arn
}

output "agentcore_custom_endpoints" {
  description = "AgentCore Runtime custom endpoints"
  value       = module.agentcore.runtime["booking"].custom_endpoints
}

output "agentcore_memory_id" {
  description = "AgentCore Memory ID (if enabled)"
  value       = var.enable_agentcore_memory ? module.agentcore.memory.memory_id : null
}

# Static Website Outputs
output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = module.static_website.cloudfront_distribution_id
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name"
  value       = module.static_website.cloudfront_domain_name
}

output "website_url" {
  description = "Full URL of the website"
  value       = module.static_website.website_url
}

output "s3_bucket_name" {
  description = "S3 bucket name for frontend assets"
  value       = module.static_website.bucket_name
}

output "frontend_deploy_command" {
  description = "Command to deploy frontend to S3"
  value       = module.static_website.deploy_command
}

# Gateway-v2 Outputs (OAuth2 callback API)
output "api_gateway_url" {
  description = "API Gateway invoke URL for OAuth2 callbacks"
  value       = module.gateway_v2.api_gateway_url
}

output "oauth2_callback_url" {
  description = "Full OAuth2 callback URL for AgentCore Identity configuration"
  value       = module.gateway_v2.oauth2_callback_url
}

output "api_lambda_function_name" {
  description = "Lambda function name for API Gateway"
  value       = module.gateway_v2.lambda_function_name
}

# AgentCore Identity Outputs
output "agentcore_workload_identity_names" {
  description = "Workload identity provider names for AgentCore"
  value       = try(module.agentcore.identity.workload_identity_names, {})
}
