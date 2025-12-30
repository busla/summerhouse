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
# Lambda Function
# -----------------------------------------------------------------------------
# Uses source_path with pip_requirements for fully declarative packaging.
# Per CLAUDE.md: NEVER use local_existing_package or terraform_data for builds.

module "lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.1"

  function_name = module.label.id
  description   = "FastAPI Lambda for Booking API (OAuth2 callbacks)"
  handler       = var.handler
  runtime       = var.runtime
  memory_size   = var.memory_size
  timeout       = var.timeout

  # Declarative packaging - module handles everything
  source_path = [
    {
      path             = "${var.backend_source_dir}/src"
      pip_requirements = "${var.backend_source_dir}/requirements-api.txt"
    }
  ]

  environment_variables = merge(
    {
      ENVIRONMENT                    = module.label.environment
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
    Statement = [
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
    ]
  })

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# API Gateway HTTP API
# -----------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "main" {
  name          = module.label.id
  protocol_type = "HTTP"
  description   = "HTTP API for Booking FastAPI Lambda"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
    max_age       = 3600
  }

  tags = module.label.tags
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

# Lambda integration
resource "aws_apigatewayv2_integration" "lambda" {
  api_id             = aws_apigatewayv2_api.main.id
  integration_type   = "AWS_PROXY"
  integration_uri    = module.lambda.lambda_function_arn
  integration_method = "POST"
  payload_format_version = "2.0"
}

# Catch-all route
resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
