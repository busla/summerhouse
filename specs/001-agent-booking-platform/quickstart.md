# Quickstart Guide: Booking Platform

**Feature**: 001-agent-booking-platform
**Date**: 2025-12-27

## Prerequisites

### Required Tools

| Tool | Version | Installation |
|------|---------|--------------|
| Node.js | 20+ | `brew install node` or [nodejs.org](https://nodejs.org) |
| Python | 3.12+ | `brew install python@3.12` or [python.org](https://python.org) |
| Terraform | 1.5+ | `brew install terraform` |
| Task | 3.x | `brew install go-task` or [taskfile.dev](https://taskfile.dev) |
| AWS CLI | 2.x | `brew install awscli` |
| Yarn | 4.x (Berry) | `corepack enable && corepack prepare yarn@stable --activate` |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### AWS Account Setup

1. **AWS Account** with permissions for:
   - DynamoDB (tables, indexes)
   - Cognito (user pools, custom auth)
   - Lambda (Cognito triggers)
   - S3 (frontend hosting, static content)
   - CloudFront (CDN)
   - AgentCore Runtime (agent deployment)

2. **AWS CLI Configuration**:
   ```bash
   aws configure
   # Or use SSO:
   aws configure sso
   ```

3. **Stripe Account** (for payment processing):
   - Sign up at [stripe.com](https://stripe.com)
   - Get API keys from Dashboard → Developers → API keys
   - Both test and live keys needed for dev/prod environments

4. **Bedrock Model Access**:
   - Enable Claude Sonnet in AWS Bedrock console
   - Region: us-east-1 (or your preferred region)

## Project Setup

### 1. Clone and Initialize

```bash
# Clone the repository
git clone https://github.com/your-org/booking.git
cd booking

# Create feature branch
git checkout -b 001-agent-booking-platform
```

### 2. Backend Setup (Python/Strands)

```bash
cd backend

# Install all workspace packages with uv sync
uv sync --dev

# Verify installation (UV creates .venv automatically)
uv run python -c "from strands import Agent; print('Strands OK')"
uv run python -c "from shared.models import Reservation; print('Shared package OK')"
uv run python -c "from api.main import app; print('API package OK')"
```

**Environment Variables** (`backend/.env`):
```env
# AWS Configuration
AWS_REGION=us-east-1
AWS_PROFILE=your-profile  # Optional if using default

# DynamoDB Tables (set by Terraform)
DYNAMODB_RESERVATIONS_TABLE=booking-dev-reservations
DYNAMODB_GUESTS_TABLE=booking-dev-guests
DYNAMODB_AVAILABILITY_TABLE=booking-dev-availability
DYNAMODB_PRICING_TABLE=booking-dev-pricing
DYNAMODB_PAYMENTS_TABLE=booking-dev-payments

# Cognito (set by Terraform)
COGNITO_USER_POOL_ID=us-east-1_xxxxx
COGNITO_CLIENT_ID=xxxxx

# Agent Configuration
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514
LOG_LEVEL=INFO
```

### 3. Frontend Setup (Next.js/Vercel AI SDK)

```bash
cd frontend

# Yarn Berry should already be initialized with nodeLinker: node-modules
# If not, initialize with:
# yarn init -2
# Then add to .yarnrc.yml: nodeLinker: node-modules

# Install dependencies
yarn install

# Verify AI SDK installation
yarn tsc --noEmit
```

**Environment Variables** (`frontend/.env.local`):
```env
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:3001/api

# Cognito (for client-side auth)
NEXT_PUBLIC_COGNITO_USER_POOL_ID=us-east-1_xxxxx
NEXT_PUBLIC_COGNITO_CLIENT_ID=xxxxx
NEXT_PUBLIC_COGNITO_REGION=us-east-1
```

### 4. Infrastructure Setup (Terraform via Taskfile)

> ⚠️ **IMPORTANT**: All Terraform commands MUST be run via `Taskfile.yaml` in repo root. Never run `terraform` directly.

```bash
# From repo root (not infrastructure/)

# Initialize Terraform for dev environment
task tf:init:dev

# Review the plan
task tf:plan:dev

# Apply infrastructure (creates DynamoDB tables, Cognito, etc.)
task tf:apply:dev
```

**Note**: The terraform-aws-agentcore module path is configured via environment variable:
```bash
export TF_VAR_agentcore_module_path="${HOME}/code/apro/agentcore-sandbox/terraform-aws-agentcore"
```
Or set in `infrastructure/environments/dev.tfvars` / `prod.tfvars` as `agentcore_module_path`.

**Available Taskfile Commands** (syntax: `task tf:<action>:<env>`):
| Command | Description |
|---------|-------------|
| `task tf:init:<env>` | Initialize Terraform with backend config |
| `task tf:plan:<env>` | Generate and show execution plan |
| `task tf:apply:<env>` | Apply infrastructure changes |
| `task tf:destroy:<env>` | Destroy infrastructure (use with caution) |
| `task tf:output:<env>` | Show Terraform outputs |

**Examples**: `task tf:plan:dev`, `task tf:apply:prod`

### 5. Stripe Payment Setup

Stripe API credentials are stored securely in AWS SSM Parameter Store.

**Store Stripe API Keys in SSM**:
```bash
# Development environment
aws ssm put-parameter \
  --name "/booking/dev/stripe/secret_key" \
  --type "SecureString" \
  --value "sk_test_your_test_secret_key" \
  --description "Stripe test secret key for dev"

aws ssm put-parameter \
  --name "/booking/dev/stripe/webhook_secret" \
  --type "SecureString" \
  --value "whsec_your_webhook_signing_secret" \
  --description "Stripe webhook signing secret for dev"

# Production environment (use live keys)
aws ssm put-parameter \
  --name "/booking/prod/stripe/secret_key" \
  --type "SecureString" \
  --value "sk_live_your_live_secret_key" \
  --description "Stripe live secret key for prod"

aws ssm put-parameter \
  --name "/booking/prod/stripe/webhook_secret" \
  --type "SecureString" \
  --value "whsec_your_prod_webhook_secret" \
  --description "Stripe webhook signing secret for prod"
```

**Configure Stripe Webhook** (after deployment):
1. Go to Stripe Dashboard → Developers → Webhooks
2. Add endpoint: `https://your-api-domain/webhooks/stripe`
3. Select events:
   - `checkout.session.completed`
   - `checkout.session.expired`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `charge.refunded`
4. Copy the webhook signing secret to SSM (as shown above)

**Verify SSM Parameters**:
```bash
# List stored parameters (values are encrypted)
aws ssm get-parameters-by-path \
  --path "/booking/dev/stripe" \
  --with-decryption
```

## Running Locally

### Start Backend (Development Mode)

```bash
cd backend

# Run API with hot reload (UV workspace)
uv run --package api uvicorn api.main:app --reload --port 3001

# Or run agent directly for testing (interactive CLI mode)
uv run --package agent python -m agent.booking_agent --interactive
```

**Note**: The FastAPI `app` is defined in `backend/api/src/api/main.py`. The `api.routes.health` module provides the health check endpoint.

### Start Frontend (Development Mode)

```bash
cd frontend

# Start Next.js dev server
yarn dev

# Opens http://localhost:3000
```

### Local Development Stack

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | Next.js app with chat interface |
| Backend API | http://localhost:3001 | Strands agent API |
| DynamoDB | AWS (remote) | Uses dev tables |

## Running Tests

### Backend Tests

```bash
cd backend

# Run all tests (UV handles venv automatically)
uv run pytest

# Run with coverage (covers all workspace packages)
uv run pytest --cov=shared --cov=api --cov=agent --cov-report=html

# Run specific test categories
uv run pytest tests/unit/           # Unit tests only
uv run pytest tests/integration/    # Integration tests
uv run pytest tests/contract/       # Contract tests

# Run tests matching pattern
uv run pytest -k "test_availability"
```

### Frontend Tests

```bash
cd frontend

# Run unit tests
yarn test

# Run with watch mode
yarn test:watch

# Run with coverage
yarn test:coverage

# Run E2E tests (requires running backend)
yarn test:e2e
```

### Test Categories

| Category | Location | Purpose | Requires |
|----------|----------|---------|----------|
| Unit (Backend) | `backend/tests/unit/` | Test individual tools, services | None |
| Unit (Frontend) | `frontend/tests/unit/` | Test components, hooks | None |
| Integration | `backend/tests/integration/` | Test tool + DynamoDB | AWS credentials |
| Contract | `backend/tests/contract/` | Verify API schemas | None |
| E2E | `frontend/tests/e2e/` | Full user flows | Running backend |

## Deployment

### Deploy Infrastructure

> ⚠️ **IMPORTANT**: All Terraform commands MUST be run via `Taskfile.yaml`. Never run `terraform` directly.

```bash
# From repo root

# Production deployment
task tf:plan:prod
task tf:apply:prod
```

### Deploy Backend (AgentCore Runtime)

```bash
cd backend

# Build Docker image
docker build -t booking-agent:latest .

# Push to ECR (set by Terraform)
aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REPO
docker tag booking-agent:latest $ECR_REPO:latest
docker push $ECR_REPO:latest

# Deploy to AgentCore (via Terraform or CLI)
# The terraform-aws-agentcore module handles this
```

### Deploy Frontend

Frontend deployment is **fully managed by Terraform**—no manual CLI commands.

```bash
# From repo root - frontend build and S3 sync happen automatically via terraform_data
task tf:apply:prod

# The static-website module handles:
# 1. Building frontend (yarn build)
# 2. Syncing to S3 (aws s3 sync)
# 3. NO CloudFront invalidation needed (content-hash filenames ensure cache-busting)
```

**Note**: CloudFront uses aggressive caching with long TTLs. Cache invalidation is NEVER required because Next.js exports artifacts with content-hash filenames (e.g., `main-abc123.js`). When content changes, filenames change, and users get fresh content automatically.

## Common Tasks

### Seed Test Data

```bash
cd backend
uv run python scripts/seed_data.py --env dev

# Seeds:
# - 2 years of availability dates
# - Seasonal pricing
# - Sample property/area info
```

### Reset DynamoDB Tables

```bash
# WARNING: Deletes all data!
cd backend
uv run python scripts/reset_tables.py --env dev --confirm
```

### View Agent Logs

```bash
# Local development
tail -f backend/logs/agent.log

# AgentCore Runtime (production)
aws logs tail /aws/agentcore/booking-prod --follow
```

### Test Agent Conversation

```bash
cd backend
uv run --package agent python -m agent.booking_agent --interactive

# Or use curl
curl -X POST http://localhost:3001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Is the apartment available in July?"}]}'
```

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError: strands` | UV not synced | Run `uv sync` in backend/ |
| `ModuleNotFoundError: shared` | UV workspace not synced | Run `uv sync --dev` in backend/ |
| `AccessDenied` on DynamoDB | Missing IAM permissions | Check AWS credentials/role |
| `Cognito: User pool not found` | Wrong pool ID or region | Verify `COGNITO_USER_POOL_ID` |
| `Bedrock: Model not accessible` | Model not enabled | Enable in Bedrock console |
| `CORS error` in browser | Frontend/backend URL mismatch | Check `NEXT_PUBLIC_API_URL` |
| `Rate limit exceeded` | Too many Cognito requests | Wait or increase Cognito limits |
| `Yarn: command not found` | Corepack not enabled | `corepack enable` |
| `Yarn PnP errors` | nodeLinker not set | Add `nodeLinker: node-modules` to `.yarnrc.yml` |
| `Stripe: Invalid API key` | SSM parameter missing/wrong | Verify `/booking/{env}/stripe/secret_key` in SSM |
| `Stripe: Invalid webhook signature` | Wrong signing secret | Check `/booking/{env}/stripe/webhook_secret` in SSM |
| `Payment failed: card_declined` | Test card not accepted | Use Stripe test card `4242 4242 4242 4242` |

### Debug Mode

```bash
# Backend verbose logging (UV workspace)
cd backend
LOG_LEVEL=DEBUG uv run --package api uvicorn api.main:app --reload

# Frontend verbose logging
DEBUG=* yarn dev
```

### Health Checks

```bash
# Backend health
curl http://localhost:3001/api/health

# DynamoDB connectivity
aws dynamodb describe-table --table-name booking-dev-reservations

# Cognito connectivity
aws cognito-idp describe-user-pool --user-pool-id $COGNITO_USER_POOL_ID
```

## Project Structure Reference

```
booking/
├── Taskfile.yaml            # ⚠️ ALL terraform commands via this (never manual)
├── backend/                 # UV workspace root
│   ├── pyproject.toml       # Workspace definition (members: agent, api, shared)
│   ├── shared/              # Shared components package
│   │   ├── pyproject.toml
│   │   └── src/shared/
│   │       ├── models/      # Pydantic data models
│   │       ├── services/    # Business logic (DynamoDB, booking, etc.)
│   │       ├── tools/       # @tool decorated functions
│   │       └── utils/       # Utilities (JWT, etc.)
│   ├── api/                 # FastAPI REST API package
│   │   ├── pyproject.toml
│   │   └── src/api/
│   │       ├── main.py      # FastAPI app + Mangum handler
│   │       ├── routes/      # API routers (auth, health)
│   │       └── middleware/  # Request/response middleware
│   ├── agent/               # Strands Agent package
│   │   ├── pyproject.toml
│   │   └── src/agent/
│   │       ├── main.py      # Lambda handler
│   │       ├── booking_agent.py
│   │       └── prompts/     # System prompts
│   └── tests/               # Tests (shared across packages)
├── frontend/
│   ├── .yarnrc.yml          # Yarn Berry config (nodeLinker: node-modules)
│   ├── src/
│   │   ├── app/             # Next.js App Router pages
│   │   ├── components/      # React components
│   │   └── lib/             # Utilities, providers
│   ├── tests/
│   └── package.json
├── infrastructure/
│   ├── main.tf              # Uses terraform-aws-agentcore + static-website
│   └── environments/        # tfvars + backend config per environment
└── specs/
    └── 001-agent-booking-platform/
        ├── spec.md          # Feature specification
        ├── plan.md          # Implementation plan
        ├── research.md      # Technology research
        ├── data-model.md    # DynamoDB schemas
        ├── quickstart.md    # This file
        └── contracts/       # API contracts
```

## Next Steps

After completing setup:

1. **Read the spec**: `specs/001-agent-booking-platform/spec.md`
2. **Review the plan**: `specs/001-agent-booking-platform/plan.md`
3. **Start with P1 User Story**: Availability & Pricing Inquiry
4. **Follow TDD**: Write tests first, then implement

## Resources

- [Vercel AI SDK Documentation](https://sdk.vercel.ai/docs)
- [Strands Agents Documentation](https://strandsagents.com/docs)
- [terraform-aws-agentcore README](~/code/apro/agentcore-sandbox/terraform-aws-agentcore/README.md)
- [AWS Cognito Custom Auth](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-lambda-challenge.html)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [Stripe Checkout Integration](https://stripe.com/docs/payments/checkout)
- [Stripe Webhooks](https://stripe.com/docs/webhooks)
- [Stripe Test Cards](https://stripe.com/docs/testing#cards)
