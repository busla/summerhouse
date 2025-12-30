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

  # AgentCore OAuth2 provider name - constructed to match terraform-aws-agentcore internal naming
  # Format: {namespace}-{environment}-{agent-name}-identity-{provider-key}
  # This avoids a dependency cycle from referencing module.agentcore.identity.oauth2_provider_names
  agentcore_oauth2_provider_name = var.enable_agentcore_oauth2 ? "${module.label.id}-agent-identity-cognito" : ""
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
# S3 Bucket for Agent Session Storage (Strands S3SessionManager)
# -----------------------------------------------------------------------------
# Stores conversation history for multi-turn agent conversations.
# Each session_id from the frontend maps to a unique conversation state in S3.
# Must be defined before AgentCore module since it references the bucket name.

module "agent_sessions_bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "~> 4.1"

  bucket = "${module.label.id}-agent-sessions"

  # Block all public access
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  # Enable versioning for recovery
  versioning = {
    enabled = true
  }

  # Server-side encryption with S3-managed keys
  server_side_encryption_configuration = {
    rule = {
      apply_server_side_encryption_by_default = {
        sse_algorithm = "AES256"
      }
    }
  }

  # Lifecycle rule to clean up old sessions (sessions older than 30 days)
  lifecycle_rule = [
    {
      id      = "cleanup-old-sessions"
      enabled = true

      filter = {
        prefix = "agent-sessions/"
      }

      expiration = {
        days = 30
      }

      # Clean up incomplete multipart uploads
      abort_incomplete_multipart_upload_days = 1
    }
  ]

  # Force destroy for easier cleanup in dev environments
  force_destroy = var.environment == "dev"

  tags = module.label.tags
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

        # AWS region for boto3 clients (DynamoDB, S3, etc.)
        # AgentCore doesn't inject AWS_REGION like Lambda, so we must set it explicitly
        AWS_DEFAULT_REGION = data.aws_region.current.name

        # DynamoDB table prefix - matches CloudPosse label pattern from dynamodb module
        # Format: namespace-environment-name (where name = "data" in dynamodb module)
        DYNAMODB_TABLE_PREFIX = module.dynamodb.table_prefix

        # Session management - S3 bucket for conversation history persistence
        # Used by Strands S3SessionManager in agent_app.py
        SESSION_BUCKET = module.agent_sessions_bucket.s3_bucket_id
        SESSION_PREFIX = "agent-sessions/"

        # Logging
        LOG_LEVEL = var.environment == "prod" ? "INFO" : "DEBUG"

        # Cognito configuration for EMAIL_OTP authentication
        # Used by auth tools (initiate_cognito_login, verify_cognito_otp)
        COGNITO_USER_POOL_ID = module.cognito.user_pool_id
        COGNITO_CLIENT_ID    = module.cognito.client_id

        # AgentCore Identity OAuth2 configuration
        # Used by @requires_access_token decorator on booking tools
        # These enable the OAuth2 3LO flow when unauthenticated users try to book
        AGENTCORE_OAUTH2_PROVIDER_NAME = local.agentcore_oauth2_provider_name
        AGENTCORE_OAUTH2_CALLBACK_URL  = var.enable_agentcore_oauth2 ? module.gateway_v2.oauth2_callback_url : ""
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

  # Identity configuration for OAuth2 authentication
  # Enables @requires_access_token decorator on agent tools
  identity = var.enable_agentcore_oauth2 ? {
    # OAuth2 Credential Provider for Cognito integration
    # This creates an AgentCore OAuth2 Credential Provider that points to our Cognito User Pool
    # Note: After first apply, the callback URL is generated by AWS and must be
    # configured in Cognito User Pool Client's callback_urls
    oauth2_providers = {
      cognito = {
        vendor        = "CustomOauth2"
        client_id     = module.cognito.agentcore_client_id
        client_secret = module.cognito.agentcore_client_secret
        discovery_url = module.cognito.discovery_url
      }
    }

    # Workload provider for agent-to-user OAuth2 flows
    # The oauth2_return_urls is where AgentCore redirects after completing OAuth2 code exchange
    workload_providers = [
      {
        name               = "cognito"
        oauth2_return_urls = [module.gateway_v2.oauth2_callback_url]
      }
    ]
  } : null

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

# IAM policy for AgentCore Runtime to access session storage bucket
resource "aws_iam_policy" "agentcore_sessions_s3" {
  name        = "${module.label.id}-agentcore-sessions-s3"
  description = "Allow AgentCore Runtime to read/write session data to S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3SessionBucketAccess"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject"
        ]
        Resource = "${module.agent_sessions_bucket.s3_bucket_arn}/*"
      },
      {
        Sid    = "S3SessionBucketList"
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = module.agent_sessions_bucket.s3_bucket_arn
      }
    ]
  })

  tags = module.label.tags
}

# Attach S3 session policy to AgentCore Runtime IAM role
resource "aws_iam_role_policy_attachment" "agentcore_sessions_s3" {
  role       = module.agentcore.runtime["booking"].role_name
  policy_arn = aws_iam_policy.agentcore_sessions_s3.arn
}

# IAM policy for AgentCore Runtime to manage Cognito users for passwordless auth
# Required for auto-creating users when they don't exist (admin_create_user)
resource "aws_iam_policy" "agentcore_cognito" {
  name        = "${module.label.id}-agentcore-cognito"
  description = "Allow AgentCore Runtime to manage Cognito users for passwordless authentication"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CognitoAdminUserManagement"
        Effect = "Allow"
        Action = [
          "cognito-idp:AdminCreateUser",
          "cognito-idp:AdminGetUser",
          "cognito-idp:AdminUpdateUserAttributes"
        ]
        Resource = module.cognito.user_pool_arn
      }
    ]
  })

  tags = module.label.tags
}

# Attach Cognito policy to AgentCore Runtime IAM role
resource "aws_iam_role_policy_attachment" "agentcore_cognito" {
  role       = module.agentcore.runtime["booking"].role_name
  policy_arn = aws_iam_policy.agentcore_cognito.arn
}

# -----------------------------------------------------------------------------
# Cognito Passwordless Authentication
# -----------------------------------------------------------------------------

module "cognito" {
  source = "./modules/cognito-passwordless"

  # Pass CloudPosse context
  context = module.label.context

  # Cognito tier and native EMAIL_OTP configuration
  # Set user_pool_tier = "ESSENTIALS" and enable_user_auth_email_otp = true
  # to use Cognito's native USER_AUTH flow with EMAIL_OTP
  # Note: Native EMAIL_OTP eliminates need for custom Lambda triggers
  user_pool_tier             = var.cognito_user_pool_tier
  enable_user_auth_email_otp = var.enable_cognito_email_otp

  # SES email configuration (optional)
  # When set, Cognito uses your SES identity instead of default email service
  ses_email_identity = var.ses_email_identity
  ses_from_email     = var.ses_from_email

  # AgentCore OAuth2 callback URL (for confidential client)
  # Set this after first deploy to complete OAuth2 setup
  agentcore_callback_urls = var.agentcore_oauth2_callback_url != "" ? [var.agentcore_oauth2_callback_url] : (
    # Auto-configure if enable_agentcore_oauth2 is true (creates client without callback initially)
    var.enable_agentcore_oauth2 ? ["https://placeholder.invalid/oauth2/callback"] : []
  )

  # Frontend callback URLs for Amplify Auth
  frontend_callback_urls = var.frontend_auth_callback_url != "" ? [
    var.frontend_auth_callback_url,
    "http://localhost:3000/auth/callback" # Dev environment
  ] : []
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

  # API Gateway origin for /api/* routes (unified domain for frontend + API)
  api_gateway_url = module.gateway_v2.api_gateway_url
}

# -----------------------------------------------------------------------------
# Gateway-v2: FastAPI Lambda + API Gateway HTTP API
# -----------------------------------------------------------------------------
# Provides OAuth2 callback endpoint for AgentCore Identity flows

module "gateway_v2" {
  source = "./modules/gateway-v2"

  # Pass CloudPosse context
  context = module.label.context

  # Backend source for Lambda build
  backend_source_dir = "${path.module}/../backend"

  # DynamoDB OAuth2 sessions table (for session_id → guest_email correlation)
  oauth2_sessions_table_name = module.dynamodb.oauth2_sessions_table_name
  oauth2_sessions_table_arn  = module.dynamodb.oauth2_sessions_table_arn

  # Cognito configuration (for JWT validation in callback)
  cognito_user_pool_id = module.cognito.user_pool_id
  cognito_client_id    = module.cognito.client_id

  # Frontend URL for post-auth redirect
  frontend_url = module.static_website.website_url
}
