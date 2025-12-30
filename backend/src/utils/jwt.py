"""JWT utility functions for extracting user identity from tokens.

T032: Provides a simple utility for backend tools to extract the cognito_sub
(user identifier) from JWT tokens passed in the request payload.

Architecture Note:
- Tokens are passed in the request payload as `auth_token` (not headers)
- We decode the JWT payload without signature verification
- Signature verification was already done by Cognito during authentication
- The `sub` claim contains the Cognito user ID (cognito_sub)
"""

import base64
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_cognito_sub(auth_token: str | None) -> str | None:
    """Extract the Cognito sub (user ID) from a JWT auth token.

    This is a lightweight extraction that decodes the JWT payload without
    signature verification. The token has already been validated by Cognito
    during the authentication flow.

    Args:
        auth_token: JWT token from the request payload's `auth_token` field.
                   Can be an ID token or access token (both contain `sub`).

    Returns:
        The Cognito sub (user identifier) if extraction succeeds, None otherwise.

    Example:
        >>> sub = extract_cognito_sub(request_payload.get("auth_token"))
        >>> if sub:
        ...     guest = db.get_guest_by_cognito_sub(sub)
    """
    if not auth_token:
        return None

    try:
        # JWT format: header.payload.signature
        parts = auth_token.split(".")
        if len(parts) != 3:
            logger.debug("Invalid JWT format: expected 3 parts, got %d", len(parts))
            return None

        # Decode the payload (middle part)
        payload_b64 = parts[1]

        # Add padding if needed (base64url requires padding to be multiple of 4)
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        payload_json = base64.urlsafe_b64decode(payload_b64)
        payload: dict[str, Any] = json.loads(payload_json)

        # Extract the sub claim
        cognito_sub = payload.get("sub")
        if cognito_sub:
            logger.debug("Extracted cognito_sub from token")
            return str(cognito_sub)

        logger.debug("No 'sub' claim found in token payload")
        return None

    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Failed to extract cognito_sub from token: %s", type(e).__name__)
        return None


def decode_jwt_payload(token: str) -> dict[str, Any] | None:
    """Decode a JWT token and return the full payload.

    Similar to extract_cognito_sub but returns all claims.
    Useful for debugging or when multiple claims are needed.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dict or None if decoding fails
    """
    if not token:
        return None

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        payload_json = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_json)

    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
