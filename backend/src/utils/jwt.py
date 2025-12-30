"""JWT utility functions for extracting user identity from tokens.

T032: Provides a simple utility for backend tools to extract the cognito_sub
(user identifier) from JWT tokens passed in the request payload.

Architecture Note:
- Tokens are passed in the request payload as `auth_token` (not headers)
- We decode the JWT payload without signature verification using PyJWT
- Signature verification was already done by Cognito during authentication
- The `sub` claim contains the Cognito user ID (cognito_sub)
"""

import logging
from typing import Any

import jwt

logger = logging.getLogger(__name__)


def decode_jwt_payload(token: str) -> dict[str, Any] | None:
    """Decode a JWT token and return the full payload using PyJWT.

    Decodes the JWT payload without signature verification.
    Signature was already verified by Cognito during authentication.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dict or None if decoding fails
    """
    if not token:
        return None

    try:
        # Decode without verification - Cognito already verified the signature
        return jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_iss": False,
                "verify_exp": False,
            },
        )
    except jwt.exceptions.DecodeError:
        logger.debug("Failed to decode JWT token")
        return None


def extract_cognito_claims(auth_token: str | None) -> tuple[str | None, str | None]:
    """Extract Cognito sub and email from a JWT auth token.

    This is a lightweight extraction that decodes the JWT payload without
    signature verification. The token has already been validated by Cognito
    during the authentication flow.

    Args:
        auth_token: JWT token from the request payload's `auth_token` field.
                   Must be an ID token (contains email claim).

    Returns:
        Tuple of (cognito_sub, email). Either or both may be None if extraction fails.

    Example:
        >>> sub, email = extract_cognito_claims(request_payload.get("auth_token"))
        >>> if sub:
        ...     guest = db.get_guest_by_cognito_sub(sub)
    """
    if not auth_token:
        return None, None

    payload = decode_jwt_payload(auth_token)
    if not payload:
        return None, None

    cognito_sub = payload.get("sub")
    email = payload.get("email")

    if cognito_sub:
        logger.debug("Extracted cognito_sub and email from token")
    else:
        logger.debug("No 'sub' claim found in token payload")

    return (str(cognito_sub) if cognito_sub else None, str(email) if email else None)


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
    sub, _ = extract_cognito_claims(auth_token)
    return sub
