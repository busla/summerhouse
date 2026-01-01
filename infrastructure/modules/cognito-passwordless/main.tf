# Cognito Passwordless Module - Main Resources
# Implements passwordless email verification using Cognito native EMAIL_OTP
#
# Flow (Native USER_AUTH with EMAIL_OTP):
# 1. Backend calls admin_create_user (if user doesn't exist) with email_verified=true
# 2. Backend calls initiate_auth with USER_AUTH flow, PREFERRED_CHALLENGE=EMAIL_OTP
# 3. Cognito sends OTP to user's email natively (no Lambda triggers needed)
# 4. User enters code -> Backend calls respond_to_auth_challenge
# 5. Cognito validates code and returns tokens
#
# Pattern: Single label module with context from root
# Requires: ESSENTIALS tier User Pool for native EMAIL_OTP

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# -----------------------------------------------------------------------------
# CloudPosse Label - inherits context from root, sets component name
# -----------------------------------------------------------------------------

module "label" {
  source  = "cloudposse/label/null"
  version = "~> 0.25"

  # Inherit namespace, environment, tags from root context
  context = var.context

  # Component name for this module
  name = "auth"
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# Cognito User Pool
# -----------------------------------------------------------------------------

resource "aws_cognito_user_pool" "main" {
  name = "${module.label.id}-users"

  # Use email as username
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # User Pool Tier - ESSENTIALS required for native EMAIL_OTP
  user_pool_tier = var.user_pool_tier

  # Sign-in policy for native EMAIL_OTP (requires ESSENTIALS tier)
  # Note: PASSWORD must always be included per Cognito requirements
  dynamic "sign_in_policy" {
    for_each = var.enable_user_auth_email_otp ? [1] : []
    content {
      allowed_first_auth_factors = ["PASSWORD", "EMAIL_OTP"]
    }
  }

  # Password policy (minimal since we use passwordless)
  password_policy {
    minimum_length                   = 8
    require_lowercase                = false
    require_numbers                  = false
    require_symbols                  = false
    require_uppercase                = false
    temporary_password_validity_days = 7
  }

  # Schema - email is standard, add custom attributes as needed
  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true
    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }

  # No Lambda triggers - native EMAIL_OTP handles everything
  # Users are created via admin_create_user with email_verified=true

  # Account recovery via email
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # Email configuration - use SES if configured, otherwise Cognito default
  dynamic "email_configuration" {
    for_each = var.ses_email_identity != "" ? [1] : []
    content {
      email_sending_account  = "DEVELOPER"
      source_arn             = "arn:aws:ses:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:identity/${var.ses_email_identity}"
      from_email_address     = var.ses_from_email != "" ? var.ses_from_email : "no-reply@${var.ses_email_identity}"
      reply_to_email_address = var.ses_from_email != "" ? var.ses_from_email : "no-reply@${var.ses_email_identity}"
    }
  }

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# SES Identity Policy for Cognito
# -----------------------------------------------------------------------------
# When using EmailSendingAccount = "DEVELOPER", SES requires an explicit
# identity policy granting Cognito permission to send emails.

resource "aws_ses_identity_policy" "cognito_sending" {
  count = var.ses_email_identity != "" ? 1 : 0

  identity = var.ses_email_identity
  name     = "${module.label.id}-cognito-sending"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCognitoToSendEmails"
        Effect = "Allow"
        Principal = {
          Service = "cognito-idp.amazonaws.com"
        }
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = "arn:aws:ses:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:identity/${var.ses_email_identity}"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
          ArnLike = {
            "aws:SourceArn" = aws_cognito_user_pool.main.arn
          }
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Cognito User Pool Client (Public - Frontend/Amplify)
# -----------------------------------------------------------------------------
# Public client for frontend use with Amplify Auth.
# No client secret - suitable for browser-based authentication.

resource "aws_cognito_user_pool_client" "main" {
  name         = "${module.label.id}-client"
  user_pool_id = aws_cognito_user_pool.main.id

  # Auth flows - USER_AUTH enables native EMAIL_OTP
  # ALLOW_ADMIN_USER_PASSWORD_AUTH for backend admin_create_user
  explicit_auth_flows = [
    "ALLOW_USER_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  # Token validity
  access_token_validity  = 1  # hours
  id_token_validity      = 1  # hours
  refresh_token_validity = 30 # days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # OAuth2 settings for Amplify-based authentication (when callback URLs are provided)
  callback_urls                = length(var.frontend_callback_urls) > 0 ? var.frontend_callback_urls : null
  logout_urls                  = length(var.frontend_callback_urls) > 0 ? var.frontend_callback_urls : null
  allowed_oauth_flows          = length(var.frontend_callback_urls) > 0 ? ["code"] : null
  allowed_oauth_scopes         = length(var.frontend_callback_urls) > 0 ? ["openid", "email", "profile"] : null
  allowed_oauth_flows_user_pool_client = length(var.frontend_callback_urls) > 0 ? true : false
  supported_identity_providers = length(var.frontend_callback_urls) > 0 ? ["COGNITO"] : null

  # Security
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true

  # No client secret for public client (frontend)
  generate_secret = false
}

# -----------------------------------------------------------------------------
# Cognito User Pool Client (Confidential - AgentCore OAuth2)
# -----------------------------------------------------------------------------
# Confidential client for AgentCore OAuth2 Credential Provider.
# Has client secret - required for server-side OAuth2 flows.
# Created only when agentcore_callback_urls is provided.

resource "aws_cognito_user_pool_client" "agentcore" {
  count = length(var.agentcore_callback_urls) > 0 ? 1 : 0

  name         = "${module.label.id}-agentcore"
  user_pool_id = aws_cognito_user_pool.main.id

  # Auth flows for OAuth2 authorization code flow
  explicit_auth_flows = [
    "ALLOW_USER_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  # Token validity - longer for server-side use
  access_token_validity  = 1   # hours
  id_token_validity      = 1   # hours
  refresh_token_validity = 30  # days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # OAuth2 settings for AgentCore integration
  callback_urls                        = var.agentcore_callback_urls
  logout_urls                          = var.agentcore_callback_urls
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  allowed_oauth_flows_user_pool_client = true
  supported_identity_providers         = ["COGNITO"]

  # Security
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true

  # Generate client secret for confidential client (required by AgentCore)
  generate_secret = true
}

# -----------------------------------------------------------------------------
# Cognito Identity Pool (for IAM-based auth)
# -----------------------------------------------------------------------------
# Provides temporary AWS credentials to anonymous users for SigV4 signing.
# This enables direct invocation of AgentCore via IAM authentication.
#
# Flow:
# 1. Frontend calls Cognito Identity to get credentials (no login required)
# 2. Frontend uses credentials to sign HTTP requests with SigV4
# 3. AgentCore validates IAM signature
# 4. Request proceeds to agent

resource "aws_cognito_identity_pool" "main" {
  identity_pool_name               = "${module.label.id}-identity"
  allow_unauthenticated_identities = true
  allow_classic_flow               = true # Required for full IAM role permissions (no session policy restrictions)

  # Link to User Pool for authenticated users (future use)
  cognito_identity_providers {
    client_id               = aws_cognito_user_pool_client.main.id
    provider_name           = aws_cognito_user_pool.main.endpoint
    server_side_token_check = false
  }

  tags = module.label.tags
}

# IAM role for unauthenticated (anonymous) users
resource "aws_iam_role" "unauthenticated" {
  name = "${module.label.id}-identity-unauth"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "cognito-identity.amazonaws.com"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "cognito-identity.amazonaws.com:aud" = aws_cognito_identity_pool.main.id
          }
          "ForAnyValue:StringLike" = {
            "cognito-identity.amazonaws.com:amr" = "unauthenticated"
          }
        }
      }
    ]
  })

  tags = module.label.tags
}

# IAM role for authenticated users (stubbed for future use)
resource "aws_iam_role" "authenticated" {
  name = "${module.label.id}-identity-auth"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "cognito-identity.amazonaws.com"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "cognito-identity.amazonaws.com:aud" = aws_cognito_identity_pool.main.id
          }
          "ForAnyValue:StringLike" = {
            "cognito-identity.amazonaws.com:amr" = "authenticated"
          }
        }
      }
    ]
  })

  tags = module.label.tags
}

# Attach roles to Identity Pool
resource "aws_cognito_identity_pool_roles_attachment" "main" {
  identity_pool_id = aws_cognito_identity_pool.main.id

  roles = {
    "unauthenticated" = aws_iam_role.unauthenticated.arn
    "authenticated"   = aws_iam_role.authenticated.arn
  }
}

# -----------------------------------------------------------------------------
# Cognito User Pool Domain (required for OAuth2 flows)
# -----------------------------------------------------------------------------
# OAuth2 authorization endpoints require a domain to be configured.
# This creates a Cognito-hosted domain: {domain_prefix}.auth.{region}.amazoncognito.com
# Required for AgentCore OAuth2 Credential Provider to work.

resource "aws_cognito_user_pool_domain" "main" {
  domain       = module.label.id # e.g., "booking-dev-auth"
  user_pool_id = aws_cognito_user_pool.main.id
}
