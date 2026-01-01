# Data Model: REST API Gateway Migration

**Feature**: 008-rest-api-gateway
**Date**: 2025-12-31
**Type**: Terraform Module Migration (Infrastructure as Code)

## Overview

This document defines the Terraform variables, outputs, and resource structures for migrating `infrastructure/modules/gateway-v2` from AWS API Gateway HTTP API to REST API. The module interface remains compatible with minimal changes.

## Resource Relationship Diagram

### Current (HTTP API)

```
┌─────────────────────────────────────────────────────────────────┐
│                    HTTP API Architecture                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  aws_apigatewayv2_api ─────► aws_apigatewayv2_stage             │
│         │                        ($default, auto_deploy)        │
│         │                                                        │
│         └───────────────────────────────────────────────────►   │
│                                                                  │
│            OpenAPI body with:                                    │
│            - x-amazon-apigateway-cors                           │
│            - x-amazon-apigateway-integration (AWS_PROXY)        │
│            - x-amazon-apigateway-authorizer (jwt)               │
│                                                                  │
│  aws_lambda_permission ────► module.lambda                      │
│         (/*/*)                   │                               │
│                                  └──► module.lambda_layer       │
│                                                                  │
│  aws_cloudwatch_log_group                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Target (REST API)

```
┌─────────────────────────────────────────────────────────────────┐
│                    REST API Architecture                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  aws_api_gateway_rest_api ─► aws_api_gateway_deployment         │
│         │                           │                            │
│         │                           └──► aws_api_gateway_stage  │
│         │                                 (named stage)          │
│         │                                       │                │
│         │                                       └──► access_log  │
│         │                                             settings   │
│         └───────────────────────────────────────────────────►   │
│                                                                  │
│            OpenAPI body with:                                    │
│            - OPTIONS methods (mock integration for CORS)        │
│            - x-amazon-apigateway-integration (aws_proxy)        │
│            - x-amazon-apigateway-authorizer (cognito_user_pools)│
│                                                                  │
│  aws_lambda_permission ────► module.lambda                      │
│         (/*/*/*)                 │                               │
│                                  └──► module.lambda_layer       │
│                                                                  │
│  aws_cloudwatch_log_group                                        │
│                                                                  │
│  aws_api_gateway_account ──► aws_iam_role (CloudWatch logging)  │
│         (CloudWatch IAM)                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Terraform Variables

### Existing Variables (Unchanged)

All existing variables remain compatible:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `context` | any | CloudPosse defaults | CloudPosse label context from root module |
| `backend_source_dir` | string | (required) | Path to backend source directory |
| `handler` | string | `"api.main.handler"` | Lambda handler path |
| `runtime` | string | `"python3.13"` | Lambda runtime |
| `memory_size` | number | `512` | Lambda memory in MB |
| `timeout` | number | `30` | Lambda timeout in seconds |
| `environment_vars` | map(string) | `{}` | Additional Lambda environment variables |
| `dynamodb_table_prefix` | string | (required) | DynamoDB table name prefix |
| `oauth2_sessions_table_name` | string | (required) | OAuth2 sessions table name |
| `oauth2_sessions_table_arn` | string | (required) | OAuth2 sessions table ARN |
| `dynamodb_table_arns` | list(string) | `[]` | Additional DynamoDB table ARNs |
| `cognito_user_pool_id` | string | (required) | Cognito User Pool ID |
| `cognito_client_id` | string | (required) | Cognito User Pool Client ID |
| `frontend_url` | string | (required) | Frontend URL for OAuth2 redirects |
| `cors_allow_origins` | list(string) | `["*"]` | Allowed CORS origins |
| `enable_openapi_generation` | bool | `true` | Enable OpenAPI-based provisioning |

### New Variable: Stage Name

```hcl
variable "stage_name" {
  description = "REST API stage name (CloudFront origin path abstracts this from end users)"
  type        = string
  default     = "api"

  validation {
    condition     = can(regex("^[a-zA-Z0-9_]+$", var.stage_name))
    error_message = "Stage name must contain only alphanumeric characters and underscores."
  }
}
```

**Rationale**: Fixed stage name `"api"` provides a clean, semantic URL structure. CloudFront origin path configuration (`origin_path = "/api"`) abstracts the stage from end-user URLs, so users see `/api/ping` while the REST API receives `/api/api/ping` (CloudFront prepends `/api` to the request path).

### Variable Usage Notes

| Variable | HTTP API Usage | REST API Usage |
|----------|----------------|----------------|
| `cognito_user_pool_id` | JWT issuer URL | Construct `providerARNs` |
| `cognito_client_id` | JWT audience | **Not used** (retained for backward compatibility; REST API authorizer uses pool ARN only) |
| `cors_allow_origins` | `x-amazon-apigateway-cors` | Generated OPTIONS methods |

---

## Terraform Outputs

### Outputs with Changes

| Output | Current (HTTP API) | Target (REST API) |
|--------|-------------------|-------------------|
| `api_gateway_url` | `aws_apigatewayv2_api.main.api_endpoint` | `aws_api_gateway_stage.main.invoke_url` |
| `api_gateway_id` | `aws_apigatewayv2_api.main.id` | `aws_api_gateway_rest_api.main.id` |
| `api_gateway_arn` | `aws_apigatewayv2_api.main.execution_arn` | `aws_api_gateway_rest_api.main.execution_arn` |
| `oauth2_callback_url` | `${api_endpoint}/api/auth/callback` | `${invoke_url}/api/auth/callback` |

### Updated Output Definitions

```hcl
output "api_gateway_url" {
  description = "API Gateway invoke URL"
  value       = aws_api_gateway_stage.main.invoke_url
}

output "api_gateway_id" {
  description = "API Gateway REST API ID"
  value       = aws_api_gateway_rest_api.main.id
}

output "api_gateway_arn" {
  description = "API Gateway execution ARN"
  value       = aws_api_gateway_rest_api.main.execution_arn
}

output "oauth2_callback_url" {
  description = "Full OAuth2 callback URL for Cognito"
  value       = "${aws_api_gateway_stage.main.invoke_url}/api/auth/callback"
}
```

### Unchanged Outputs

These Lambda-related outputs remain identical:

- `lambda_function_name`
- `lambda_function_arn`
- `lambda_role_name`
- `lambda_role_arn`
- `lambda_layer_arn`

### New Output: Stage Name

```hcl
output "api_gateway_stage_name" {
  description = "REST API stage name"
  value       = aws_api_gateway_stage.main.stage_name
}
```

---

## AWS Resources

### Resources to Remove (HTTP API)

| Resource | Type | Purpose |
|----------|------|---------|
| `aws_apigatewayv2_api.main` | HTTP API | Base API resource |
| `aws_apigatewayv2_stage.default` | Stage | Auto-deploy stage |
| `aws_apigatewayv2_integration.lambda[0]` | Integration | Legacy mode Lambda integration |
| `aws_apigatewayv2_route.default[0]` | Route | Legacy mode catch-all route |

### Resources to Add (REST API)

#### 1. REST API Resource

```hcl
resource "aws_api_gateway_rest_api" "main" {
  name        = module.label.id
  description = "REST API for Booking FastAPI Lambda"

  # Use OpenAPI body when enabled
  body = var.enable_openapi_generation ? data.external.openapi[0].result.openapi_spec : null

  # Required for REST API with OpenAPI body
  put_rest_api_mode = "overwrite"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = module.label.tags
}
```

**Key Differences from HTTP API**:
- No `protocol_type` (REST is default)
- `put_rest_api_mode = "overwrite"` required for OpenAPI body updates
- `endpoint_configuration.types` explicitly set

#### 2. Deployment Resource

```hcl
resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  # Trigger redeployment when OpenAPI body changes
  triggers = {
    redeployment = sha1(jsonencode(aws_api_gateway_rest_api.main.body))
  }

  lifecycle {
    create_before_destroy = true
  }
}
```

**Critical**: The `triggers` block with SHA1 hash ensures deployments occur when the OpenAPI spec changes. Without this, REST API changes won't take effect.

#### 3. Stage Resource

```hcl
resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = var.stage_name

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      responseLength = "$context.responseLength"
      errorMessage   = "$context.error.message"
    })
  }

  tags = module.label.tags
}
```

**Key Differences**:
- Named stage instead of `$default`
- `$context.resourcePath` instead of `$context.routeKey`
- No `auto_deploy` (explicit deployment resource handles this)

#### 4. CloudWatch IAM Role (Required for REST API Logging)

```hcl
resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn
}

resource "aws_iam_role" "api_gateway_cloudwatch" {
  name = "${module.label.id}-apigw-cw"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "apigateway.amazonaws.com"
      }
    }]
  })

  tags = module.label.tags
}

resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  role       = aws_iam_role.api_gateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}
```

**Note**: This IAM configuration is account-level and may already exist. Consider using `count` or `lifecycle { prevent_destroy = true }` to handle existing resources.

#### 5. Updated Lambda Permission

```hcl
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  # REST API pattern: execution_arn/{stage}/{method}/{resource}
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*/*"
}
```

**Key Change**: ARN pattern from `/*/*` to `/*/*/*`.

### Unchanged Resources

| Resource | Purpose |
|----------|---------|
| `module.label` | CloudPosse naming |
| `terraform_data.layer_deps` | Layer dependency build |
| `module.lambda_layer` | Lambda dependencies layer |
| `module.lambda` | Lambda function |
| `data.external.openapi` | OpenAPI generation |
| `aws_cloudwatch_log_group.api_gateway` | Access logs (unchanged) |

---

## OpenAPI Schema Changes

The `generate_openapi.py` script must produce different OpenAPI extensions:

### Integration Extension

**Before (HTTP API)**:
```json
{
  "x-amazon-apigateway-integration": {
    "type": "AWS_PROXY",
    "httpMethod": "POST",
    "uri": "arn:aws:apigateway:{region}:lambda:...",
    "payloadFormatVersion": "2.0"
  }
}
```

**After (REST API)**:
```json
{
  "x-amazon-apigateway-integration": {
    "type": "aws_proxy",
    "httpMethod": "POST",
    "uri": "arn:aws:apigateway:{region}:lambda:...",
    "passthroughBehavior": "when_no_match"
  }
}
```

### Authorizer Extension

**Before (HTTP API)**:
```json
{
  "components": {
    "securitySchemes": {
      "cognito-jwt": {
        "type": "oauth2",
        "x-amazon-apigateway-authorizer": {
          "type": "jwt",
          "identitySource": "$request.header.Authorization",
          "jwtConfiguration": {
            "issuer": "https://cognito-idp.{region}.amazonaws.com/{pool}",
            "audience": ["{client_id}"]
          }
        }
      }
    }
  }
}
```

**After (REST API)**:
```json
{
  "components": {
    "securitySchemes": {
      "CognitoAuthorizer": {
        "type": "apiKey",
        "name": "Authorization",
        "in": "header",
        "x-amazon-apigateway-authtype": "cognito_user_pools",
        "x-amazon-apigateway-authorizer": {
          "type": "cognito_user_pools",
          "providerARNs": [
            "arn:aws:cognito-idp:{region}:{account}:userpool/{pool}"
          ]
        }
      }
    }
  }
}
```

### CORS Configuration

**Before (HTTP API)** - API-level extension:
```json
{
  "x-amazon-apigateway-cors": {
    "allowOrigins": ["https://example.com"],
    "allowMethods": ["GET", "POST", ...],
    "allowHeaders": [...],
    "maxAge": 86400
  }
}
```

**After (REST API)** - Explicit OPTIONS methods per path:
```json
{
  "paths": {
    "/bookings": {
      "options": {
        "x-amazon-apigateway-integration": {
          "type": "mock",
          "requestTemplates": { "application/json": "{\"statusCode\": 200}" },
          "responses": {
            "default": {
              "statusCode": "200",
              "responseParameters": {
                "method.response.header.Access-Control-Allow-Methods": "'GET,POST,OPTIONS'",
                "method.response.header.Access-Control-Allow-Headers": "'Content-Type,Authorization'",
                "method.response.header.Access-Control-Allow-Origin": "'https://example.com'"
              }
            }
          }
        },
        "responses": {
          "200": {
            "headers": {
              "Access-Control-Allow-Origin": { "schema": { "type": "string" } },
              "Access-Control-Allow-Methods": { "schema": { "type": "string" } },
              "Access-Control-Allow-Headers": { "schema": { "type": "string" } }
            }
          }
        }
      }
    }
  }
}
```

---

## Script Input Changes

### External Data Source Query

```hcl
data "external" "openapi" {
  count = var.enable_openapi_generation ? 1 : 0

  program = [
    "uv", "run", "--package", "api",
    "python", "-m", "api.scripts.generate_openapi"
  ]

  working_dir = var.backend_source_dir

  query = {
    # Existing
    lambda_arn           = local.lambda_function_arn
    cognito_user_pool_id = var.cognito_user_pool_id
    cognito_client_id    = var.cognito_client_id
    cors_allow_origins   = jsonencode(var.cors_allow_origins)

    # New: API type flag
    api_type             = "rest"  # "rest" or "http"

    # New: AWS account ID (for Cognito ARN construction)
    aws_account_id       = data.aws_caller_identity.current.account_id
  }
}
```

---

## URL Format Change

| API Type | URL Format | Example |
|----------|------------|---------|
| HTTP API | `https://{api-id}.execute-api.{region}.amazonaws.com` | `https://abc123.execute-api.eu-west-1.amazonaws.com` |
| REST API | `https://{api-id}.execute-api.{region}.amazonaws.com/{stage}` | `https://abc123.execute-api.eu-west-1.amazonaws.com/prod` |

**Impact**: Frontend configuration may need updating if it constructs URLs manually. The `api_gateway_url` output includes the stage name, so consumers using this output require no changes.

---

## Migration Checklist

### Terraform Changes

- [ ] Replace `aws_apigatewayv2_api` with `aws_api_gateway_rest_api`
- [ ] Add `aws_api_gateway_deployment` resource
- [ ] Replace `aws_apigatewayv2_stage` with `aws_api_gateway_stage`
- [ ] Add `aws_api_gateway_account` and IAM role for CloudWatch
- [ ] Update `aws_lambda_permission` ARN pattern
- [ ] Add `stage_name` variable
- [ ] Update all outputs to use REST API resources

### OpenAPI Script Changes

- [ ] Change integration type from `AWS_PROXY` to `aws_proxy`
- [ ] Remove `payloadFormatVersion`
- [ ] Add `passthroughBehavior`
- [ ] Change authorizer from `jwt` to `cognito_user_pools`
- [ ] Construct `providerARNs` from pool ID and account ID
- [ ] Generate OPTIONS methods for CORS
- [ ] Accept `api_type` and `aws_account_id` inputs

### Root Module Changes

- [ ] Pass `stage_name` variable (optional, defaults to "prod")
- [ ] No other changes required (interface compatible)
