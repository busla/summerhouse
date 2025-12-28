# Summerhouse: Agent-First Vacation Rental Booking Platform

Auto-generated from feature plans. Last updated: 2025-12-27

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
- **Framework**: Strands Agents (Python 3.12+)
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

# Backend
task backend:install  # Install Python deps with uv
task backend:dev      # Run FastAPI dev server on :3001
task backend:test     # Run pytest
task backend:lint     # Run ruff
task backend:typecheck # Run mypy

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
summerhouse/
├── Taskfile.yaml           # ⚠️ ALL terraform commands via this
├── CLAUDE.md               # This file
├── backend/
│   ├── src/
│   │   ├── agent/          # Strands agent definition
│   │   │   └── prompts/    # System prompts
│   │   ├── tools/          # @tool decorated functions
│   │   ├── models/         # Pydantic models
│   │   ├── services/       # Business logic
│   │   └── api/            # FastAPI endpoints
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── contract/
│   └── pyproject.toml
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
| `summerhouse-{env}-reservations` | Bookings | `reservation_id` | — |
| `summerhouse-{env}-guests` | Guest profiles | `guest_id` | — |
| `summerhouse-{env}-availability` | Date availability | `date` | — |
| `summerhouse-{env}-pricing` | Seasonal pricing | `season_id` | — |
| `summerhouse-{env}-payments` | Payment records | `payment_id` | — |
| `summerhouse-{env}-verification-codes` | Auth codes (TTL) | `email` | — |

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

## Environment Variables

### Backend (.env)
```
AWS_REGION=us-east-1
DYNAMODB_RESERVATIONS_TABLE=summerhouse-dev-reservations
DYNAMODB_GUESTS_TABLE=summerhouse-dev-guests
COGNITO_USER_POOL_ID=us-east-1_xxxxx
COGNITO_CLIENT_ID=xxxxx
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514
LOG_LEVEL=INFO
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:3001/api
NEXT_PUBLIC_COGNITO_USER_POOL_ID=us-east-1_xxxxx
NEXT_PUBLIC_COGNITO_CLIENT_ID=xxxxx
NEXT_PUBLIC_COGNITO_REGION=us-east-1
```

## Constitution Principles

This project follows the Summerhouse Constitution (v1.1.0):

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
