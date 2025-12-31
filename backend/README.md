# Quesada Apartment Booking Backend

Agent-First Vacation Rental Booking Platform - Backend powered by Strands Agents.

## Architecture

This backend uses a **UV workspace** with three packages:

| Package | Purpose | Entry Point |
|---------|---------|-------------|
| `shared` | Models, services, tools | `from shared.models import ...` |
| `api` | FastAPI REST endpoints | `api.main:app` |
| `agent` | Strands agent definition | `agent.main:handler` |

## Setup

```bash
# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install all packages
uv sync

# Or install with dev dependencies
uv sync --dev
```

## Development

```bash
# Run API development server
uv run --package api uvicorn api.main:app --reload --port 3001

# Run tests (from workspace root)
uv run pytest

# Run linting
uv run ruff check .

# Run type checking
uv run mypy shared/src api/src agent/src
```

## Package Details

### `shared/` - Shared Components

Common code used by both `api` and `agent`:

```
shared/src/shared/
├── models/          # Pydantic data models
│   ├── auth.py
│   ├── guest.py
│   ├── reservation.py
│   └── ...
├── services/        # Business logic
│   ├── dynamodb.py
│   ├── booking.py
│   └── ...
├── tools/           # @tool decorated functions
│   ├── availability.py
│   ├── reservations.py
│   └── ...
└── utils/           # Utilities (JWT, etc.)
```

### `api/` - FastAPI REST API

Deployed to AWS Lambda via API Gateway:

```
api/src/api/
├── main.py          # FastAPI app + Mangum handler
├── routes/          # API routers (21 endpoints across 8 modules)
│   ├── health.py        # /health endpoint
│   ├── availability.py  # /availability, /availability/calendar/{month}
│   ├── pricing.py       # /pricing, /pricing/calculate, /pricing/rates, /pricing/minimum-stay
│   ├── reservations.py  # CRUD for reservations (JWT required for create/modify/delete)
│   ├── payments.py      # Payment processing (JWT required)
│   ├── guests.py        # Email verification, profile management
│   ├── property.py      # /property, /property/photos
│   └── area.py          # /area, /area/recommendations
├── models/          # Pydantic request/response models
├── middleware/      # Request/response middleware
└── scripts/         # OpenAPI generation
```

**API Authentication:**
- Public endpoints: availability, pricing, property, area info
- JWT required: create/modify/cancel reservations, payments, guest profile updates
- API Gateway validates JWT and passes user identity via `x-user-sub` header

### `agent/` - Strands Agent

Deployed to AgentCore Runtime:

```
agent/src/agent/
├── main.py          # Lambda handler
├── booking_agent.py # Agent definition
└── prompts/         # System prompts
    └── system_prompt.md
```

## Testing

```bash
# Run all tests
uv run pytest

# Run specific test type
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/contract/

# Run with coverage
uv run pytest --cov=shared --cov=api --cov=agent
```

## Infrastructure

The backend is deployed via Terraform:

- **API Lambda**: `infrastructure/modules/gateway-v2/` - FastAPI + API Gateway
- **Agent**: `infrastructure/main.tf` - AgentCore Runtime via `terraform-aws-agentcore`

See `task tf:apply:dev` in root `Taskfile.yaml` for deployment commands.
