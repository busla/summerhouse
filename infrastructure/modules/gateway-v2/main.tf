# Gateway-v2 Module - FastAPI Lambda + API Gateway HTTP API
# Provides OAuth2 callback endpoint and API access for the booking platform
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
  name    = "api"
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# Lambda Dependencies Layer
# -----------------------------------------------------------------------------
# Uses uv to install dependencies with Linux platform targeting.
# This avoids Docker by using uv's --python-platform flag to download
# Linux-compatible wheels (e.g., pydantic-core) on macOS/Windows.
#
# The layer is built in a local directory and packaged by terraform-aws-modules/lambda.

locals {
  # Layer build directory - outside of terraform state
  layer_build_dir = "${path.module}/builds/layer"
  # Hash of requirements file to trigger rebuilds
  requirements_hash = filemd5("${var.backend_source_dir}/requirements-api.txt")
}

# Build layer dependencies using uv with Linux platform targeting
resource "terraform_data" "layer_deps" {
  triggers_replace = {
    requirements_hash = local.requirements_hash
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      rm -rf "${local.layer_build_dir}"
      mkdir -p "${local.layer_build_dir}/python"
      uv pip install \
        --python-platform x86_64-manylinux2014 \
        --python-version 3.13 \
        --target "${local.layer_build_dir}/python" \
        -r "${var.backend_source_dir}/requirements-api.txt"
    EOT
  }
}

# Lambda layer for Python dependencies
module "lambda_layer" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.1"

  create_layer = true
  create_function = false

  layer_name          = "${module.label.id}-deps"
  description         = "Python dependencies for API Lambda (pydantic, fastapi, boto3)"
  compatible_runtimes = [var.runtime]

  # Package the uv-built dependencies
  source_path = local.layer_build_dir

  tags = module.label.tags

  depends_on = [terraform_data.layer_deps]
}

# -----------------------------------------------------------------------------
# Lambda Function
# -----------------------------------------------------------------------------
# Uses source_path for application code only (dependencies in layer).
# No Docker required - layer handles platform-specific binaries.

module "lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.1"

  function_name = module.label.id
  description   = "FastAPI Lambda for Booking API (OAuth2 callbacks)"
  handler       = var.handler
  runtime       = var.runtime
  memory_size   = var.memory_size
  timeout       = var.timeout

  # Application code only - dependencies provided by layer
  # API Lambda only needs api and shared packages (agent runs in AgentCore Runtime)
  source_path = [
    {
      path = "${var.backend_source_dir}/api/src"
    },
    {
      path = "${var.backend_source_dir}/shared/src"
    }
  ]

  # Attach dependencies layer
  layers = [module.lambda_layer.lambda_layer_arn]

  environment_variables = merge(
    {
      ENVIRONMENT                    = module.label.environment
      DYNAMODB_TABLE_PREFIX          = var.dynamodb_table_prefix
      DYNAMODB_OAUTH2_SESSIONS_TABLE = var.oauth2_sessions_table_name
      COGNITO_USER_POOL_ID           = var.cognito_user_pool_id
      COGNITO_CLIENT_ID              = var.cognito_client_id
      FRONTEND_URL                   = var.frontend_url
    },
    var.environment_vars
  )

  # IAM
  attach_policy_json = true
  policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid    = "DynamoDBOAuth2Sessions"
          Effect = "Allow"
          Action = [
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:UpdateItem",
            "dynamodb:DeleteItem",
            "dynamodb:Query"
          ]
          Resource = [
            var.oauth2_sessions_table_arn,
            "${var.oauth2_sessions_table_arn}/index/*"
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
      ],
      # Additional DynamoDB tables for API routes (booking tables)
      length(var.dynamodb_table_arns) > 0 ? [
        {
          Sid    = "DynamoDBBookingTables"
          Effect = "Allow"
          Action = [
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:UpdateItem",
            "dynamodb:DeleteItem",
            "dynamodb:Query",
            "dynamodb:Scan",
            "dynamodb:BatchGetItem",
            "dynamodb:BatchWriteItem"
          ]
          Resource = concat(
            var.dynamodb_table_arns,
            [for arn in var.dynamodb_table_arns : "${arn}/index/*"]
          )
        }
      ] : []
    )
  })

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# OpenAPI Generation (when enable_openapi_generation = true)
# -----------------------------------------------------------------------------
# Uses external data source to generate OpenAPI at plan time.
# The Python script outputs JSON with openapi_spec as a JSON-encoded string.
#
# NOTE: We compute the Lambda ARN rather than referencing module.lambda.lambda_function_arn
# to avoid a dependency cycle. The cycle occurs because:
#   gateway_v2.frontend_url <- static_website.website_url <- cloudfront <- api_gateway_url <- gateway_v2
# Using computed ARN breaks this cycle since it only depends on region/account/function_name.

locals {
  # Compute Lambda ARN without depending on Lambda module output (breaks dependency cycle)
  lambda_function_arn = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${module.label.id}"
}

data "external" "openapi" {
  count = var.enable_openapi_generation ? 1 : 0

  program = [
    "uv", "run", "--package", "api",
    "python", "-m", "api.scripts.generate_openapi"
  ]

  working_dir = var.backend_source_dir

  query = {
    lambda_arn           = local.lambda_function_arn
    cognito_user_pool_id = var.cognito_user_pool_id
    cognito_client_id    = var.cognito_client_id
    cors_allow_origins   = jsonencode(var.cors_allow_origins)
  }
}

# -----------------------------------------------------------------------------
# API Gateway HTTP API
# -----------------------------------------------------------------------------
# When OpenAPI generation is enabled, routes/integrations come from the spec body.
# When disabled (legacy mode), uses catch-all routing with explicit integration.

resource "aws_apigatewayv2_api" "main" {
  name          = module.label.id
  protocol_type = "HTTP"
  description   = "HTTP API for Booking FastAPI Lambda"

  # Use OpenAPI body when enabled, otherwise use inline CORS
  body = var.enable_openapi_generation ? data.external.openapi[0].result.openapi_spec : null

  # CORS configuration only used when NOT using OpenAPI body
  # (OpenAPI body includes x-amazon-apigateway-cors)
  dynamic "cors_configuration" {
    for_each = var.enable_openapi_generation ? [] : [1]
    content {
      allow_origins = var.cors_allow_origins
      allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
      allow_headers = ["Content-Type", "Authorization", "X-Requested-With", "X-Amz-Date"]
      max_age       = 86400
    }
  }

  tags = module.label.tags

  # Force replacement when OpenAPI spec changes
  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      responseLength = "$context.responseLength"
      errorMessage   = "$context.error.message"
    })
  }

  tags = module.label.tags
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${module.label.id}"
  retention_in_days = 7

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# Legacy Mode: Explicit Lambda integration and catch-all route
# Only created when NOT using OpenAPI generation
# -----------------------------------------------------------------------------

resource "aws_apigatewayv2_integration" "lambda" {
  count = var.enable_openapi_generation ? 0 : 1

  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = module.lambda.lambda_function_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  count = var.enable_openapi_generation ? 0 : 1

  api_id    = aws_apigatewayv2_api.main.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda[0].id}"
}

# Lambda permission for API Gateway (needed in both modes)
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
