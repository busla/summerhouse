# OTP Interceptor Module - Variables

# -----------------------------------------------------------------------------
# CloudPosse Context
# -----------------------------------------------------------------------------

variable "context" {
  type        = any
  description = "CloudPosse label context for consistent naming"
  default = {
    enabled             = true
    namespace           = "booking"
    environment         = "dev"
    stage               = null
    name                = null
    delimiter           = "-"
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
}

# -----------------------------------------------------------------------------
# Lambda Configuration
# -----------------------------------------------------------------------------

variable "lambda_source_path" {
  type        = string
  description = "Path to the Lambda source code directory"
}

variable "runtime" {
  type        = string
  description = "Lambda runtime (python3.12 required for SAM build image compatibility)"
  default     = "python3.12"
}

variable "memory_size" {
  type        = number
  description = "Lambda memory size in MB"
  default     = 128
}

variable "timeout" {
  type        = number
  description = "Lambda timeout in seconds"
  default     = 10
}

# -----------------------------------------------------------------------------
# DynamoDB Configuration
# -----------------------------------------------------------------------------

variable "verification_codes_table_name" {
  type        = string
  description = "Name of the DynamoDB table for verification codes"
}

variable "verification_codes_table_arn" {
  type        = string
  description = "ARN of the DynamoDB table for verification codes"
}

# -----------------------------------------------------------------------------
# Cognito Configuration
# -----------------------------------------------------------------------------

variable "cognito_user_pool_arn" {
  type        = string
  description = "ARN of the Cognito User Pool to receive triggers from. If null, Lambda permission is not created (create it externally to break dependency cycles)."
  default     = null
}

# -----------------------------------------------------------------------------
# SES Email Configuration
# -----------------------------------------------------------------------------
# Custom Email Sender takes over ALL email delivery from Cognito.
# We must send emails ourselves via SES.

variable "ses_from_email" {
  type        = string
  description = "FROM email address for sending OTP emails via SES (e.g., 'no-reply@example.com')"
}

variable "ses_identity" {
  type        = string
  description = "SES verified identity (domain or email) used for sending. Used to construct the SES ARN for IAM permissions."
}
