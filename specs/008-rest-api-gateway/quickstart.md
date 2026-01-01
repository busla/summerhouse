# Quickstart: REST API Gateway Migration

**Phase**: 1 - Design | **Date**: 2025-12-31 | **Spec**: [spec.md](./spec.md)

## Overview

This guide covers the key changes and common tasks for migrating from HTTP API (`aws_apigatewayv2_*`) to REST API (`aws_api_gateway_*`).

---

## 1. Key Differences at a Glance

| Aspect | HTTP API (v2) | REST API |
|--------|---------------|----------|
| Integration type | `"AWS_PROXY"` | `"aws_proxy"` |
| Payload format | `payloadFormatVersion: "2.0"` | Always 1.0 (no property) |
| Passthrough | Implicit | `passthroughBehavior: "when_no_match"` |
| Authorizer type | `"jwt"` | `"cognito_user_pools"` |
| Token config | `jwtConfiguration` | `providerARNs` |
| CORS | `x-amazon-apigateway-cors` | Explicit OPTIONS methods |
| Stage name | `"$default"` | Named (default: `"api"`) |
| Auto-deploy | `auto_deploy = true` | Explicit deployment resource |
| Lambda ARN pattern | `/*/*` | `/*/*/*` |

---

## 2. Terraform Changes

### Deployment Resource

REST API requires an explicit deployment resource:

```hcl
resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  # CRITICAL: Trigger redeployment when OpenAPI changes
  triggers = {
    redeployment = sha1(jsonencode(aws_api_gateway_rest_api.main.body))
  }

  lifecycle {
    create_before_destroy = true
  }
}
```

**Why**: Without `triggers`, Terraform won't redeploy when OpenAPI spec changes. The `sha1(jsonencode(...))` pattern ensures changes are detected.

### CloudWatch IAM Role

REST API requires account-level IAM configuration for logging:

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
}

resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  role       = aws_iam_role.api_gateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}
```

**Note**: `aws_api_gateway_account` is account-global. If another module already creates it, use `count = 0` or import the existing resource.

### Lambda Permission Pattern

```hcl
# HTTP API (v2) - OLD
source_arn = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
#            execution_arn/{stage}/{route}

# REST API - NEW
source_arn = "${aws_api_gateway_rest_api.main.execution_arn}/*/*/*"
#            execution_arn/{stage}/{method}/{resource}
```

---

## 3. OpenAPI Script Changes

### Integration Extension

```python
# OLD (HTTP API)
operation["x-amazon-apigateway-integration"] = {
    "type": "AWS_PROXY",
    "httpMethod": "POST",
    "uri": integration_uri,
    "payloadFormatVersion": "2.0",
}

# NEW (REST API)
operation["x-amazon-apigateway-integration"] = {
    "type": "aws_proxy",
    "httpMethod": "POST",
    "uri": integration_uri,
    "passthroughBehavior": "when_no_match",
}
```

### Authorizer Extension

```python
# OLD (HTTP API)
openapi["components"]["securitySchemes"]["cognito-jwt"] = {
    "type": "oauth2",
    "x-amazon-apigateway-authorizer": {
        "type": "jwt",
        "identitySource": "$request.header.Authorization",
        "jwtConfiguration": {
            "issuer": f"https://cognito-idp.{region}.amazonaws.com/{pool_id}",
            "audience": [client_id],
        },
    },
}

# NEW (REST API)
openapi["components"]["securitySchemes"]["CognitoAuthorizer"] = {
    "type": "apiKey",
    "name": "Authorization",
    "in": "header",
    "x-amazon-apigateway-authtype": "cognito_user_pools",
    "x-amazon-apigateway-authorizer": {
        "type": "cognito_user_pools",
        "providerARNs": [
            f"arn:aws:cognito-idp:{region}:{account_id}:userpool/{pool_id}"
        ],
    },
}
```

**Note**: REST API uses full Cognito User Pool ARN, which requires `account_id` as input.

### CORS OPTIONS Methods

REST API doesn't support `x-amazon-apigateway-cors`. Generate OPTIONS for each path:

```python
def add_cors_options(path_item, cors_origins, methods):
    """Add OPTIONS method with mock integration for CORS."""
    path_item["options"] = {
        "summary": "CORS preflight",
        "responses": {
            "200": {
                "description": "CORS preflight response",
                "headers": {
                    "Access-Control-Allow-Origin": {"schema": {"type": "string"}},
                    "Access-Control-Allow-Methods": {"schema": {"type": "string"}},
                    "Access-Control-Allow-Headers": {"schema": {"type": "string"}},
                },
            }
        },
        "x-amazon-apigateway-integration": {
            "type": "mock",
            "requestTemplates": {"application/json": '{"statusCode": 200}'},
            "responses": {
                "default": {
                    "statusCode": "200",
                    "responseParameters": {
                        "method.response.header.Access-Control-Allow-Methods": f"'{','.join(methods)}'",
                        "method.response.header.Access-Control-Allow-Headers": "'Content-Type,Authorization,X-Requested-With,X-Amz-Date'",
                        "method.response.header.Access-Control-Allow-Origin": f"'{cors_origins[0]}'",
                    },
                }
            },
        },
    }
```

---

## 4. Testing the Migration

### Terraform Plan

```bash
# From repo root
task tf:plan:dev

# Expected changes:
# - aws_apigatewayv2_api.main: DESTROY
# - aws_apigatewayv2_stage.default: DESTROY
# + aws_api_gateway_rest_api.main: CREATE
# + aws_api_gateway_deployment.main: CREATE
# + aws_api_gateway_stage.main: CREATE
# + aws_api_gateway_account.main: CREATE
# + aws_iam_role.api_gateway_cloudwatch: CREATE
```

### Manual API Test

```bash
# Get the API URL (includes stage name)
API_URL=$(terraform output -raw api_gateway_url)
echo $API_URL
# https://abc123.execute-api.eu-west-1.amazonaws.com/api

# Test health endpoint
curl "$API_URL/api/ping"

# Test CORS preflight
curl -X OPTIONS "$API_URL/api/auth/callback" \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: POST" \
  -i

# Should see CORS headers:
# Access-Control-Allow-Origin: https://example.com
# Access-Control-Allow-Methods: GET,POST,OPTIONS
```

### Verify Lambda Invocation

```bash
# Check CloudWatch logs for Lambda
aws logs tail /aws/lambda/booking-dev-api --follow

# Call a protected endpoint
curl "$API_URL/api/reservations" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 5. Common Issues

### 403 Missing Authentication Token

**Symptom**: Calls return `{"message": "Missing Authentication Token"}`

**Cause**: REST API returns this for undefined routes (not just auth issues)

**Check**:
1. Route exists in OpenAPI spec
2. Deployment was triggered after spec changes
3. URL includes stage name (e.g., `/api/api/ping`)

### 500 Internal Server Error on OPTIONS

**Symptom**: CORS preflight returns 500

**Cause**: Missing or malformed mock integration

**Fix**: Verify OPTIONS method has all required response parameters:
```json
{
  "method.response.header.Access-Control-Allow-Origin": "'*'",
  "method.response.header.Access-Control-Allow-Methods": "'GET,POST,OPTIONS'",
  "method.response.header.Access-Control-Allow-Headers": "'Content-Type,Authorization'"
}
```

### Changes Not Taking Effect

**Symptom**: Updated routes don't appear in deployed API

**Cause**: Deployment not triggered

**Fix**: Ensure `triggers` block in `aws_api_gateway_deployment`:
```hcl
triggers = {
  redeployment = sha1(jsonencode(aws_api_gateway_rest_api.main.body))
}
```

### CloudWatch Logs Empty

**Symptom**: No access logs in CloudWatch

**Cause**: Missing `aws_api_gateway_account` IAM configuration

**Fix**: Add the account-level IAM role and attachment (see Section 2).

### Authorizer 401 Unauthorized

**Symptom**: Valid Cognito tokens rejected

**Cause**: Incorrect `providerARNs` format

**Check**: ARN must be full format:
```
arn:aws:cognito-idp:{region}:{account_id}:userpool/{pool_id}
```

Not just the pool ID (e.g., `eu-west-1_ABC123xyz`).

---

## 6. URL Format Change

Consumers need to account for the stage name in URLs:

| API Type | URL Format |
|----------|------------|
| HTTP API | `https://{api-id}.execute-api.{region}.amazonaws.com/api/ping` |
| REST API | `https://{api-id}.execute-api.{region}.amazonaws.com/api/api/ping` |

The `api_gateway_url` output includes the stage, so consumers using this output directly don't need changes.

---

## 7. File Reference

| File | Purpose |
|------|---------|
| `infrastructure/modules/gateway-v2/main.tf` | REST API resources |
| `infrastructure/modules/gateway-v2/variables.tf` | Module inputs (+ `stage_name`) |
| `infrastructure/modules/gateway-v2/outputs.tf` | Module outputs |
| `backend/api/src/api/scripts/generate_openapi.py` | OpenAPI generation |
| `specs/008-rest-api-gateway/contracts/openapi-rest-api.schema.json` | Schema validation |
| `specs/008-rest-api-gateway/contracts/gateway-v2-interface.md` | Module contract |
| `specs/008-rest-api-gateway/data-model.md` | Resource structures |
| `specs/008-rest-api-gateway/research.md` | Technical research |

---

## 8. Rollback Procedure

If migration causes issues:

1. **Revert Terraform module** to v2.x (HTTP API resources)
2. **Run `task tf:apply:dev`** - creates new HTTP API, destroys REST API
3. **Update DNS/frontend** if URL changed

**Note**: Rolling back will change the API Gateway ID, which may affect caching or rate limiting if consumers cache the API ID.
