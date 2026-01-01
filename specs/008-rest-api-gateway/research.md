# Phase 0 Research: REST API Gateway Migration

**Feature**: REST API Gateway Migration (008-rest-api-gateway)
**Date**: 2025-12-31
**Status**: Complete

## Summary

This research documents the technical differences between AWS API Gateway HTTP API (v2) and REST API (v1), focusing on OpenAPI-driven configuration, Cognito authorizer integration, and Terraform resource patterns. The findings inform the migration of `infrastructure/modules/gateway-v2` from HTTP API to REST API.

---

## 1. API Gateway HTTP API vs REST API Comparison

### 1.1 Resource Type Differences

| Aspect | HTTP API (Current) | REST API (Target) |
|--------|-------------------|-------------------|
| Terraform resource | `aws_apigatewayv2_api` | `aws_api_gateway_rest_api` |
| Protocol type | `protocol_type = "HTTP"` | N/A (REST by default) |
| Auto deploy | `auto_deploy = true` on stage | Requires explicit `aws_api_gateway_deployment` |
| Stage resource | `aws_apigatewayv2_stage` | `aws_api_gateway_stage` |
| Integration resource | `aws_apigatewayv2_integration` | Embedded in OpenAPI or `aws_api_gateway_integration` |
| Authorizer | JWT authorizer | Cognito User Pools authorizer |

### 1.2 Deployment Model Differences

**HTTP API (Current)**:
```hcl
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true  # Automatic deployment on changes
}
```

**REST API (Target)**:
```hcl
resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  triggers = {
    redeployment = sha1(jsonencode(aws_api_gateway_rest_api.main.body))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = var.stage_name  # e.g., "prod" or "v1"
}
```

**Key Insight**: REST API requires explicit deployment tracking via `triggers` to detect OpenAPI body changes, whereas HTTP API handles this automatically with `auto_deploy`.

---

## 2. OpenAPI Integration Extensions

### 2.1 Lambda Proxy Integration Format

**HTTP API (Current)**:
```json
"x-amazon-apigateway-integration": {
  "type": "AWS_PROXY",
  "httpMethod": "POST",
  "uri": "arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{lambda-arn}/invocations",
  "payloadFormatVersion": "2.0"
}
```

**REST API (Target)**:
```json
"x-amazon-apigateway-integration": {
  "type": "aws_proxy",
  "httpMethod": "POST",
  "uri": "arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{lambda-arn}/invocations",
  "passthroughBehavior": "when_no_match",
  "responses": {
    "default": {
      "statusCode": "200"
    }
  }
}
```

**Critical Differences**:
| Property | HTTP API | REST API |
|----------|----------|----------|
| `type` | `"AWS_PROXY"` (uppercase) | `"aws_proxy"` (lowercase) |
| `payloadFormatVersion` | `"2.0"` | Not supported (always 1.0) |
| `passthroughBehavior` | Not required | Required: `"when_no_match"` |
| `responses` | Not required | Required for non-proxy integrations |

### 2.2 CORS Configuration

**HTTP API (Current)** - API-level extension:
```json
"x-amazon-apigateway-cors": {
  "allowOrigins": ["https://example.com"],
  "allowMethods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
  "allowHeaders": ["Content-Type", "Authorization", "X-Requested-With", "X-Amz-Date"],
  "maxAge": 86400
}
```

**REST API (Target)** - Mock integration for OPTIONS:
```json
"options": {
  "responses": {
    "200": {
      "description": "CORS preflight response",
      "headers": {
        "Access-Control-Allow-Origin": { "schema": { "type": "string" } },
        "Access-Control-Allow-Methods": { "schema": { "type": "string" } },
        "Access-Control-Allow-Headers": { "schema": { "type": "string" } }
      }
    }
  },
  "x-amazon-apigateway-integration": {
    "type": "mock",
    "requestTemplates": {
      "application/json": "{\"statusCode\": 200}"
    },
    "responses": {
      "default": {
        "statusCode": "200",
        "responseParameters": {
          "method.response.header.Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS,PATCH'",
          "method.response.header.Access-Control-Allow-Headers": "'Content-Type,Authorization,X-Requested-With,X-Amz-Date'",
          "method.response.header.Access-Control-Allow-Origin": "'https://example.com'"
        }
      }
    }
  }
}
```

**Key Insight**: REST API does not support the `x-amazon-apigateway-cors` shorthand. CORS must be implemented via explicit OPTIONS methods with mock integrations.

---

## 3. Cognito Authorizer Configuration

### 3.1 Security Scheme Definitions

**HTTP API (Current)** - JWT Authorizer:
```json
"components": {
  "securitySchemes": {
    "cognito-jwt": {
      "type": "oauth2",
      "x-amazon-apigateway-authorizer": {
        "type": "jwt",
        "identitySource": "$request.header.Authorization",
        "jwtConfiguration": {
          "issuer": "https://cognito-idp.{region}.amazonaws.com/{user_pool_id}",
          "audience": ["{client_id}"]
        }
      },
      "flows": {
        "implicit": {
          "authorizationUrl": "https://{domain}.auth.{region}.amazoncognito.com/oauth2/authorize",
          "scopes": {}
        }
      }
    }
  }
}
```

**REST API (Target)** - Cognito User Pools Authorizer:
```json
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
          "arn:aws:cognito-idp:{region}:{account_id}:userpool/{user_pool_id}"
        ]
      }
    }
  }
}
```

**Critical Differences**:
| Property | HTTP API | REST API |
|----------|----------|----------|
| `type` (securityScheme) | `"oauth2"` | `"apiKey"` |
| Authorizer `type` | `"jwt"` | `"cognito_user_pools"` |
| Identity source | `identitySource` | `name` + `in` |
| Pool reference | `jwtConfiguration.issuer` | `providerARNs` (full ARN) |

### 3.2 Applying Security to Operations

Both APIs use the same OpenAPI security application pattern:

```json
"paths": {
  "/bookings": {
    "get": {
      "security": [{ "CognitoAuthorizer": [] }],
      "x-amazon-apigateway-integration": { ... }
    }
  }
}
```

---

## 4. CloudWatch Logging Configuration

### 4.1 Terraform Configuration

**HTTP API (Current)**:
```hcl
resource "aws_apigatewayv2_stage" "default" {
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
}
```

**REST API (Target)**:
```hcl
resource "aws_api_gateway_stage" "main" {
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
}
```

**Key Difference**: REST API uses `$context.resourcePath` instead of `$context.routeKey`.

### 4.2 IAM Permissions for Logging

REST API requires an IAM role for CloudWatch logging (unlike HTTP API):

```hcl
resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn
}

resource "aws_iam_role" "api_gateway_cloudwatch" {
  name = "${module.label.id}-apigw-cloudwatch"

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
}

resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  role       = aws_iam_role.api_gateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}
```

---

## 5. Lambda Permission Configuration

**HTTP API (Current)**:
```hcl
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
```

**REST API (Target)**:
```hcl
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*/*"
}
```

**Key Difference**: REST API execution ARN pattern uses `/*/*/*` (stage/method/resource) vs HTTP API's `/*/*` (stage/route).

---

## 6. OpenAPI Script Changes Required

The `backend/api/src/api/scripts/generate_openapi.py` script requires updates:

### 6.1 Integration Extension Changes

```python
# Current (HTTP API)
operation["x-amazon-apigateway-integration"] = {
    "type": "AWS_PROXY",
    "httpMethod": "POST",
    "uri": integration_uri,
    "payloadFormatVersion": "2.0",
}

# Updated (REST API)
operation["x-amazon-apigateway-integration"] = {
    "type": "aws_proxy",
    "httpMethod": "POST",
    "uri": integration_uri,
    "passthroughBehavior": "when_no_match",
}
```

### 6.2 Authorizer Extension Changes

```python
# Current (HTTP API)
openapi["components"]["securitySchemes"]["cognito-jwt"] = {
    "type": "oauth2",
    "x-amazon-apigateway-authorizer": {
        "type": "jwt",
        "identitySource": "$request.header.Authorization",
        "jwtConfiguration": {
            "issuer": f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}",
            "audience": [client_id],
        },
    },
    ...
}

# Updated (REST API)
openapi["components"]["securitySchemes"]["CognitoAuthorizer"] = {
    "type": "apiKey",
    "name": "Authorization",
    "in": "header",
    "x-amazon-apigateway-authtype": "cognito_user_pools",
    "x-amazon-apigateway-authorizer": {
        "type": "cognito_user_pools",
        "providerARNs": [
            f"arn:aws:cognito-idp:{region}:{account_id}:userpool/{user_pool_id}"
        ],
    },
}
```

### 6.3 CORS Handling Changes

The script must generate explicit OPTIONS methods with mock integrations for each path, rather than relying on `x-amazon-apigateway-cors`.

---

## 7. Terraform Module Migration Pattern

### 7.1 Resource Mapping

| Current (gateway-v2) | Target (gateway-v2) |
|---------------------|---------------------|
| `aws_apigatewayv2_api.main` | `aws_api_gateway_rest_api.main` |
| `aws_apigatewayv2_stage.default` | `aws_api_gateway_stage.main` + `aws_api_gateway_deployment.main` |
| `aws_apigatewayv2_integration.lambda` (legacy) | Removed (OpenAPI body) |
| `aws_apigatewayv2_route.default` (legacy) | Removed (OpenAPI body) |
| `aws_lambda_permission.api_gateway` | `aws_lambda_permission.api_gateway` (ARN pattern change) |
| `aws_cloudwatch_log_group.api_gateway` | `aws_cloudwatch_log_group.api_gateway` (unchanged) |
| — | `aws_api_gateway_account.main` (new - CloudWatch IAM) |
| — | `aws_iam_role.api_gateway_cloudwatch` (new) |

### 7.2 Variable Changes

No variable interface changes required. The module inputs remain compatible:

- `cognito_user_pool_id` → Used for `providerARNs` construction
- `cognito_client_id` → No longer used in authorizer (REST API uses pool ARN only)
- `cors_allow_origins` → Used in CORS OPTIONS responses
- `enable_openapi_generation` → Unchanged
- `backend_source_dir` → Unchanged

### 7.3 Output Changes

| Output | Current | Target |
|--------|---------|--------|
| `api_gateway_url` | `aws_apigatewayv2_api.main.api_endpoint` | `aws_api_gateway_stage.main.invoke_url` |
| `api_gateway_id` | `aws_apigatewayv2_api.main.id` | `aws_api_gateway_rest_api.main.id` |
| `api_gateway_arn` | `aws_apigatewayv2_api.main.arn` | `aws_api_gateway_rest_api.main.arn` |
| `execution_arn` | `aws_apigatewayv2_api.main.execution_arn` | `aws_api_gateway_rest_api.main.execution_arn` |

---

## 8. Risk Assessment

### 8.1 High Risk Areas

1. **CORS Implementation**: Moving from declarative `x-amazon-apigateway-cors` to procedural OPTIONS methods significantly increases OpenAPI complexity.
   - **Mitigation**: Generate OPTIONS methods programmatically in `generate_openapi.py`

2. **Deployment Timing**: REST API requires explicit deployment resource with proper triggers to detect changes.
   - **Mitigation**: Use `sha1(jsonencode(...body))` trigger pattern with `create_before_destroy` lifecycle

3. **Payload Format Incompatibility**: REST API uses payload format 1.0, not 2.0.
   - **Impact**: Lambda handler receives slightly different event structure
   - **Mitigation**: Mangum adapter handles both formats; verify with integration tests

### 8.2 Medium Risk Areas

1. **CloudWatch IAM Role**: REST API requires account-level IAM role for logging.
   - **Impact**: First deployment may fail if role not configured
   - **Mitigation**: Add `aws_api_gateway_account` resource with proper IAM role

2. **Stage Name Change**: Moving from `$default` to named stage (e.g., `prod`).
   - **Impact**: URL format changes from `https://{api-id}.execute-api.{region}.amazonaws.com` to `https://{api-id}.execute-api.{region}.amazonaws.com/{stage}`
   - **Mitigation**: Document URL change; update frontend configuration if needed

### 8.3 Low Risk Areas

1. **Lambda Permission ARN Pattern**: Minor change from `/*/*` to `/*/*/*`.
   - **Impact**: None if configured correctly
   - **Mitigation**: Straightforward pattern update

---

## 9. Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Does REST API support `$default` stage? | No, REST API requires named stages. Use environment name or `prod`. |
| Is `cognito_client_id` needed for REST API authorizer? | No, REST API uses `providerARNs` only (pool ARN, not client). |
| How to handle deployment ordering? | Use `depends_on` and `triggers` with `create_before_destroy`. |
| Is binary media handling different? | Not for Lambda proxy integration; both pass through to Lambda. |

---

## 10. References

- [AWS API Gateway REST API Developer Guide](https://docs.aws.amazon.com/apigateway/latest/developerguide/)
- [Terraform aws_api_gateway_rest_api](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_rest_api)
- [Terraform aws_api_gateway_stage](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_stage)
- [x-amazon-apigateway-integration for REST API](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-integration.html)
- [x-amazon-apigateway-authorizer for Cognito](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-swagger-extensions-authorizer.html)
