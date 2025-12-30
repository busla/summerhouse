# Contract: Tool Responses with @requires_access_token

**Feature Branch**: `005-agentcore-amplify-oauth2`
**Date**: 2025-12-30

## Overview

This document defines the response formats for agent tools decorated with `@requires_access_token`. The decorator triggers AgentCore's OAuth2 flow when no valid token exists, returning an authorization URL to the agent.

---

## @requires_access_token Decorator

### Usage

```python
from bedrock_agentcore.identity import requires_access_token
from strands import tool

@tool
@requires_access_token(
    credential_provider_name="booking-dev-cognito",
    scopes=["openid", "email", "profile"]
)
def make_reservation(
    check_in_date: str,
    check_out_date: str,
    guest_count: int,
    access_token: str | None = None  # Injected by decorator
) -> dict:
    """Create a reservation for the authenticated guest."""
    if access_token is None:
        # This shouldn't happen - decorator handles auth flow
        raise ValueError("Access token required")

    # Tool implementation with authenticated context
    ...
```

### Decorator Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `credential_provider_name` | String | Yes | Name of OAuth2 credential provider |
| `scopes` | List[String] | No | OAuth2 scopes to request |
| `on_auth_url` | Callable | No | Callback when auth URL is generated |

---

## Response Scenarios

### Scenario 1: Authenticated Request (Token Valid)

When a valid token exists in AgentCore's Token Vault, the tool executes normally.

**Tool Response**:
```json
{
  "success": true,
  "reservation_id": "RES-2025-ABC123",
  "check_in_date": "2025-03-15",
  "check_out_date": "2025-03-20",
  "guest_count": 2,
  "total_price": 750.00,
  "status": "confirmed"
}
```

### Scenario 2: Unauthenticated Request (No Token)

When no valid token exists, the decorator triggers OAuth2 flow and returns an authorization URL.

**Tool Response** (via `on_auth_url` callback):
```json
{
  "requires_authentication": true,
  "authorization_url": "https://booking.example.com/login?session_id=abc123&custom_state=xyz789",
  "message": "Authentication required to complete your booking",
  "expires_in_seconds": 600
}
```

### Scenario 3: Token Expired (Refresh Failed)

When the token has expired and refresh fails, a new authorization URL is generated.

**Tool Response**:
```json
{
  "requires_authentication": true,
  "authorization_url": "https://booking.example.com/login?session_id=def456&custom_state=uvw012",
  "message": "Your session has expired. Please sign in again to continue.",
  "expires_in_seconds": 600
}
```

---

## Agent Prompt Handling

### System Prompt Update

The agent's system prompt must include instructions for handling authorization URLs:

```text
## Authentication Flow

When a protected tool returns `requires_authentication: true`:

1. Present the authorization URL to the user as a clickable link
2. Explain that they need to sign in to complete their booking
3. Wait for them to return after authentication
4. Once they send a new message, retry the original request

Example response:
"To complete your reservation, I need you to sign in first. Please click here to authenticate: [Sign In](authorization_url)

Once you've signed in, just let me know and I'll continue with your booking!"
```

### Agent Response Format

When receiving an authorization URL, the agent should respond:

```markdown
To complete your reservation for **March 15-20**, I need you to sign in first.

[Click here to sign in](https://booking.example.com/login?session_id=abc123)

Once you've completed the sign-in, just send me a message and I'll finalize your booking right away!
```

---

## Protected Tools

### List of Tools with @requires_access_token

| Tool | Purpose | Scopes Required |
|------|---------|-----------------|
| `make_reservation` | Create new booking | `openid`, `email` |
| `modify_reservation` | Update existing booking | `openid`, `email` |
| `cancel_reservation` | Cancel booking | `openid`, `email` |
| `get_my_reservations` | List user's bookings | `openid`, `email` |

### Implementation Pattern

The `access_token` parameter is a **guardrail** for the agent. The agent uses JWT claims to scope DynamoDB queries to user-specific data, preventing unauthorized access to other users' reservations.

```python
# backend/src/tools/reservation.py

from bedrock_agentcore.identity import requires_access_token
from strands import tool
from src.services.dynamodb import get_dynamodb_service

CREDENTIAL_PROVIDER = os.environ.get("AGENTCORE_CREDENTIAL_PROVIDER_NAME", "booking-dev-cognito")

@tool
@requires_access_token(credential_provider_name=CREDENTIAL_PROVIDER)
def make_reservation(
    check_in_date: str,
    check_out_date: str,
    guest_count: int,
    special_requests: str | None = None,
    access_token: str | None = None,  # Injected by decorator - GUARDRAIL
) -> dict:
    """Create a reservation for the authenticated guest.

    Args:
        check_in_date: Check-in date (YYYY-MM-DD format)
        check_out_date: Check-out date (YYYY-MM-DD format)
        guest_count: Number of guests (1-4)
        special_requests: Optional special requests
        access_token: Injected OAuth2 access token (do not pass manually)
                      Used as GUARDRAIL - agent extracts claims to scope queries

    Returns:
        Reservation confirmation or error details
    """
    # GUARDRAIL: Extract user identity from token claims
    # This ensures agent can ONLY access this user's data
    user_sub = _extract_sub_from_token(access_token)

    # Query scoped by user_sub - prevents access to other users' data
    db = get_dynamodb_service()
    guest = db.get_guest_by_cognito_sub(user_sub)  # Scoped query

    if not guest:
        # Create guest from token claims
        claims = _decode_token_claims(access_token)
        guest = db.create_guest(
            email=claims.get("email"),
            name=claims.get("name", "Guest"),
            cognito_sub=user_sub,  # Links to Cognito identity
        )

    # Create reservation linked to authenticated user
    reservation = db.create_reservation(
        guest_id=guest.guest_id,  # Tied to token's sub claim
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        guest_count=guest_count,
        special_requests=special_requests,
    )

    return {
        "success": True,
        "reservation_id": reservation.reservation_id,
        "check_in_date": reservation.check_in_date,
        "check_out_date": reservation.check_out_date,
        "guest_count": reservation.guest_count,
        "total_price": reservation.total_price,
        "status": reservation.status,
    }
```

**Security Note**: Without the `access_token` guardrail, a prompt injection attack could potentially trick the agent into querying another user's reservations. The JWT claims ensure authorization at the data layer.

---

## Removed Tool Responses (from Spec 004)

The following response formats are **no longer used**:

### TokenDeliveryEvent (REMOVED)

```json
// REMOVED - Do not use
{
  "event_type": "auth_tokens",
  "success": true,
  "id_token": "...",
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 3600
}
```

### OTP Challenge Response (REMOVED)

```json
// REMOVED - Do not use
{
  "success": true,
  "session_token": "...",
  "challenge": "EMAIL_OTP",
  "email": "user@example.com"
}
```

---

## Error Responses

### Standard Error Format

All protected tools use the standard `ToolError` format for errors:

```python
from src.models.errors import ErrorCode, ToolError

# Usage in tool
if not dates_available:
    error = ToolError.from_code(
        ErrorCode.DATES_UNAVAILABLE,
        details={"requested_dates": f"{check_in_date} to {check_out_date}"}
    )
    return error.model_dump()
```

### Error Response Schema

```json
{
  "success": false,
  "error_code": "ERR_001",
  "message": "The requested dates are not available",
  "recovery": "Please try different dates or ask about availability",
  "details": {
    "requested_dates": "2025-03-15 to 2025-03-20"
  }
}
```

### Error Codes for Protected Tools

| Code | Name | Description |
|------|------|-------------|
| `ERR_001` | `DATES_UNAVAILABLE` | Requested dates are already booked |
| `ERR_002` | `MINIMUM_NIGHTS_NOT_MET` | Stay is shorter than minimum |
| `ERR_003` | `MAX_GUESTS_EXCEEDED` | More than 4 guests |
| `ERR_006` | `RESERVATION_NOT_FOUND` | Reservation ID doesn't exist |
| `ERR_007` | `UNAUTHORIZED` | User can't access this reservation |

---

## on_auth_url Callback

### Callback Signature

```python
from typing import Callable

OnAuthUrlCallback = Callable[[str, dict], None]

def on_auth_url(authorization_url: str, context: dict) -> None:
    """Called when an authorization URL is generated.

    Args:
        authorization_url: The URL to present to the user
        context: Additional context (tool name, session_id, etc.)
    """
    pass
```

### Agent Integration

The Strands agent framework integrates with `on_auth_url` to stream the URL to the user:

```python
# backend/src/agent/agent.py

from strands import Agent
from bedrock_agentcore.identity import configure_auth_handler

def create_agent():
    agent = Agent(
        model="bedrock/anthropic.claude-sonnet-4-20250514",
        tools=[make_reservation, modify_reservation, ...],
    )

    # Configure auth URL handler
    configure_auth_handler(
        agent,
        on_auth_url=lambda url, ctx: agent.stream_message(
            f"requires_authentication: {url}"
        )
    )

    return agent
```

---

## Testing

### Unit Test: Auth Required Response

```python
def test_make_reservation_requires_auth_when_no_token():
    """Tool should return auth URL when no token exists."""
    # Mock AgentCore to return no token
    with mock_agentcore_no_token():
        result = make_reservation(
            check_in_date="2025-03-15",
            check_out_date="2025-03-20",
            guest_count=2,
        )

    assert result["requires_authentication"] is True
    assert "authorization_url" in result
    assert "session_id=" in result["authorization_url"]
```

### Unit Test: Authenticated Execution

```python
def test_make_reservation_with_valid_token():
    """Tool should execute when valid token is provided."""
    # Mock AgentCore with valid token
    with mock_agentcore_valid_token(sub="cognito-sub-123"):
        result = make_reservation(
            check_in_date="2025-03-15",
            check_out_date="2025-03-20",
            guest_count=2,
        )

    assert result["success"] is True
    assert "reservation_id" in result
```

### Integration Test: Full OAuth2 Flow

```python
@pytest.mark.integration
async def test_full_oauth2_flow():
    """Test complete auth flow from tool to callback."""
    # 1. Call protected tool (should return auth URL)
    # 2. Simulate user auth on Cognito
    # 3. Call CompleteResourceTokenAuth
    # 4. Call protected tool again (should succeed)
    pass
```
