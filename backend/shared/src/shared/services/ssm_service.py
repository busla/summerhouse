"""SSM Parameter Store service for secure secret retrieval.

Provides cached access to AWS SSM Parameter Store SecureString parameters.
Used primarily for Stripe API keys and webhook secrets.
"""

import logging
from functools import lru_cache
from typing import ClassVar

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SSMServiceError(Exception):
    """Raised when SSM parameter retrieval fails."""

    pass


class SSMService:
    """Service for retrieving secrets from AWS SSM Parameter Store.

    Features:
    - Retrieves SecureString parameters with automatic decryption
    - In-process caching to avoid repeated API calls
    - Environment-aware parameter paths

    Usage:
        ssm = SSMService()
        stripe_key = ssm.get_parameter("/booking/dev/stripe/secret_key")
    """

    _instance: ClassVar["SSMService | None"] = None
    _cache: ClassVar[dict[str, str]] = {}

    def __init__(self) -> None:
        """Initialize the SSM client."""
        self._client = boto3.client("ssm")

    @classmethod
    def get_instance(cls) -> "SSMService":
        """Get singleton instance of SSMService.

        Returns:
            SSMService: Shared service instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_parameter(self, name: str, *, use_cache: bool = True) -> str:
        """Retrieve a parameter value from SSM Parameter Store.

        Args:
            name: Full parameter path (e.g., "/booking/dev/stripe/secret_key")
            use_cache: Whether to use cached value if available (default: True)

        Returns:
            The decrypted parameter value.

        Raises:
            SSMServiceError: If parameter cannot be retrieved.
        """
        # Check cache first
        if use_cache and name in self._cache:
            logger.debug("SSM cache hit for %s", name)
            return self._cache[name]

        try:
            logger.info("Fetching SSM parameter: %s", name)
            response = self._client.get_parameter(Name=name, WithDecryption=True)
            value = response["Parameter"]["Value"]

            # Cache the value
            self._cache[name] = value
            logger.debug("SSM parameter cached: %s", name)

            return value

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "ParameterNotFound":
                raise SSMServiceError(f"SSM parameter not found: {name}") from e
            if error_code == "AccessDeniedException":
                raise SSMServiceError(
                    f"Access denied to SSM parameter: {name}. "
                    "Check IAM permissions for ssm:GetParameter."
                ) from e
            raise SSMServiceError(
                f"Failed to retrieve SSM parameter {name}: {e}"
            ) from e

    def clear_cache(self) -> None:
        """Clear all cached parameters.

        Useful for testing or when parameters are known to have changed.
        """
        self._cache.clear()
        logger.info("SSM parameter cache cleared")


@lru_cache(maxsize=1)
def get_ssm_service() -> SSMService:
    """Get the shared SSMService instance (singleton pattern).

    This function uses lru_cache to ensure only one instance is created,
    even across multiple imports.

    Returns:
        SSMService: Shared service instance.
    """
    return SSMService.get_instance()
