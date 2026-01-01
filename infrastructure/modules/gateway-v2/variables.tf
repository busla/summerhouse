# Gateway-v2 Module Variables
# FastAPI Lambda + API Gateway HTTP API for OAuth2 callback handling

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
  description = "CloudPosse label context from root module"
}

variable "backend_source_dir" {
  description = "Path to the backend source directory containing FastAPI app"
  type        = string
}

variable "handler" {
  description = "Lambda handler path (module.function)"
  type        = string
  default     = "api.main.handler"
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.13"
}

variable "memory_size" {
  description = "Lambda memory in MB"
  type        = number
  default     = 512
}

variable "timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 30
}

variable "environment_vars" {
  description = "Additional environment variables for the Lambda function"
  type        = map(string)
  default     = {}
}

# DynamoDB configuration for Lambda environment
variable "dynamodb_table_prefix" {
  description = "Prefix for DynamoDB table names (e.g., 'booking-dev-data')"
  type        = string
}

variable "oauth2_sessions_table_name" {
  description = "Name of the DynamoDB table for OAuth2 sessions"
  type        = string
}

variable "oauth2_sessions_table_arn" {
  description = "ARN of the DynamoDB table for OAuth2 sessions"
  type        = string
}

# Additional DynamoDB tables for API routes
variable "dynamodb_table_arns" {
  description = "List of DynamoDB table ARNs for API routes (reservations, guests, availability, etc.)"
  type        = list(string)
  default     = []
}

# Cognito configuration
variable "cognito_user_pool_id" {
  description = "Cognito User Pool ID for authentication"
  type        = string
}

variable "cognito_client_id" {
  description = "Cognito User Pool Client ID"
  type        = string
}

# Frontend URL for OAuth2 redirects
variable "frontend_url" {
  description = "Frontend URL for redirecting after OAuth2 callback"
  type        = string
}

# CORS configuration
variable "cors_allow_origins" {
  description = "Allowed CORS origins for API Gateway (passed to OpenAPI generation)"
  type        = list(string)
  default     = ["*"]
}

# OpenAPI generation configuration
variable "enable_openapi_generation" {
  description = "Enable OpenAPI-based API Gateway provisioning (vs catch-all routing)"
  type        = bool
  default     = true
}

# REST API stage name
variable "stage_name" {
  description = "REST API stage name (CloudFront origin path abstracts this from end users)"
  type        = string
  default     = "api"

  validation {
    condition     = can(regex("^[a-zA-Z0-9_]+$", var.stage_name))
    error_message = "Stage name must contain only alphanumeric characters and underscores."
  }
}
