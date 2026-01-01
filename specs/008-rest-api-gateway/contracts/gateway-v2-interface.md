# Contract: gateway-v2 Terraform Module Interface

**Version**: 3.0.0 (breaking change from v2.x - REST API migration)
**Date**: 2025-12-31
**Feature**: 008-rest-api-gateway

## Overview

This document defines the contract for the `gateway-v2` Terraform module migrated from AWS API Gateway HTTP API (`aws_apigatewayv2_api`) to AWS API Gateway REST API (`aws_api_gateway_rest_api`). The module interface remains backwards-compatible with v2.x inputs while changing internal implementation.

---

## Module Location

```
infrastructure/modules/gateway-v2/
├── main.tf          # REST API resources (migrated from HTTP API)
├── variables.tf     # Module inputs (interface preserved)
└── outputs.tf       # Module outputs (interface preserved)
```

---

## Breaking Changes from v2.x

### API Type Change

| Aspect | v2.x (HTTP API) | v3.x (REST API) |
|--------|-----------------|-----------------|
| Terraform resource | `aws_apigatewayv2_api` | `aws_api_gateway_rest_api` |
| Auto-deploy | Built-in | Explicit `aws_api_gateway_deployment` |
| Stage naming | `$default` | Named stage (default: `api`) |
| URL format | `https://{api-id}.execute-api.{region}.amazonaws.com` | `https://{api-id}.execute-api.{region}.amazonaws.com/{stage}` |

### New Resources Created

```hcl
# Explicit deployment resource (no auto_deploy in REST API)
resource "aws_api_gateway_deployment" "main" { ... }

# Named stage (REST API doesn't support $default)
resource "aws_api_gateway_stage" "main" { ... }

# CloudWatch IAM role (required for REST API logging)
resource "aws_api_gateway_account" "main" { ... }
resource "aws_iam_role" "api_gateway_cloudwatch" { ... }
```

### Removed Resources

```hcl
# REMOVED - replaced by aws_api_gateway_rest_api
# resource "aws_apigatewayv2_api" "main" { ... }

# REMOVED - replaced by aws_api_gateway_stage
# resource "aws_apigatewayv2_stage" "default" { ... }
```

---

## Input Variables

### Required Variables (Unchanged)

| Variable | Type | Description |
|----------|------|-------------|
| `context` | `any` | CloudPosse label context from root module |
| `backend_source_dir` | `string` | Path to backend source directory for OpenAPI generation |
| `dynamodb_table_prefix` | `string` | DynamoDB table name prefix |
| `oauth2_sessions_table_name` | `string` | OAuth2 sessions table name |
| `oauth2_sessions_table_arn` | `string` | OAuth2 sessions table ARN |
| `cognito_user_pool_id` | `string` | Cognito User Pool ID |
| `cognito_client_id` | `string` | Cognito User Pool Client ID |
| `frontend_url` | `string` | Frontend URL for OAuth2 redirects |

### Optional Variables (Unchanged)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `handler` | `string` | `"api.main.handler"` | Lambda handler path |
| `runtime` | `string` | `"python3.13"` | Lambda runtime |
| `memory_size` | `number` | `512` | Lambda memory in MB |
| `timeout` | `number` | `30` | Lambda timeout in seconds |
| `environment_vars` | `map(string)` | `{}` | Additional Lambda environment variables |
| `dynamodb_table_arns` | `list(string)` | `[]` | Additional DynamoDB table ARNs |
| `cors_allow_origins` | `list(string)` | `["*"]` | Allowed CORS origins |
| `enable_openapi_generation` | `bool` | `true` | Enable OpenAPI-based provisioning |

### New Variable (v3.0)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `stage_name` | `string` | `"api"` | REST API stage name (REST API requires named stages) |

**Validation**: Stage name must match `^[a-zA-Z0-9_]+$` (alphanumeric and underscores only).

**CloudFront Integration**: When using CloudFront as origin, set `origin_path = "/api"` to abstract the stage name from end-user URLs.

---

## Output Values

### Changed Outputs (Same Name, Different Source)

| Output | v2.x Source | v3.x Source |
|--------|-------------|-------------|
| `api_gateway_url` | `aws_apigatewayv2_api.main.api_endpoint` | `aws_api_gateway_stage.main.invoke_url` |
| `api_gateway_id` | `aws_apigatewayv2_api.main.id` | `aws_api_gateway_rest_api.main.id` |
| `api_gateway_arn` | `aws_apigatewayv2_api.main.execution_arn` | `aws_api_gateway_rest_api.main.execution_arn` |
| `oauth2_callback_url` | `${api_endpoint}/api/auth/callback` | `${invoke_url}/api/auth/callback` |

### Unchanged Outputs

| Output | Type | Description |
|--------|------|-------------|
| `lambda_function_name` | `string` | Lambda function name |
| `lambda_function_arn` | `string` | Lambda function ARN |
| `lambda_role_name` | `string` | Lambda execution role name |
| `lambda_role_arn` | `string` | Lambda execution role ARN |

### New Output (v3.0)

| Output | Type | Description |
|--------|------|-------------|
| `api_gateway_stage_name` | `string` | REST API stage name |

---

## Module Usage

### v2.x Usage (DEPRECATED)

```hcl
module "gateway" {
  source = "./modules/gateway-v2"

  context              = module.label.context
  backend_source_dir   = local.backend_source_dir
  dynamodb_table_prefix = local.dynamodb_table_prefix
  # ... other variables
}
# URL: https://{api-id}.execute-api.{region}.amazonaws.com
```

### v3.x Usage

```hcl
module "gateway" {
  source = "./modules/gateway-v2"

  context              = module.label.context
  backend_source_dir   = local.backend_source_dir
  dynamodb_table_prefix = local.dynamodb_table_prefix

  # NEW: Optional stage name (defaults to "api")
  # stage_name         = "api"  # usually omitted, uses default

  # ... other variables unchanged
}
# URL: https://{api-id}.execute-api.{region}.amazonaws.com/api
```

---

## OpenAPI Generation Contract

### External Data Source Changes

The `generate_openapi.py` script receives additional parameters:

```hcl
data "external" "openapi" {
  count = var.enable_openapi_generation ? 1 : 0

  program = [
    "uv", "run", "--package", "api",
    "python", "-m", "api.scripts.generate_openapi"
  ]

  working_dir = var.backend_source_dir

  query = {
    # Existing parameters
    lambda_arn           = local.lambda_function_arn
    cognito_user_pool_id = var.cognito_user_pool_id
    cognito_client_id    = var.cognito_client_id
    cors_allow_origins   = jsonencode(var.cors_allow_origins)

    # NEW: REST API specific parameters
    api_type             = "rest"
    aws_account_id       = data.aws_caller_identity.current.account_id
  }
}
```

### Script Input Changes

| Parameter | v2.x | v3.x |
|-----------|------|------|
| `api_type` | N/A (assumed `"http"`) | `"rest"` (explicit) |
| `aws_account_id` | N/A | Required for Cognito ARN construction |

---

## Lambda Permission Changes

### v2.x (HTTP API)

```hcl
resource "aws_lambda_permission" "api_gateway" {
  source_arn = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
  #            execution_arn/{stage}/{route}
}
```

### v3.x (REST API)

```hcl
resource "aws_lambda_permission" "api_gateway" {
  source_arn = "${aws_api_gateway_rest_api.main.execution_arn}/*/*/*"
  #            execution_arn/{stage}/{method}/{resource}
}
```

**Note**: REST API ARN pattern includes HTTP method as a separate segment.

---

## Validation Checklist

Before deployment, verify:

- [ ] `cognito_user_pool_id` format: `{region}_{id}` (e.g., `eu-west-1_ABC123xyz`)
- [ ] `cognito_client_id` is the App Client ID
- [ ] Python 3.13 and `uv` are available in Terraform execution environment
- [ ] FastAPI app is importable from `backend_source_dir`
- [ ] `stage_name` contains only alphanumeric characters and underscores
- [ ] Frontend handles URL with stage name suffix

---

## Error Scenarios

| Error | Cause | Resolution |
|-------|-------|------------|
| `Invalid stage name` | Stage name contains invalid characters | Use only `[a-zA-Z0-9_]` |
| `CloudWatch logging failed` | Missing IAM role | Verify `aws_api_gateway_account` is created |
| `Deployment not created` | Missing deployment triggers | Check `sha1(jsonencode(...body))` trigger |
| `401 Unauthorized` | Cognito authorizer misconfigured | Verify `providerARNs` in OpenAPI |
| `CORS preflight failed` | Missing OPTIONS methods | Verify OpenAPI includes mock OPTIONS |

---

## Migration Notes

### URL Impact

Consumers of `api_gateway_url` output need to account for the stage name:

- **v2.x**: `https://abc123.execute-api.eu-west-1.amazonaws.com`
- **v3.x**: `https://abc123.execute-api.eu-west-1.amazonaws.com/api`

The output already includes the stage, so consumers using `api_gateway_url` directly require no changes.

**CloudFront Integration**: When CloudFront fronts the API Gateway, configure `origin_path = "/api"` so end users access clean URLs (e.g., `/api/ping`) while CloudFront routes to `/api/api/ping` internally.

### Cognito Client ID (Backward Compatibility)

The `cognito_client_id` variable is **no longer used** in the REST API authorizer configuration. REST API Cognito authorizers use `providerARNs` (User Pool ARN) instead of client ID.

**Why retained**: The variable is kept for backward compatibility with v2.x root module configurations. Removing it would require all callers to update their Terraform code. The variable is accepted but ignored - no functional impact.
