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
