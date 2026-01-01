# Cognito Passwordless Module - Outputs
# Outputs for native USER_AUTH with EMAIL_OTP configuration

# -----------------------------------------------------------------------------
# User Pool Outputs
# -----------------------------------------------------------------------------

output "user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.main.id
}

output "user_pool_arn" {
  description = "Cognito User Pool ARN"
  value       = aws_cognito_user_pool.main.arn
}

output "user_pool_endpoint" {
  description = "Cognito User Pool endpoint"
  value       = aws_cognito_user_pool.main.endpoint
}

output "client_id" {
  description = "Cognito User Pool Client ID (public client for frontend)"
  value       = aws_cognito_user_pool_client.main.id
}

output "agentcore_client_id" {
  description = "Cognito User Pool Client ID (confidential client for AgentCore OAuth2)"
  value       = length(aws_cognito_user_pool_client.agentcore) > 0 ? aws_cognito_user_pool_client.agentcore[0].id : null
}

output "agentcore_client_secret" {
  description = "Cognito User Pool Client Secret (confidential client for AgentCore OAuth2)"
  value       = length(aws_cognito_user_pool_client.agentcore) > 0 ? aws_cognito_user_pool_client.agentcore[0].client_secret : null
  sensitive   = true
}

output "discovery_url" {
  description = "OpenID Connect discovery URL for JWT validation"
  value       = "https://cognito-idp.${data.aws_region.current.id}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/openid-configuration"
}

output "issuer_url" {
  description = "JWT issuer URL"
  value       = "https://cognito-idp.${data.aws_region.current.id}.amazonaws.com/${aws_cognito_user_pool.main.id}"
}

# -----------------------------------------------------------------------------
# Identity Pool Outputs (for IAM-based auth)
# -----------------------------------------------------------------------------

output "identity_pool_id" {
  description = "Cognito Identity Pool ID"
  value       = aws_cognito_identity_pool.main.id
}

output "identity_pool_arn" {
  description = "Cognito Identity Pool ARN"
  value       = aws_cognito_identity_pool.main.arn
}

output "unauthenticated_role_arn" {
  description = "IAM Role ARN for unauthenticated Identity Pool users"
  value       = aws_iam_role.unauthenticated.arn
}

output "unauthenticated_role_name" {
  description = "IAM Role name for unauthenticated Identity Pool users"
  value       = aws_iam_role.unauthenticated.name
}

output "authenticated_role_arn" {
  description = "IAM Role ARN for authenticated Identity Pool users"
  value       = aws_iam_role.authenticated.arn
}

output "authenticated_role_name" {
  description = "IAM Role name for authenticated Identity Pool users"
  value       = aws_iam_role.authenticated.name
}

# -----------------------------------------------------------------------------
# User Pool Domain Outputs (required for OAuth2 flows)
# -----------------------------------------------------------------------------

output "user_pool_domain" {
  description = "Cognito User Pool domain prefix"
  value       = aws_cognito_user_pool_domain.main.domain
}

output "user_pool_domain_url" {
  description = "Cognito User Pool full domain URL for OAuth2 flows"
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${data.aws_region.current.id}.amazoncognito.com"
}
