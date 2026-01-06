# OTP Interceptor Module - Custom Email Sender Lambda Trigger
# Intercepts OTP codes from Cognito EMAIL_OTP authentication by taking over email
# delivery. Stores codes in DynamoDB for E2E test retrieval, then forwards to SES.
#
# ARCHITECTURE NOTE: Custom Email Sender receives the ACTUAL encrypted OTP code,
# unlike Custom Message which only receives a placeholder. This requires:
# - KMS key for decrypting the code
# - Taking over email delivery (we send via SES)
#
# Reference: specs/019-e2e-email-otp/contracts/cognito-trigger-event.md
#
# Uses terraform-aws-modules/lambda/aws per CLAUDE.md requirements

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
# CloudPosse Label
# -----------------------------------------------------------------------------

module "label" {
  source  = "cloudposse/label/null"
  version = "~> 0.25"

  context = var.context
  name    = "otp-interceptor"
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# KMS Key for Custom Email Sender
# -----------------------------------------------------------------------------
# Cognito encrypts the OTP code with this key before passing to Lambda.
# Lambda decrypts to get the actual code for storage and email delivery.

resource "aws_kms_key" "custom_email_sender" {
  description             = "KMS key for Cognito Custom Email Sender - encrypts OTP codes"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  # Policy allowing Cognito to encrypt and Lambda to decrypt
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowRootAccountFullAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowCognitoToEncrypt"
        Effect = "Allow"
        Principal = {
          Service = "cognito-idp.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:GenerateDataKey*"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = module.label.tags
}

resource "aws_kms_alias" "custom_email_sender" {
  name          = "alias/${module.label.id}"
  target_key_id = aws_kms_key.custom_email_sender.key_id
}

# -----------------------------------------------------------------------------
# Lambda Function
# -----------------------------------------------------------------------------
# Custom Email Sender Lambda that:
# 1. Decrypts the OTP code from Cognito
# 2. Stores it in DynamoDB for E2E test retrieval (test emails only)
# 3. Sends the email via SES (all emails)

module "lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.1"

  function_name = module.label.id
  description   = "Custom Email Sender - intercepts OTP codes and sends via SES"
  handler       = "handler.handler"
  runtime       = var.runtime
  memory_size   = var.memory_size
  timeout       = var.timeout

  # IMPORTANT: Use arm64 (Graviton2) architecture for native dependencies.
  # The Docker build runs on Apple Silicon (arm64) so pip downloads arm64 wheels.
  # arm64 Lambdas are also ~20% cheaper and typically faster than x86_64.
  architectures = ["arm64"]

  # Build dependencies in Docker to ensure Linux-compatible native binaries.
  # The cryptography package (required by aws-encryption-sdk) contains Rust-compiled
  # .so files that must be built for Linux, not macOS.
  # Uses SAM build image which has pip pre-configured for Lambda packaging.
  build_in_docker = true
  docker_image    = "public.ecr.aws/sam/build-python3.12"

  # Lambda source code - structured format enables pip_requirements in Docker
  source_path = [
    {
      path             = var.lambda_source_path
      pip_requirements = true
      patterns = [
        "!.*/.*\\.pyc",
        "!__pycache__/.*",
        "!tests/.*",
        "!\\.pytest_cache/.*"
      ]
    }
  ]

  environment_variables = {
    ENVIRONMENT              = module.label.environment
    VERIFICATION_CODES_TABLE = var.verification_codes_table_name
    KMS_KEY_ARN              = aws_kms_key.custom_email_sender.arn
    SES_FROM_EMAIL           = var.ses_from_email
    SES_REGION               = data.aws_region.current.id
  }

  # IAM policy for DynamoDB, KMS, and SES access
  attach_policy_json = true
  policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDBVerificationCodes"
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem"
        ]
        Resource = var.verification_codes_table_arn
      },
      {
        Sid    = "KMSDecrypt"
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = aws_kms_key.custom_email_sender.arn
      },
      {
        Sid    = "SESSendEmail"
        Effect = "Allow"
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = [
          "arn:aws:ses:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:identity/${var.ses_identity}",
          "arn:aws:ses:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:configuration-set/*"
        ]
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:*"
      }
    ]
  })

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# Cognito Lambda Permission
# -----------------------------------------------------------------------------
# Allow Cognito User Pool to invoke this Lambda as Custom Email Sender trigger.
# Only created if cognito_user_pool_arn is provided.

resource "aws_lambda_permission" "cognito" {
  count = var.cognito_user_pool_arn != null ? 1 : 0

  statement_id  = "AllowCognitoInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.lambda_function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = var.cognito_user_pool_arn
}
