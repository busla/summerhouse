# Booking: Agent-First Vacation Rental Booking Platform

Auto-generated from feature plans. Last updated: 2025-12-31

## Project Overview

An AI agent-driven vacation rental booking platform where the conversational agent IS the primary website interface. Users interact naturally with the agent to check availability, get pricing, view photos, and complete bookings for a single apartment in Quesada, Alicante.

## Technology Stack

### Frontend
- **Framework**: Next.js 14+ (App Router) with static export
- **AI SDK**: Vercel AI SDK v6 (`ai` package, `@ai-sdk/react`)
- **Language**: TypeScript 5.x (strict mode)
- **Package Manager**: Yarn Berry with `nodeLinker: node-modules`
- **Testing**: Vitest (unit), Playwright (E2E)

### Backend
- **Framework**: Strands Agents (Python 3.13+)
- **Package Manager**: UV workspaces (3 packages: `shared`, `api`, `agent`)
- **API**: FastAPI for REST endpoints
- **Data Validation**: Pydantic v2 (strict mode)
- **LLM**: Amazon Bedrock (Claude Sonnet)
- **Testing**: pytest

### Infrastructure
- **IaC**: Terraform via `terraform-aws-agentcore` module
- **Database**: AWS DynamoDB (6 tables)
- **Auth**: AWS Cognito (passwordless email verification)
- **Hosting**: S3 + CloudFront (frontend), AgentCore Runtime (backend)
- **Region**: Configured per environment in `terraform.tfvars.json`

## Research-First Rules

### NON-NEGOTIABLE: Research Before Writing Custom Code

**NEVER assume a library, SDK, or tool doesn't exist. ALWAYS verify first.**

Before writing ANY custom integration code (especially for AWS services):

1. **Use the AWS Documentation MCP server** (`mcp__aws-documentation__search_documentation`) to search for official SDKs and clients
2. **Search npm/PyPI** for official packages (e.g., `@aws-sdk/client-*` for AWS services)
3. **Check the AgentCore MCP server** (`mcp__agentcore__search_agentcore_docs`) for Bedrock AgentCore specifics

**AWS SDK Client Naming Convention:**
- AWS SDK v3 clients follow the pattern: `@aws-sdk/client-{service-name}`
- Example: `@aws-sdk/client-bedrock-agentcore`, `@aws-sdk/client-dynamodb`
- **ALWAYS check if a client exists before writing manual SigV4 signing or custom HTTP calls**

**Research workflow:**
```
1. Identify the AWS service being used
2. Search: mcp__aws-documentation__search_documentation(search_phrase="<service> SDK client")
3. Check npm: npm search @aws-sdk/client-<service>
4. Only if NO official client exists, consider custom implementation
```

**Violations of this rule waste significant time writing code that already exists.**

### NON-NEGOTIABLE: Use Official SDKs Over Custom Code

When an official SDK client exists:
- **DO**: Use the SDK client with `fromCognitoIdentityPool` for credentials
- **DON'T**: Write custom SigV4 signing code
- **DON'T**: Write custom HTTP request builders
- **DON'T**: Manually manage credentials when SDK handles it

## Infrastructure Rules

### NON-NEGOTIABLE: Use CloudPosse Label Module

**ALWAYS use `cloudposse/label/null` for consistent naming and tagging across all modules.**

Convention for this project:
- `namespace`: `booking`
- `environment`: `dev` or `prod` (from `var.environment`)
- `name`: Component name (e.g., `reservations`, `website`, `auth`)
- `attributes`: Optional additional context

Every module MUST include:
```hcl
module "label" {
  source  = "cloudposse/label/null"
  version = "~> 0.25"

  namespace   = "booking"
  environment = var.environment
  name        = "component-name"
}
```

Use `module.label.id` for resource names and `module.label.tags` for tags.

### NON-NEGOTIABLE: Use terraform-aws-modules

**NEVER write raw AWS resources when a terraform-aws-modules equivalent exists.**

Use modules from [terraform-aws-modules](https://github.com/terraform-aws-modules):

| Resource Type | Required Module |
|---------------|-----------------|
| DynamoDB tables | `terraform-aws-modules/dynamodb-table/aws` |
| S3 buckets | `terraform-aws-modules/s3-bucket/aws` |
| CloudFront | `terraform-aws-modules/cloudfront/aws` |
| IAM roles/policies | `terraform-aws-modules/iam/aws` |
| Lambda functions | `terraform-aws-modules/lambda/aws` |
| VPC/networking | `terraform-aws-modules/vpc/aws` |
| Security groups | `terraform-aws-modules/security-group/aws` |
| ALB/NLB | `terraform-aws-modules/alb/aws` |
| ECS | `terraform-aws-modules/ecs/aws` |
| RDS | `terraform-aws-modules/rds/aws` |

**Exceptions** (no terraform-aws-modules equivalent):
- Cognito User Pool / Client
- Bedrock resources
- Custom/niche AWS services

### NON-NEGOTIABLE: Use Taskfile for Terraform

**NEVER run `terraform` or `terragrunt` commands directly. ALL commands via Taskfile.**

If a `task tf:*` command fails, report the error to the user. Do NOT bypass with raw terraform.

### NON-NEGOTIABLE: Terraform Must Be Fully Declarative

**Terraform must handle EVERYTHING. NEVER require users to run external commands before `task tf:apply`.**

This means:
- **NO** pre-build steps outside Terraform (e.g., "run this script first")
- **NO** workarounds like "run apply twice"
- **NO** external dependencies that must exist before plan/apply

**For Lambda functions with `terraform-aws-modules/lambda/aws`:**
- **DO**: Use `source_path` to let the module build packages declaratively
- **DO**: Use `pip_requirements` for Python dependencies
- **DO**: Use the module's built-in packaging features
- **DON'T**: Use `local_existing_package` which requires pre-built files (causes `fileexists()` failures during plan)
- **DON'T**: Use `terraform_data` or `null_resource` to build packages (timing issues with plan-phase function evaluation)

Example of correct Lambda configuration:
```hcl
module "lambda" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "~> 8.1"

  function_name = "my-function"
  handler       = "api.main.handler"
  runtime       = "python3.13"

  # UV workspace: include only needed packages (api + shared)
  # Dependencies provided via separate Lambda layer
  source_path = [
    { path = "${path.module}/../backend/api/src" },
    { path = "${path.module}/../backend/shared/src" }
  ]

  layers = [module.lambda_layer.lambda_layer_arn]
}
```

**Violations of this rule create broken workflows that require manual intervention.**

### Frontend Auto-Deploy via Terraform

The `static-website` module automatically detects frontend source changes, builds, and deploys:

**How it works:**
- `terraform_data.frontend_build` hashes ALL frontend source files using `fileset()` + `sha256()`
- Files watched: `src/**/*`, `public/**/*`, `*.{json,js,mjs,ts,cjs,yaml,yml}`
- Generated directories (`node_modules/`, `.next/`, `out/`, `.yarn/`) are naturally excluded
- When hash changes: runs `yarn install && yarn build`, then syncs to S3 and invalidates CloudFront

**Usage:**
```bash
# After making frontend changes:
task tf:plan:dev   # Shows frontend_build will be replaced if hash changed
task tf:apply:dev  # Builds and deploys frontend automatically
```

**Note:** If `task tf:apply:dev` shows no changes after frontend modifications, the hash detection is working correctly and determined no source files changed.

## Critical Commands

**⚠️ All Terraform commands MUST be run via Taskfile.yaml - NEVER run terraform directly**

```bash
# Terraform (always from repo root, syntax: task tf:<action>:<env>)
task tf:init:dev      # Initialize for dev
task tf:plan:dev      # Plan changes
task tf:apply:dev     # Apply changes
task tf:destroy:dev   # Destroy (careful!)
task tf:output:dev    # Show outputs
task tf:envs          # List available environments

# Backend (UV workspace)
task backend:install  # Install all packages with `uv sync`
task backend:dev      # Run FastAPI dev server on :3001
task backend:test     # Run pytest
task backend:lint     # Run ruff
task backend:typecheck # Run mypy on shared/src api/src agent/src

# Frontend
task frontend:install # Install deps with Yarn
task frontend:dev     # Run Next.js dev server on :3000
task frontend:build   # Build static export
task frontend:test    # Run Vitest
task frontend:lint    # Run eslint

# Combined
task install          # Install all dependencies
task dev              # Run both frontend and backend
task test             # Run all tests
task lint             # Run all linters

# Data
task seed:dev         # Seed dev database
```

## Project Structure

```text
booking/
├── Taskfile.yaml           # ⚠️ ALL terraform commands via this
├── CLAUDE.md               # This file
├── backend/                # UV workspace root
│   ├── pyproject.toml      # Workspace definition (members: agent, api, shared)
│   ├── shared/             # Shared components package
│   │   ├── pyproject.toml
│   │   └── src/shared/
│   │       ├── models/     # Pydantic data models
│   │       ├── services/   # Business logic (DynamoDB, booking, etc.)
│   │       ├── tools/      # @tool decorated functions
│   │       └── utils/      # Utilities (JWT, etc.)
│   ├── api/                # FastAPI REST API package
│   │   ├── pyproject.toml
│   │   └── src/api/
│   │       ├── main.py     # FastAPI app + Mangum handler
│   │       ├── routes/     # API routers (auth, health)
│   │       └── middleware/ # Request/response middleware
│   ├── agent/              # Strands Agent package
│   │   ├── pyproject.toml
│   │   └── src/agent/
│   │       ├── main.py     # Lambda handler
│   │       ├── booking_agent.py
│   │       └── prompts/    # System prompts
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── contract/
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js App Router
│   │   ├── components/     # React components
│   │   ├── lib/            # Utilities
│   │   └── types/
│   ├── tests/
│   │   ├── unit/
│   │   └── e2e/
│   └── package.json
├── infrastructure/
│   ├── main.tf
│   └── environments/
│       ├── dev/
│       │   ├── backend.hcl
│       │   └── terraform.tfvars.json
│       └── prod/
│           ├── backend.hcl
│           └── terraform.tfvars.json
└── specs/
    └── 001-agent-booking-platform/
        ├── spec.md
        ├── plan.md
        ├── tasks.md
        ├── data-model.md
        ├── quickstart.md
        └── contracts/
```

## DynamoDB Tables

| Table | Purpose | PK | SK |
|-------|---------|----|----|
| `booking-{env}-reservations` | Bookings | `reservation_id` | — |
| `booking-{env}-guests` | Guest profiles | `guest_id` | — |
| `booking-{env}-availability` | Date availability | `date` | — |
| `booking-{env}-pricing` | Seasonal pricing | `season_id` | — |
| `booking-{env}-payments` | Payment records | `payment_id` | — |
| `booking-{env}-verification-codes` | Auth codes (TTL) | `email` | — |

## Strands Tools

Tools are Python functions with `@tool` decorator. Categories:

**Inquiry** (no side effects):
- `check_availability`, `get_calendar`, `get_pricing`, `calculate_total`
- `get_property_details`, `get_photos`, `get_area_info`, `get_recommendations`
- `get_guest_info`, `get_reservation`

**Booking** (requires verification):
- `create_reservation`, `modify_reservation`, `cancel_reservation`, `process_payment`

**Verification**:
- `initiate_verification`, `verify_code`

## Code Style

### Python (Backend)
- Type hints on all functions
- Pydantic models with `strict=True` for validation
- Strands `@tool` decorator for agent tools
- Follow ruff linting rules

### TypeScript (Frontend)
- Strict mode enabled
- Use `useChat` hook from Vercel AI SDK
- Server components by default (App Router)
- Follow ESLint + Prettier config

## Backend Patterns

### DynamoDB Singleton Pattern (Performance)

**All tools MUST use `get_dynamodb_service()` instead of instantiating `DynamoDBService` directly.**

This avoids ~100-200ms boto3 re-instantiation overhead per tool call:

```python
from shared.services.dynamodb import get_dynamodb_service

def _get_db():
    """Get shared DynamoDB service instance (singleton for performance)."""
    return get_dynamodb_service()

@tool
def my_tool():
    db = _get_db()  # ✅ Use singleton
    # db = DynamoDBService()  # ❌ Never instantiate directly
```

### ToolError Standard Error Format

**All tools MUST return `ToolError` for error conditions.**

Standard error response format defined in `backend/shared/src/shared/models/errors.py`:

```python
from shared.models.errors import ErrorCode, ToolError

# Return structured error
if not reservation:
    error = ToolError.from_code(
        ErrorCode.RESERVATION_NOT_FOUND,
        details={"reservation_id": reservation_id},
    )
    return error.model_dump()  # Returns structured dict
```

**Error response structure:**
```json
{
  "success": false,
  "error_code": "ERR_006",
  "message": "Reservation not found",
  "recovery": "Ask guest to verify reservation ID",
  "details": {"reservation_id": "RES-2025-ABC123"}
}
```

**Standard error codes:**
| Code | Name | When to Use |
|------|------|-------------|
| ERR_001 | DATES_UNAVAILABLE | Requested dates are booked/blocked |
| ERR_002 | MINIMUM_NIGHTS_NOT_MET | Stay duration below seasonal minimum |
| ERR_003 | MAX_GUESTS_EXCEEDED | More than 4 guests requested |
| ERR_004 | VERIFICATION_REQUIRED | Booking attempted without verification |
| ERR_005 | VERIFICATION_FAILED | Invalid/expired verification code |
| ERR_006 | RESERVATION_NOT_FOUND | Reservation ID doesn't exist |
| ERR_007 | UNAUTHORIZED | Guest can't modify this reservation |
| ERR_008 | PAYMENT_FAILED | Payment processing error |

## Environment Variables

### Backend (.env)
```
AWS_REGION=us-east-1
DYNAMODB_RESERVATIONS_TABLE=booking-dev-reservations
DYNAMODB_GUESTS_TABLE=booking-dev-guests
COGNITO_USER_POOL_ID=us-east-1_xxxxx
COGNITO_CLIENT_ID=xxxxx
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514
LOG_LEVEL=INFO
```

### Frontend (.env.local)
```
# AWS Region for SDK clients
NEXT_PUBLIC_AWS_REGION=eu-west-1

# Cognito Identity Pool for anonymous AWS credentials
NEXT_PUBLIC_COGNITO_IDENTITY_POOL_ID=eu-west-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# AgentCore Runtime ARN (full ARN, not just the ID)
# Format: arn:aws:bedrock-agentcore:{region}:{account}:runtime/{id}
NEXT_PUBLIC_AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:eu-west-1:123456789012:runtime/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

**Note**: The frontend uses `@aws-sdk/client-bedrock-agentcore` with credentials from `@aws-sdk/credential-providers` (fromCognitoIdentityPool). No custom SigV4 signing required.

## Constitution Principles

This project follows the Booking Constitution (v1.1.0):

1. **Test-First Development (NON-NEGOTIABLE)** - TDD for all features
2. **Simplicity & YAGNI** - Minimal viable implementation
3. **Type Safety** - Strict typing in both languages
4. **Observability** - Structured logging, correlation IDs
5. **Incremental Delivery** - Small, independently deployable increments
6. **Technology Stack (NON-NEGOTIABLE)** - Vercel AI SDK, Strands, terraform-aws-agentcore

## Key Constraints

- Single property (one apartment in Quesada, Alicante)
- Max 4 guests per booking
- Minimum night requirements vary by season
- Payment processing is mocked (MVP)
- Email verification required for bookings

## Performance Goals

- Agent response < 3 seconds
- 100 concurrent conversations
- 99.9% availability accuracy
- Zero double-bookings

## Key Resources

- Feature Spec: `specs/001-agent-booking-platform/spec.md`
- Implementation Plan: `specs/001-agent-booking-platform/plan.md`
- Task Breakdown: `specs/001-agent-booking-platform/tasks.md`
- Data Model: `specs/001-agent-booking-platform/data-model.md`
- API Contracts: `specs/001-agent-booking-platform/contracts/`
- Quickstart Guide: `specs/001-agent-booking-platform/quickstart.md`
- Constitution: `.specify/memory/constitution.md`

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

## Active Technologies
- HCL (Terraform >= 1.5.0) + cloudposse/waf/aws v1.17.0, cloudposse/label/null ~> 0.25, terraform-aws-modules/cloudfront/aws ~> 6.0 (002-static-website-waf)
- N/A (Infrastructure as Code module) (002-static-website-waf)
- Python 3.13+ (backend), TypeScript 5.x strict mode (frontend) + Strands Agents, bedrock-agentcore, boto3 (cognito-idp), FastAPI (backend); Vercel AI SDK v6, @aws-sdk/client-cognito-identity-provider (frontend) (003-agentcore-identity-oauth2)
- AWS Cognito User Pool (user identity), DynamoDB (OAuth2 session state with TTL) (003-agentcore-identity-oauth2)
- Python 3.13+ (backend), TypeScript 5.x (frontend) + bedrock-agentcore, boto3, strands-agents, @aws-amplify/ui-react, @aws-amplify/auth (003-agentcore-identity-oauth2)
- DynamoDB (OAuth2 sessions table with TTL), AWS Cognito (user identity) (003-agentcore-identity-oauth2)
- Python 3.13+ (backend), TypeScript 5.x strict mode (frontend) + strands-agents, boto3 (cognito-idp), pyjwt (backend); Vercel AI SDK v6, @aws-sdk/client-bedrock-agentcore (frontend) (004-jwt-session-auth)
- AWS Cognito User Pool (EMAIL_OTP), localStorage (browser session), DynamoDB (guests table) (004-jwt-session-auth)
- N/A (AgentCore Identity manages token vault; Cognito manages users) (005-agentcore-amplify-oauth2)
- Python 3.13+ + UV workspaces, FastAPI, Pydantic v2 (backend); HCL (Terraform >= 1.5.0) (infrastructure) (006-backend-workspace-openapi)
- AWS API Gateway HTTP API (OpenAPI-provisioned), AWS Cognito JWT authorizer (006-backend-workspace-openapi)
- Python 3.13+ + FastAPI, Pydantic v2 strict mode; pytest + moto (testing) (007-tools-api-endpoints)
- DynamoDB (6 tables), AWS API Gateway HTTP API with JWT authorizer (007-tools-api-endpoints)
- HCL (Terraform >= 1.5.0) + cloudposse/label/null ~> 0.25, terraform-aws-modules/lambda/aws ~> 8.1; Python 3.13 (OpenAPI generation) (008-rest-api-gateway)
- AWS API Gateway REST API (OpenAPI-provisioned), Cognito User Pools authorizer, explicit deployment/stage resources (008-rest-api-gateway)

## Recent Changes
- 008-rest-api-gateway: Migrate gateway-v2 module from HTTP API to REST API; Cognito User Pools authorizer, explicit OPTIONS methods for CORS, deployment triggers
- 007-tools-api-endpoints: 21 REST endpoints exposing Strands agent tools; reuses shared/services layer; marker-based JWT auth for OpenAPI generation
- 006-backend-workspace-openapi: Restructured backend into UV workspace (agent, api, shared); API Gateway provisioned via OpenAPI with JWT authorizer
- 004-jwt-session-auth: Added JWT token delivery from backend to frontend, TokenDeliveryEvent in tool responses, auth_token in transport payload
