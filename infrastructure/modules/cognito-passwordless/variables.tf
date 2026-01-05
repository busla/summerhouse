# Cognito Passwordless Module - Variables
# Uses cloudposse/label/null context pattern - receives context from root module
#
# Simplified for native USER_AUTH with EMAIL_OTP (no Lambda triggers)

variable "context" {
  type = any
  default = {
    enabled             = true
    namespace           = null
    tenant              = null
    environment         = null
    stage               = null
    name                = null
    delimiter           = null
    attributes          = []
    tags                = {}
    additional_tag_map  = {}
    regex_replace_chars = null
    label_order         = []
    id_length_limit     = null
    label_key_case      = null
    label_value_case    = null
    descriptor_formats  = {}
    labels_as_tags      = ["unset"]
  }
  description = <<-EOT
    Single object for setting entire context at once.
    See description of individual variables for details.
    Leave string and numeric variables as `null` to use default value.
    Individual variable settings (non-null) override settings in context object,
    except for attributes, tags, and additional_tag_map, which are merged.
  EOT

  validation {
    condition     = lookup(var.context, "label_key_case", null) == null ? true : contains(["lower", "title", "upper"], var.context["label_key_case"])
    error_message = "Allowed values: `lower`, `title`, `upper`."
  }

  validation {
    condition     = lookup(var.context, "label_value_case", null) == null ? true : contains(["lower", "title", "upper", "none"], var.context["label_value_case"])
    error_message = "Allowed values: `lower`, `title`, `upper`, `none`."
  }
}

# -----------------------------------------------------------------------------
# Cognito Tier and Auth Configuration
# -----------------------------------------------------------------------------

variable "user_pool_tier" {
  description = <<-EOT
    Cognito User Pool tier. Options:
    - "LITE": Free tier with limited features (default)
    - "ESSENTIALS": Paid tier required for native EMAIL_OTP auth
    - "PLUS": Enterprise tier with advanced security

    Set to "ESSENTIALS" to enable native USER_AUTH with EMAIL_OTP.
  EOT
  type        = string
  default     = "LITE"

  validation {
    condition     = contains(["LITE", "ESSENTIALS", "PLUS"], var.user_pool_tier)
    error_message = "user_pool_tier must be LITE, ESSENTIALS, or PLUS"
  }
}

variable "enable_user_auth_email_otp" {
  description = <<-EOT
    Enable native Cognito USER_AUTH flow with EMAIL_OTP.
    Requires user_pool_tier = "ESSENTIALS" or higher.

    When enabled:
    - Adds USER_AUTH to explicit_auth_flows
    - Configures AllowedFirstAuthFactors = ["EMAIL_OTP"]
    - Cognito handles OTP generation and email delivery natively
  EOT
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# SES Email Configuration
# -----------------------------------------------------------------------------

variable "ses_email_identity" {
  description = <<-EOT
    SES email identity (verified email or domain) for sending Cognito emails.
    Examples:
    - "noreply@example.com" (verified email)
    - "example.com" (verified domain - sends from no-reply@example.com)

    If not set, Cognito uses its default email service (limited to 50 emails/day).
  EOT
  type        = string
  default     = ""
}

variable "ses_from_email" {
  description = <<-EOT
    The FROM email address for Cognito emails when using SES.
    Must be within the verified SES identity domain.
    Example: "noreply@example.com"

    If not set but ses_email_identity is set, uses "no-reply@{ses_email_identity}".
  EOT
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# AgentCore OAuth2 Integration
# -----------------------------------------------------------------------------

variable "agentcore_callback_urls" {
  description = <<-EOT
    Callback URLs for AgentCore OAuth2 integration. These are the URLs that
    AgentCore Identity will redirect to after OAuth2 authorization.

    When set, creates a confidential Cognito User Pool Client (with client_secret)
    for AgentCore to use as an OAuth2 credential provider.

    Example: ["https://bedrock-agentcore.eu-west-1.amazonaws.com/oauth2/callback/abc123"]
  EOT
  type        = list(string)
  default     = []
}

variable "frontend_callback_urls" {
  description = <<-EOT
    Callback URLs for frontend Amplify OAuth2 integration. These are where
    Amplify Auth redirects after Cognito authentication completes.

    Example: ["https://myapp.example.com/auth/callback"]
  EOT
  type        = list(string)
  default     = []
}

# -----------------------------------------------------------------------------
# Test Automation Support
# -----------------------------------------------------------------------------

variable "enable_user_password_auth" {
  description = <<-EOT
    Enable USER_PASSWORD_AUTH flow for test automation.

    When enabled, adds ALLOW_USER_PASSWORD_AUTH to the app client's explicit_auth_flows.
    This allows test users to authenticate with username/password via InitiateAuth
    with AuthFlow=USER_PASSWORD_AUTH, bypassing the EMAIL_OTP flow.

    Use case: E2E tests can create users with AdminSetUserPassword and authenticate
    programmatically without needing to intercept OTP emails.

    Note: This does NOT disable EMAIL_OTP - both auth methods work simultaneously.
    Real users continue using EMAIL_OTP while test users can use passwords.
  EOT
  type        = bool
  default     = false
}
