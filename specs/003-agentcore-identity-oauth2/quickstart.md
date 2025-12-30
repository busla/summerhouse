# Quickstart Guide: AgentCore Identity OAuth2 Login

**Feature**: 003-agentcore-identity-oauth2
**Date**: 2025-12-29
**Prerequisite**: Feature 001 (agent-booking-platform) must be deployed

> **Note**: This guide provides implementation steps. For authoritative technical context (API patterns, SDK usage, Cognito configuration), see [spec.md](./spec.md#technical-context).

## Prerequisites

### Additional Dependencies

This feature adds the following dependencies to the existing platform:

| Component | Addition | Purpose |
|-----------|----------|---------|
| Backend | `bedrock-agentcore` | AgentCore Identity SDK |
| Backend | `boto3-stubs[cognito-idp]` | Type hints for Cognito |
| Infrastructure | Cognito Essentials tier | Required for EMAIL_OTP |
| Infrastructure | OAuth2 Sessions DynamoDB table | Session state storage |

### Cognito Essentials Tier

> ⚠️ **IMPORTANT**: EMAIL_OTP passwordless authentication requires **Cognito Essentials tier**.
>
> Cognito Essentials is a paid tier. Review [Cognito pricing](https://aws.amazon.com/cognito/pricing/) before proceeding.

## Configuration Changes

### Backend Environment Variables (Terraform-Managed)

> **IMPORTANT**: Per FR-017, all configuration values from `terraform-aws-agentcore` module outputs MUST be wired through Terraform to dependent modules. Do NOT manually add these to `.env` files.

The `gateway-v2` module receives these as input variables from parent Terraform configuration:

```hcl
# infrastructure/main.tf - Module output wiring (NOT .env files)
module "gateway_v2" {
  source = "./modules/gateway-v2"

  # Wired from terraform-aws-agentcore outputs
  agentcore_identity_provider_name = module.agentcore.identity_provider_name
  oauth2_callback_url              = module.agentcore.oauth2_callback_url
  dynamodb_oauth2_sessions_table   = module.agentcore.oauth2_sessions_table_name

  # ... other configuration
}
```

The Lambda function receives these as environment variables from the Terraform module (NOT from `.env` files):

| Variable | Source | Description |
|----------|--------|-------------|
| `AGENTCORE_IDENTITY_PROVIDER_NAME` | `module.agentcore.identity_provider_name` | AgentCore Identity provider |
| `OAUTH2_CALLBACK_URL` | API Gateway invoke URL + `/api/auth/callback` | OAuth2 redirect URI |
| `DYNAMODB_OAUTH2_SESSIONS_TABLE` | `module.agentcore.oauth2_sessions_table_name` | Session storage table |

### Infrastructure Updates

The Cognito module requires updates for EMAIL_OTP:

```hcl
# infrastructure/modules/cognito-passwordless/variables.tf additions

variable "user_pool_tier" {
  description = "Cognito User Pool tier (LITE or ESSENTIALS)"
  type        = string
  default     = "ESSENTIALS"  # Required for EMAIL_OTP
}

variable "allowed_first_auth_factors" {
  description = "Allowed first authentication factors"
  type        = list(string)
  default     = ["EMAIL_OTP"]
}
```

## Implementation Steps

### Step 1: Update Backend Dependencies

```bash
cd backend

# Add bedrock-agentcore to pyproject.toml dependencies
# (Already listed in Feature 001, verify it's installed)
uv pip install bedrock-agentcore boto3-stubs[cognito-idp]

# Verify installation
python -c "from bedrock_agentcore.services.identity import IdentityClient; print('AgentCore Identity OK')"
```

### Step 2: Deploy Infrastructure Updates

```bash
# From repo root (all terraform via Taskfile)

# Review changes (should show Cognito tier update + new OAuth2 sessions table)
task tf:plan:dev

# Apply infrastructure
task tf:apply:dev
```

**Expected Changes**:
- Cognito User Pool updated to Essentials tier
- New DynamoDB table: `booking-dev-oauth2-sessions`
- New GSI on guests table: `cognito-sub-index`
- New `gateway-v2` module: FastAPI Lambda + API Gateway HTTP API
- CloudFront updated with API Gateway origin and `/api` path routing

### Step 3: AgentCore Identity Provider (Terraform-Managed)

> **Note**: The `terraform-aws-agentcore` module automatically configures Cognito as an OAuth2 provider in AgentCore Identity. **No manual CLI commands required.**

The module creates the credential provider and exposes outputs for dependent modules:

```hcl
# terraform-aws-agentcore module outputs (automatically configured)
output "identity_provider_name" {
  description = "AgentCore Identity credential provider name"
  value       = aws_agentcore_credential_provider.cognito.name
}

output "oauth2_callback_url" {
  description = "AgentCore OAuth2 callback URL"
  value       = aws_agentcore_credential_provider.cognito.callback_url
}

output "cognito_client_id" {
  description = "Cognito User Pool Client ID"
  value       = aws_cognito_user_pool_client.agent.id
}
```

These outputs are then wired to the `gateway-v2` module as shown in the Configuration Changes section above.

### Step 4: Create Auth Service

Create `backend/src/services/auth_service.py`:

```python
"""Authentication service for Cognito passwordless login."""

import os
from datetime import datetime, timedelta

import boto3
from pydantic import BaseModel, ConfigDict

from src.models.guest import Guest
from src.services.dynamodb import get_dynamodb_service


class CognitoAuthState(BaseModel):
    """Tracks Cognito USER_AUTH flow state."""

    model_config = ConfigDict(strict=True)

    session: str
    username: str
    challenge: str = "EMAIL_OTP"
    otp_sent_at: datetime


class AuthResult(BaseModel):
    """Result of OTP verification."""

    model_config = ConfigDict(strict=True)

    success: bool
    guest: Guest | None = None
    error_code: str | None = None
    message: str


class AuthService:
    """Handles Cognito passwordless authentication."""

    def __init__(self) -> None:
        self.cognito = boto3.client("cognito-idp")
        self.user_pool_id = os.environ["COGNITO_USER_POOL_ID"]
        self.client_id = os.environ["COGNITO_CLIENT_ID"]
        self.db = get_dynamodb_service()

    async def initiate_passwordless_auth(self, email: str) -> CognitoAuthState:
        """Start Cognito USER_AUTH flow with EMAIL_OTP."""
        response = self.cognito.initiate_auth(
            AuthFlow="USER_AUTH",
            ClientId=self.client_id,
            AuthParameters={
                "USERNAME": email,
                "PreferredChallenge": "EMAIL_OTP",
            },
        )

        return CognitoAuthState(
            session=response["Session"],
            username=email,
            challenge=response.get("ChallengeName", "EMAIL_OTP"),
            otp_sent_at=datetime.utcnow(),
        )

    async def verify_otp(
        self, email: str, otp_code: str, session: str
    ) -> AuthResult:
        """Verify OTP and complete authentication."""
        try:
            response = self.cognito.respond_to_auth_challenge(
                ClientId=self.client_id,
                ChallengeName="EMAIL_OTP",
                Session=session,
                ChallengeResponses={
                    "USERNAME": email,
                    "EMAIL_OTP_CODE": otp_code,
                },
            )

            if "AuthenticationResult" in response:
                # Extract Cognito sub from ID token
                id_token = response["AuthenticationResult"]["IdToken"]
                cognito_sub = self._extract_sub_from_token(id_token)

                # Get or create guest
                guest = await self.get_or_create_guest(cognito_sub, email)

                return AuthResult(success=True, guest=guest, message="Authentication successful")

            return AuthResult(
                success=False,
                error_code="UNEXPECTED_RESPONSE",
                message="Unexpected response from Cognito",
            )

        except self.cognito.exceptions.CodeMismatchException:
            return AuthResult(
                success=False,
                error_code="INVALID_OTP",
                message="The verification code is incorrect",
            )
        except self.cognito.exceptions.ExpiredCodeException:
            return AuthResult(
                success=False,
                error_code="OTP_EXPIRED",
                message="The verification code has expired",
            )

    async def get_or_create_guest(self, cognito_sub: str, email: str) -> Guest:
        """Get existing guest by Cognito sub or create new one."""
        # Try to find by cognito_sub first
        existing = await self.db.get_guest_by_cognito_sub(cognito_sub)
        if existing:
            return existing

        # Try by email
        existing = await self.db.get_guest_by_email(email)
        if existing:
            # Bind cognito_sub to existing guest
            existing.cognito_sub = cognito_sub
            await self.db.update_guest(existing)
            return existing

        # Create new guest
        return await self.db.create_guest(
            email=email,
            cognito_sub=cognito_sub,
            email_verified=True,
        )

    def _extract_sub_from_token(self, id_token: str) -> str:
        """Extract 'sub' claim from JWT ID token."""
        import base64
        import json

        # JWT is base64url encoded, split by dots
        payload = id_token.split(".")[1]
        # Add padding if needed
        payload += "=" * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded)
        return claims["sub"]
```

### Step 5: Create Auth Tools

Create `backend/src/tools/auth.py`:

```python
"""Authentication tools for Strands agent."""

import os
from typing import Any

from bedrock_agentcore.identity import requires_access_token
from strands import tool

from src.models.errors import ErrorCode, ToolError
from src.services.auth_service import AuthService


def _get_auth_service() -> AuthService:
    """Get shared AuthService instance."""
    # Consider using a singleton pattern like DynamoDB service
    return AuthService()


def stream_auth_url_to_client(auth_url: str) -> None:
    """Callback to stream authorization URL to guest via agent.

    This is called by the @requires_access_token decorator when
    the guest needs to authenticate. The URL will be rendered as
    a clickable hyperlink within the chat message bubble.
    """
    # The Strands agent framework handles streaming this to the chat
    # Frontend renders as clickable link: <a href="{auth_url}">Sign in</a>
    pass  # Implementation depends on Strands streaming API


@tool
async def initiate_cognito_login(email: str) -> dict[str, Any]:
    """
    Start passwordless EMAIL_OTP login flow.

    Sends a 6-digit verification code to the guest's email address.
    The code is valid for 5 minutes.

    Args:
        email: Guest's email address

    Returns:
        Result containing session_token for OTP verification
    """
    auth_service = _get_auth_service()

    try:
        state = await auth_service.initiate_passwordless_auth(email)
        return {
            "success": True,
            "session_token": state.session,
            "message": f"A verification code has been sent to {email}. Please enter the 6-digit code.",
            "expires_in_seconds": 300,  # 5 minutes
        }
    except Exception as e:
        error = ToolError.from_code(
            ErrorCode.EMAIL_DELIVERY_FAILED,
            details={"email": email, "error": str(e)},
        )
        return error.model_dump()


@tool
async def verify_cognito_otp(
    email: str, otp_code: str, session_token: str
) -> dict[str, Any]:
    """
    Verify the OTP code to complete authentication.

    Args:
        email: Guest's email address
        otp_code: 6-digit verification code from email
        session_token: Session token from initiate_cognito_login

    Returns:
        Result containing guest_id if successful
    """
    auth_service = _get_auth_service()

    result = await auth_service.verify_otp(email, otp_code, session_token)

    if result.success and result.guest:
        return {
            "success": True,
            "guest_id": result.guest.guest_id,
            "message": f"Welcome! You are now signed in as {result.guest.email}",
        }

    # Map error codes to ToolError
    error_map = {
        "INVALID_OTP": ErrorCode.VERIFICATION_FAILED,
        "OTP_EXPIRED": ErrorCode.VERIFICATION_FAILED,
    }

    error_code = error_map.get(result.error_code or "", ErrorCode.VERIFICATION_FAILED)
    error = ToolError.from_code(error_code, details={"message": result.message})
    return error.model_dump()


@tool
@requires_access_token(
    provider_name=os.getenv("AGENTCORE_IDENTITY_PROVIDER_NAME", "CognitoIdentityProvider"),
    scopes=["openid", "email"],
    auth_flow="USER_FEDERATION",
    on_auth_url=stream_auth_url_to_client,
    callback_url=os.getenv("OAUTH2_CALLBACK_URL", ""),
)
async def get_authenticated_guest(*, access_token: str) -> dict[str, Any]:
    """
    Get the currently authenticated guest's profile.

    If not authenticated, triggers OAuth2 login flow automatically.
    The access_token parameter is injected by the decorator.

    Returns:
        Guest profile information
    """
    # Decode the access token to get guest identity
    auth_service = _get_auth_service()
    cognito_sub = auth_service._extract_sub_from_token(access_token)

    guest = await auth_service.db.get_guest_by_cognito_sub(cognito_sub)

    if not guest:
        error = ToolError.from_code(ErrorCode.UNAUTHORIZED)
        return error.model_dump()

    return {
        "success": True,
        "guest_id": guest.guest_id,
        "email": guest.email,
        "name": guest.name,
        "email_verified": guest.email_verified,
    }
```

### Step 6: Create OAuth2 Callback Endpoint

Create `backend/src/api/auth.py`:

```python
"""OAuth2 callback endpoint."""

import os
from urllib.parse import urlencode

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from src.services.identity_client import AgentCoreIdentityService

router = APIRouter(prefix="/auth", tags=["OAuth2"])


@router.get("/callback")
async def oauth2_callback(
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="OAuth2 state parameter"),
    error: str | None = Query(None, description="Error code"),
    error_description: str | None = Query(None, description="Error description"),
) -> RedirectResponse:
    """
    Handle OAuth2 authorization callback from Cognito.

    Exchanges the authorization code for tokens and binds them
    to the correct agent conversation via session state.
    """
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Handle error from Cognito
    if error:
        params = urlencode({"auth": "error", "message": error_description or error})
        return RedirectResponse(url=f"{frontend_url}/?{params}")

    try:
        identity_service = AgentCoreIdentityService()

        # Complete token exchange
        result = await identity_service.complete_oauth2(
            state=state,
            auth_code=code,
        )

        if result.success:
            params = urlencode({
                "auth": "success",
                "session_id": result.session_id,
            })
        else:
            params = urlencode({
                "auth": "error",
                "message": result.error_message,
            })

        return RedirectResponse(url=f"{frontend_url}/?{params}")

    except Exception as e:
        params = urlencode({"auth": "error", "message": str(e)})
        return RedirectResponse(url=f"{frontend_url}/?{params}")


@router.get("/session/{session_id}")
async def get_session_status(session_id: str) -> dict:
    """
    Check OAuth2 session status.

    Used by frontend to poll for authentication completion.
    """
    identity_service = AgentCoreIdentityService()
    session = await identity_service.get_session(session_id)

    if not session:
        return {"error": "session_not_found", "message": "Session not found or expired"}

    return {
        "session_id": session.session_id,
        "status": session.status.value,
        "created_at": session.created_at.isoformat(),
        "expires_at": session.expires_at,
    }
```

### Step 7: Register Auth Tools with Agent

Update `backend/src/agent/booking_agent.py`:

```python
from src.tools.auth import (
    initiate_cognito_login,
    verify_cognito_otp,
    get_authenticated_guest,
)

# Add to agent tool list
AGENT_TOOLS = [
    # Existing tools...
    initiate_cognito_login,
    verify_cognito_otp,
    get_authenticated_guest,
]
```

## Testing

### Unit Tests

Create `backend/tests/unit/test_auth_service.py`:

```python
"""Unit tests for authentication service."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.services.auth_service import AuthService, CognitoAuthState, AuthResult


@pytest.fixture
def auth_service():
    with patch.dict("os.environ", {
        "COGNITO_USER_POOL_ID": "test-pool",
        "COGNITO_CLIENT_ID": "test-client",
    }):
        with patch("boto3.client"):
            yield AuthService()


@pytest.mark.unit
async def test_initiate_passwordless_auth(auth_service):
    """Test initiating EMAIL_OTP flow."""
    auth_service.cognito.initiate_auth.return_value = {
        "Session": "test-session-token",
        "ChallengeName": "EMAIL_OTP",
    }

    state = await auth_service.initiate_passwordless_auth("guest@example.com")

    assert state.session == "test-session-token"
    assert state.username == "guest@example.com"
    assert state.challenge == "EMAIL_OTP"


@pytest.mark.unit
async def test_verify_otp_success(auth_service):
    """Test successful OTP verification."""
    # Mock successful response with tokens
    auth_service.cognito.respond_to_auth_challenge.return_value = {
        "AuthenticationResult": {
            "IdToken": "eyJ...",  # Mock JWT
            "AccessToken": "access...",
            "RefreshToken": "refresh...",
        }
    }

    # Mock guest lookup/creation
    with patch.object(auth_service, "get_or_create_guest") as mock_guest:
        mock_guest.return_value = MagicMock(guest_id="guest-123", email="guest@example.com")

        result = await auth_service.verify_otp(
            email="guest@example.com",
            otp_code="123456",
            session="session-token",
        )

    assert result.success is True
    assert result.guest is not None
```

### Integration Tests

Create `backend/tests/integration/test_cognito_flow.py`:

```python
"""Integration tests for Cognito authentication flow."""

import pytest
from moto import mock_aws

from src.services.auth_service import AuthService


@pytest.fixture
def cognito_user_pool():
    """Create mock Cognito user pool."""
    with mock_aws():
        import boto3

        client = boto3.client("cognito-idp", region_name="us-east-1")

        # Create user pool
        response = client.create_user_pool(
            PoolName="test-pool",
            # Note: moto may not fully support Essentials tier/EMAIL_OTP
            # These tests verify the service logic, not full Cognito behavior
        )

        pool_id = response["UserPool"]["Id"]

        # Create app client
        client_response = client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName="test-client",
        )

        yield {
            "pool_id": pool_id,
            "client_id": client_response["UserPoolClient"]["ClientId"],
        }


@pytest.mark.integration
async def test_full_auth_flow(cognito_user_pool):
    """Test complete authentication flow."""
    # Note: Full EMAIL_OTP testing requires real Cognito
    # or more sophisticated mocking
    pass
```

### Manual Testing

```bash
# Start backend
cd backend && python -m uvicorn src.api:app --reload --port 3001

# Test initiate login (via agent conversation)
curl -X POST http://localhost:3001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "I want to book the apartment. My email is test@example.com"}]}'

# Check your email for OTP code, then continue conversation with code
```

## Deployment Checklist

- [ ] Cognito User Pool upgraded to Essentials tier
- [ ] EMAIL_OTP enabled in `AllowedFirstAuthFactors`
- [ ] OAuth2 sessions DynamoDB table created
- [ ] GSI `cognito-sub-index` added to guests table
- [ ] AgentCore Identity provider configured
- [ ] `OAUTH2_CALLBACK_URL` environment variable set
- [ ] Auth router registered in FastAPI app
- [ ] Auth tools registered with Strands agent

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `EMAIL_OTP not available` | Cognito Lite tier | Upgrade to Cognito Essentials |
| `User pool not found` | Wrong pool ID | Verify `COGNITO_USER_POOL_ID` |
| `InvalidParameterException: PreferredChallenge` | Old Cognito API version | Update boto3 to latest |
| `IdentityClient not found` | Missing bedrock-agentcore | `uv pip install bedrock-agentcore` |
| `OAuth2 state mismatch` | Session expired or CSRF | Restart authentication flow |
| `Callback URL mismatch` | Cognito client config | Update allowed callback URLs |

## Resources

- [AgentCore Identity Documentation](https://awslabs.github.io/agents/bedrock-agentcore/user-guide/identity/)
- [Cognito USER_AUTH Flow](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-authentication-flow-methods.html)
- [Cognito Essentials Pricing](https://aws.amazon.com/cognito/pricing/)
- [OAuth2 PKCE RFC 7636](https://datatracker.ietf.org/doc/html/rfc7636)
