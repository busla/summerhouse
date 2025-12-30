# Summerhouse Infrastructure Variables

variable "environment" {
  description = "Deployment environment (dev, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be 'dev' or 'prod'."
  }
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "bedrock_model_id" {
  description = "Amazon Bedrock model ID for the agent"
  type        = string
  default     = "anthropic.claude-sonnet-4-20250514"
}

variable "domain_name" {
  description = "Domain name for the frontend (optional, uses CloudFront default if not set)"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN for custom domain (required if domain_name is set)"
  type        = string
  default     = ""
}

variable "cert_name" {
  description = "Domain name of the ACM certificate and Route53 hosted zone (e.g., 'example.com')"
  type        = string
}

variable "hosted_zone_id" {
  description = "Route53 hosted zone ID for DNS records (required for custom domain)"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# AgentCore Configuration
# -----------------------------------------------------------------------------

variable "agentcore_idle_session_ttl" {
  description = "Idle session TTL in seconds for AgentCore Runtime"
  type        = number
  default     = 3600
}

variable "agentcore_max_tokens" {
  description = "Maximum tokens for agent responses"
  type        = number
  default     = 4096
}

variable "agentcore_temperature" {
  description = "Model temperature for agent responses"
  type        = number
  default     = 0.7
}

variable "enable_agentcore_memory" {
  description = "Whether to enable AgentCore Memory for conversation state"
  type        = bool
  default     = true
}

variable "enable_agentcore_observability" {
  description = "Whether to enable AgentCore observability (CloudWatch metrics/alarms)"
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# Cognito Authentication Configuration
# -----------------------------------------------------------------------------

variable "cognito_user_pool_tier" {
  description = <<-EOT
    Cognito User Pool tier. Set to "ESSENTIALS" to enable native EMAIL_OTP auth.
    Options: "LITE" (free), "ESSENTIALS" (paid, required for EMAIL_OTP), "PLUS" (enterprise)
  EOT
  type        = string
  default     = "LITE"
}

variable "enable_cognito_email_otp" {
  description = <<-EOT
    Enable native Cognito USER_AUTH flow with EMAIL_OTP (requires ESSENTIALS tier).
    When enabled, Cognito handles OTP generation and email delivery natively.
  EOT
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# SES Email Configuration for Cognito
# -----------------------------------------------------------------------------

variable "ses_email_identity" {
  description = <<-EOT
    SES verified identity (domain or email) for Cognito to send emails.
    Examples: "example.com" (domain) or "noreply@example.com" (email).
    If empty, Cognito uses its default email service (limited to 50/day).
  EOT
  type        = string
  default     = ""
}

variable "ses_from_email" {
  description = <<-EOT
    The FROM email address for Cognito emails when using SES.
    Must be within the verified SES identity domain.
    If empty but ses_email_identity is set, uses "no-reply@{ses_email_identity}".
  EOT
  type        = string
  default     = ""
}

