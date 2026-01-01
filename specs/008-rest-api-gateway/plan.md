# Implementation Plan: REST API Gateway Migration

**Branch**: `008-rest-api-gateway` | **Date**: 2025-12-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-rest-api-gateway/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Migrate the existing `infrastructure/modules/gateway-v2` from AWS API Gateway HTTP API (`aws_apigatewayv2_api`) to AWS API Gateway REST API (`aws_api_gateway_rest_api`). The migration maintains OpenAPI-driven route configuration, Cognito JWT authorization, and CloudWatch logging while enabling REST API-specific features. The module interface (inputs/outputs) remains compatible to minimize changes to the root Terraform configuration.

## Technical Context

**Language/Version**: HCL (Terraform >= 1.5.0), Python 3.13 (OpenAPI generation)
**Primary Dependencies**: cloudposse/label/null ~> 0.25, terraform-aws-modules/lambda/aws ~> 8.1, AWS provider >= 5.0
**Storage**: N/A (Infrastructure module)
**Testing**: `task tf:plan:dev`, `task tf:apply:dev`, manual endpoint verification
**Target Platform**: AWS (API Gateway REST API, Lambda, CloudWatch)
**Project Type**: Single module refactoring
**Performance Goals**: API response < 3 seconds (unchanged from current)
**Constraints**: REST API cold start must accommodate Lambda cold starts
**Scale/Scope**: Single Terraform module, ~300 lines of HCL

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Test-First Development | ✅ PASS | Terraform plan/apply provides implicit testing; manual API verification; quickstart.md documents test procedures |
| II. Simplicity & YAGNI | ✅ PASS | Direct migration without adding unused REST API features (caching, API keys, usage plans marked out of scope) |
| III. Type Safety | ✅ PASS | Terraform validation rules in variables.tf; JSON Schema (`openapi-rest-api.schema.json`) enforces OpenAPI structure |
| IV. Observability | ✅ PASS | CloudWatch access logging preserved; data-model.md defines log format explicitly |
| V. Incremental Delivery | ✅ PASS | Single module change, independently deployable; interface contract preserves backward compatibility |
| VI. Technology Stack | ✅ PASS | Uses terraform-aws-modules for Lambda; no terraform-aws-modules exists for REST API (verified) |
| UI Component Development | N/A | No UI components in this feature |

**Post-Design Verification (2025-12-31)**: ✅ All principles verified against Phase 1 artifacts (data-model.md, contracts/, quickstart.md). No scope creep or violations introduced.

**Notes on Technology Stack**:
- `terraform-aws-modules/apigateway-v2` only supports HTTP/WebSocket APIs (v2), not REST APIs
- REST API requires raw AWS provider resources (`aws_api_gateway_rest_api`, `aws_api_gateway_deployment`, `aws_api_gateway_stage`, `aws_api_gateway_authorizer`)
- This is a valid exception per CLAUDE.md: "Exceptions (no terraform-aws-modules equivalent): [...] Custom/niche AWS services"

## Project Structure

### Documentation (this feature)

```text
specs/008-rest-api-gateway/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
infrastructure/
├── main.tf                        # Root module (references gateway-v2)
├── variables.tf                   # Root variables
├── outputs.tf                     # Root outputs
└── modules/
    └── gateway-v2/                # Module being migrated
        ├── main.tf                # REST API resources (migrated from HTTP API)
        ├── variables.tf           # Module inputs (interface preserved)
        └── outputs.tf             # Module outputs (interface preserved)

backend/
└── api/
    └── src/api/
        └── scripts/
            └── generate_openapi.py  # Updated for REST API extensions
```

**Structure Decision**: The existing module structure is preserved. Only the internal implementation changes from HTTP API to REST API resources.

## Complexity Tracking

> **No violations identified** - All changes follow constitution principles.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Raw AWS resources (no terraform-aws-modules) | No terraform-aws-modules exists for REST API | N/A - terraform-aws-modules/apigateway-v2 only supports HTTP/WebSocket |
