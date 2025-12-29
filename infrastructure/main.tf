# Booking Platform: Agent-First Vacation Rental
# Main Terraform configuration
#
# ⚠️ IMPORTANT: All terraform commands MUST be run via Taskfile.yaml
# Syntax: task tf:<action>:<env>
# Examples: task tf:init:dev, task tf:plan:prod, task tf:apply:dev
#
# Uses cloudposse/label/null for consistent naming. Context is passed
# from root to all child modules following CloudPosse conventions.

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.27"
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }

  # Backend configuration loaded from environments/{env}/backend.hcl
  backend "s3" {}
}

provider "aws" {}

# Provider alias for us-east-1 (required for CloudFront certificates)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

# Provider alias for Cognito (required by AgentCore module)
provider "aws" {
  alias = "cognito"
}

# Data sources for Docker provider authentication
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_ecr_authorization_token" "token" {}

# Docker provider with ECR authentication (required for AgentCore image push)
provider "docker" {
  registry_auth {
    address  = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${data.aws_region.current.id}.amazonaws.com"
    username = data.aws_ecr_authorization_token.token.user_name
    password = data.aws_ecr_authorization_token.token.password
  }
}

# -----------------------------------------------------------------------------
# CloudPosse Label - Root context for all modules
# -----------------------------------------------------------------------------

module "label" {
  source  = "cloudposse/label/null"
  version = "~> 0.25"

  namespace   = "booking"
  environment = var.environment

  # Note: Don't add Environment here - CloudPosse auto-generates from environment variable
  # Adding it manually would cause "duplicate tag keys" errors in child modules
  tags = {
    Project   = "booking"
    ManagedBy = "terraform"
  }
}

locals {
  certificate_arn = var.certificate_arn != "" ? var.certificate_arn : data.aws_acm_certificate.wildcard.arn
  hosted_zone_id  = var.hosted_zone_id != "" ? var.hosted_zone_id : data.aws_route53_zone.main.zone_id
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

# Look up ACM certificate by domain name (must be in us-east-1 for CloudFront)
data "aws_acm_certificate" "wildcard" {
  domain      = var.cert_name
  statuses    = ["ISSUED"]
  most_recent = true
  provider    = aws.us_east_1
}

# Look up Route53 hosted zone by domain name
data "aws_route53_zone" "main" {
  name         = var.cert_name
  private_zone = false
}

# -----------------------------------------------------------------------------
# DynamoDB Tables
# -----------------------------------------------------------------------------

module "dynamodb" {
  source = "./modules/dynamodb"

  # Pass CloudPosse context - module will inherit namespace, environment, tags
  context = module.label.context
}

# -----------------------------------------------------------------------------
# AgentCore Runtime
# -----------------------------------------------------------------------------

module "agentcore" {
  # Note: Terraform requires static source paths - cannot use variables.
  # Update this path to match your local terraform-aws-agentcore module location.
  source = "/Users/levy/code/apro/agentcore-sandbox/terraform-aws-agentcore"

  providers = {
    aws         = aws
    aws.cognito = aws.cognito
  }

  # Pass CloudPosse context - module inherits namespace, environment, tags
  context     = module.label.context
  name        = "agent"
  namespace   = module.label.namespace
  environment = var.environment

  # Use existing Cognito user pool from our passwordless auth module
  existing_user_pool_id        = module.cognito.user_pool_id
  existing_user_pool_client_id = module.cognito.client_id

  # Runtime configuration - single runtime for the booking agent
  runtime = {
    booking = {
      # Docker build configuration
      dockerfile_path = "Dockerfile"
      context_path    = "${path.module}/../backend"
      platform        = "linux/arm64"
      force_delete    = true

      # Runtime settings
      network_mode     = "PUBLIC"
      idle_session_ttl = var.agentcore_idle_session_ttl

      # Environment variables for the agent container
      environment_vars = {
        # Model configuration
        BEDROCK_MODEL_ID = var.bedrock_model_id
        MAX_TOKENS       = tostring(var.agentcore_max_tokens)
        TEMPERATURE      = tostring(var.agentcore_temperature)

        # Application environment - used by DynamoDB service for table names
        ENVIRONMENT = var.environment

        # Logging
        LOG_LEVEL = var.environment == "prod" ? "INFO" : "DEBUG"
      }

      # IAM authorization - Uses SigV4 signing
      # Anonymous users get temporary credentials from Cognito Identity Pool
      # No JWT authorizer = IAM auth via bedrock-agentcore:InvokeAgentRuntime
      # cognito_user_pool_id, cognito_discovery_url, cognito_client_ids intentionally omitted
    }
  }

  # Memory configuration for conversation state (optional)
  memory = var.enable_agentcore_memory ? {
    event_storage = {
      max_events = 100 # Keep last 100 events per session
    }
    strategies = {
      semantic = {
        enabled   = false # Not needed for simple booking conversations
        namespace = "booking-semantic"
      }
      summarization = {
        enabled     = true # Summarize long conversations
        model_id    = var.bedrock_model_id
        max_tokens  = 1024
        temperature = 0.3
      }
      user_preference = {
        enabled = true # Remember user preferences
      }
    }
  } : null

  # Observability (CloudWatch metrics and alarms)
  enable_observability = var.enable_agentcore_observability
  observability_alarms = var.enable_agentcore_observability ? {
    runtime_invocation_errors = {
      threshold = 5
      period    = 300
    }
    runtime_latency = {
      threshold = 10000 # 10 seconds
      period    = 300
    }
  } : null

  # No gateway - frontend calls runtime directly via API Gateway or AppSync
  gateway = null

  # Additional IAM permissions for DynamoDB access
  # The runtime IAM role needs access to our booking tables
  depends_on = [module.dynamodb]
}

# IAM policy for AgentCore Runtime to access DynamoDB booking tables
resource "aws_iam_policy" "agentcore_dynamodb" {
  name        = "${module.label.id}-agentcore-dynamodb"
  description = "Allow AgentCore Runtime to access booking DynamoDB tables"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBTableAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:TransactWriteItems",
          "dynamodb:TransactGetItems"
        ]
        Resource = concat(
          module.dynamodb.table_arns,
          [for arn in module.dynamodb.table_arns : "${arn}/index/*"]
        )
      }
    ]
  })

  tags = module.label.tags
}

# Attach DynamoDB policy to AgentCore Runtime IAM role
resource "aws_iam_role_policy_attachment" "agentcore_dynamodb" {
  role       = module.agentcore.runtime["booking"].role_name
  policy_arn = aws_iam_policy.agentcore_dynamodb.arn
}

# -----------------------------------------------------------------------------
# Cognito Passwordless Authentication
# -----------------------------------------------------------------------------

module "cognito" {
  source = "./modules/cognito-passwordless"

  # Pass CloudPosse context
  context = module.label.context

  # SES Configuration
  ses_from_email = var.ses_from_email

  # Use verification_codes table from DynamoDB module
  verification_table_name = module.dynamodb.verification_codes_table_name
  verification_table_arn  = module.dynamodb.verification_codes_table_arn

  # Verification settings
  code_ttl_seconds = 300 # 5 minutes
  max_attempts     = 3
  code_length      = 6

  # Anonymous user support - shared user for unauthenticated visitors
  anonymous_user_email = var.anonymous_user_email
}


# -----------------------------------------------------------------------------
# Identity Pool IAM Policy for AgentCore Invocation
# -----------------------------------------------------------------------------
# Allows Identity Pool users (both authenticated and unauthenticated) to invoke
# the AgentCore Runtime via SigV4-signed requests.

resource "aws_iam_policy" "identity_pool_agentcore" {
  name        = "${module.label.id}-identity-pool-agentcore"
  description = "Allow Identity Pool users to invoke AgentCore Runtime"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeAgentCoreRuntime"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:InvokeAgentRuntime"
        ]
        # SDK calls target subresources like /runtime-endpoint/DEFAULT
        # Include both base ARN and wildcard for all subresources
        Resource = [
          module.agentcore.runtime["booking"].runtime_arn,
          "${module.agentcore.runtime["booking"].runtime_arn}/*"
        ]
      }
    ]
  })

  tags = module.label.tags
}

# Attach AgentCore policy to unauthenticated Identity Pool role
resource "aws_iam_role_policy_attachment" "identity_pool_unauth_agentcore" {
  role       = module.cognito.unauthenticated_role_name
  policy_arn = aws_iam_policy.identity_pool_agentcore.arn
}

# Attach AgentCore policy to authenticated Identity Pool role
resource "aws_iam_role_policy_attachment" "identity_pool_auth_agentcore" {
  role       = module.cognito.authenticated_role_name
  policy_arn = aws_iam_policy.identity_pool_agentcore.arn
}

# -----------------------------------------------------------------------------
# Static Website (S3 + CloudFront)
# -----------------------------------------------------------------------------

module "static_website" {
  source = "./modules/static-website"

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  # Pass CloudPosse context
  context = module.label.context

  domain_name        = var.domain_name
  certificate_arn    = local.certificate_arn
  hosted_zone_id     = local.hosted_zone_id
  frontend_build_dir = "${path.module}/../frontend/out"

  enable_waf = true
  waf_whitelisted_ips = [
    { ip = "157.157.199.250/32", description = "Hlíð" }
  ]
}
