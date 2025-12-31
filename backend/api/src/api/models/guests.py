"""API models for guest endpoints.

Extends shared guest models with API-specific response formats.
"""

from pydantic import BaseModel, ConfigDict, Field


class VerificationInitiatedResponse(BaseModel):
    """Response when verification code has been sent.

    Indicates successful initiation of email verification flow.
    """

    model_config = ConfigDict(
        strict=True,
        json_schema_extra={
            "examples": [
                {
                    "message": "Verification code sent",
                    "expires_in_seconds": 600,
                }
            ]
        },
    )

    message: str = Field(
        default="Verification code sent",
        description="Confirmation message",
    )
    expires_in_seconds: int = Field(
        default=600,
        description="Code validity in seconds (10 minutes)",
    )
