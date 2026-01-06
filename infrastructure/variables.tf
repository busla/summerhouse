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

variable "enable_cognito_password_auth" {
  description = <<-EOT
    Enable USER_PASSWORD_AUTH flow for E2E test automation.
    When enabled, test users can authenticate with username/password via
    InitiateAuth with AuthFlow=USER_PASSWORD_AUTH.

    This allows E2E tests to run without intercepting EMAIL_OTP codes.
    Real users continue using EMAIL_OTP; test users use passwords.
  EOT
  type        = bool
  default     = false
}

variable "enable_otp_interceptor" {
  description = <<-EOT
    Enable OTP Interceptor Lambda for E2E test automation.
    When enabled, deploys a Lambda that intercepts Cognito EMAIL_OTP codes
    for test email patterns (test+*@summerhouse.com) and stores them in
    DynamoDB for E2E test retrieval.

    This allows E2E tests to programmatically verify OTP codes without
    needing access to email inboxes.

    Security: Only intercepts codes in dev environment for test email patterns.
    Should only be enabled in dev environments.
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

# -----------------------------------------------------------------------------
# AgentCore Identity OAuth2 Configuration
# -----------------------------------------------------------------------------

variable "enable_agentcore_oauth2" {
  description = <<-EOT
    Enable AgentCore Identity OAuth2 integration with Cognito.
    When enabled:
    - Creates a confidential Cognito User Pool Client (with client_secret)
    - Creates an OAuth2 Credential Provider in AgentCore pointing to Cognito
    - Enables @requires_access_token decorator on agent tools

    Requires a two-phase deployment:
    1. First apply creates the OAuth2 Credential Provider
    2. AWS generates the callback URL
    3. Second apply (or manual) configures Cognito with the callback URL

    Set agentcore_oauth2_callback_url after first apply to complete setup.
  EOT
  type        = bool
  default     = false
}

variable "agentcore_oauth2_callback_url" {
  description = <<-EOT
    AgentCore Identity OAuth2 callback URL. This URL is generated by AWS after
    the OAuth2 Credential Provider is created.

    After the first terraform apply with enable_agentcore_oauth2 = true:
    1. Get the callback URL from module.agentcore.identity.oauth2_provider_callback_urls["cognito"]
    2. Set this variable to that URL
    3. Run terraform apply again to configure Cognito with the callback URL

    Example: "https://bedrock-agentcore.eu-west-1.amazonaws.com/oauth2/callback/abc123"
  EOT
  type        = string
  default     = ""
}

variable "frontend_auth_callback_url" {
  description = <<-EOT
    Frontend authentication callback URL for Amplify Auth.
    This is where Amplify Auth redirects after successful Cognito authentication.

    For static sites, this is typically: "https://{domain}/auth/callback"
  EOT
  type        = string
  default     = ""
}

