# Booking: Agent-First Vacation Rental Platform

Single-property vacation rental booking in Quesada, Alicante. AI agent is the primary interface.

## Tech Stack

| Layer | Stack |
|-------|-------|
| Frontend | Next.js 14+ (App Router, static export), TypeScript strict, Vercel AI SDK v6, Yarn Berry |
| Backend | Python 3.13+, UV workspaces (shared/api/agent), Strands Agents, FastAPI, Pydantic v2 strict |
| Infra | Terraform via `terraform-aws-agentcore`, DynamoDB, Cognito, S3+CloudFront, AgentCore Runtime |
| Testing | Vitest + Playwright (frontend), pytest + moto (backend) |

## NON-NEGOTIABLE Rules

### 1. Research Before Custom Code

**NEVER write custom integration code without verifying SDKs exist first.**

```
1. mcp__aws-documentation__search_documentation(search_phrase="<service> SDK client")
2. npm search @aws-sdk/client-<service>
3. Only if NO client exists → custom implementation
```

AWS SDK v3 pattern: `@aws-sdk/client-{service-name}`

### 2. Use terraform-aws-modules

**NEVER write raw AWS resources when a module exists.**

| Use Module For | Exception (raw OK) |
|----------------|-------------------|
| DynamoDB, S3, CloudFront, IAM, Lambda, VPC, SG, ALB, ECS, RDS | Cognito, Bedrock, niche services |

### 3. CloudPosse Label Module

Every module MUST use `cloudposse/label/null`:
- `namespace`: `booking`
- `environment`: `dev`/`prod`
- `name`: component name

### 4. Taskfile Only

**NEVER run terraform/terragrunt directly. ALL via `task tf:*`**

### 5. Terraform Fully Declarative

- NO pre-build steps outside Terraform
- NO "run apply twice" workarounds
- For Lambda: use `source_path`, NOT `local_existing_package`

### 6. Generated API Clients

- Frontend MUST use `@hey-api/openapi-ts` generated clients
- NO custom fetch/axios for OpenAPI endpoints
- Regenerate when backend spec changes

### 7. shadcn/ui First

Research shadcn/ui catalogue before ANY custom UI component.

## Commands

```bash
# Terraform (ALWAYS use these)
task tf:init:dev | task tf:plan:dev | task tf:apply:dev | task tf:output:dev

# Backend
task backend:install    # uv sync
task backend:dev        # FastAPI on :3001
task backend:test       # pytest

# Frontend  
task frontend:install   # yarn
task frontend:dev       # Next.js on :3000
task frontend:build     # static export

# Combined
task install | task dev | task test | task lint
```

## Project Structure

```
booking/
├── backend/
│   ├── shared/src/shared/   # models/, services/, tools/, utils/
│   ├── api/src/api/         # FastAPI app, routes/, middleware/
│   └── agent/src/agent/     # Strands agent, prompts/
├── frontend/src/
│   ├── app/                 # Next.js App Router
│   ├── components/          # React + shadcn/ui
│   └── lib/                 # Generated API client
├── infrastructure/
│   ├── main.tf
│   └── environments/{dev,prod}/
└── specs/{NNN-feature}/     # spec.md, plan.md, tasks.md, etc.
```

## Backend Patterns

### DynamoDB Singleton (Required)

```python
from shared.services.dynamodb import get_dynamodb_service

@tool
def my_tool():
    db = get_dynamodb_service()  # ✅ Singleton
    # db = DynamoDBService()     # ❌ Never instantiate directly
```

### ToolError Format (Required)

```python
from shared.models.errors import ErrorCode, ToolError

if not found:
    return ToolError.from_code(ErrorCode.RESERVATION_NOT_FOUND, 
                               details={"id": id}).model_dump()
```

## Environment Variables

### Backend (.env)
```
AWS_REGION, DYNAMODB_*_TABLE, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID, BEDROCK_MODEL_ID
```

### Frontend (.env.local)
```
NEXT_PUBLIC_AWS_REGION, NEXT_PUBLIC_COGNITO_IDENTITY_POOL_ID, NEXT_PUBLIC_AGENTCORE_RUNTIME_ARN
```

## Key Constraints

- Single property, max 4 guests
- Minimum nights vary by season
- Payment via Stripe Checkout
- Email verification required for bookings

## References

- Constitution: `.specify/memory/constitution.md`
- Active spec: `specs/{current-feature}/`
- Data model: `specs/001-agent-booking-platform/data-model.md`

## Active Technologies
- Python 3.13+ (Lambda), TypeScript strict (E2E tests) + AWS Lambda, Cognito Custom Message Trigger, DynamoDB, Playwrigh (019-e2e-email-otp)
- DynamoDB (`verification_codes` table - already exists with TTL enabled) (019-e2e-email-otp)

## Recent Changes
- 019-e2e-email-otp: Added Python 3.13+ (Lambda), TypeScript strict (E2E tests) + AWS Lambda, Cognito Custom Message Trigger, DynamoDB, Playwrigh
