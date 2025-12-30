"""DynamoDB service wrapper for type-safe table operations."""

import os
from datetime import datetime, timezone
from typing import Any, TypeVar

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# Module-level singleton for connection reuse (performance optimization T114)
_dynamodb_service_instance: "DynamoDBService | None" = None


def get_dynamodb_service(environment: str | None = None) -> "DynamoDBService":
    """Get or create the singleton DynamoDB service instance.

    This avoids creating new boto3 clients on every tool call,
    which adds ~100-200ms overhead per instantiation.

    Args:
        environment: Environment name. Only used on first call.

    Returns:
        Shared DynamoDBService instance
    """
    global _dynamodb_service_instance
    if _dynamodb_service_instance is None:
        _dynamodb_service_instance = DynamoDBService(environment)
    return _dynamodb_service_instance


def reset_dynamodb_service() -> None:
    """Reset the singleton instance (for testing only).

    This allows tests to create a fresh DynamoDBService inside
    a mock_aws context.
    """
    global _dynamodb_service_instance
    _dynamodb_service_instance = None


class DynamoDBService:
    """Service for DynamoDB operations with environment-aware table names."""

    def __init__(self, environment: str | None = None) -> None:
        """Initialize DynamoDB service.

        Args:
            environment: Environment name (dev/prod). Defaults to ENVIRONMENT env var.
        """
        self.environment = environment or os.getenv("ENVIRONMENT", "dev")
        # Allow override via DYNAMODB_TABLE_PREFIX for testing
        self.name_prefix = os.getenv(
            "DYNAMODB_TABLE_PREFIX", f"booking-{self.environment}"
        )
        self._dynamodb = boto3.resource("dynamodb")
        self._client = boto3.client("dynamodb")

    def _table_name(self, table: str) -> str:
        """Get full table name with prefix."""
        return f"{self.name_prefix}-{table}"

    def _get_table(self, table: str) -> Any:
        """Get DynamoDB table resource."""
        return self._dynamodb.Table(self._table_name(table))

    # Generic CRUD operations

    def get_item(
        self,
        table: str,
        key: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Get a single item by key.

        Args:
            table: Table name without prefix
            key: Primary key dict

        Returns:
            Item dict or None if not found
        """
        response = self._get_table(table).get_item(Key=key)
        item: dict[str, Any] | None = response.get("Item")
        return item

    def put_item(
        self,
        table: str,
        item: dict[str, Any],
        condition_expression: str | None = None,
    ) -> bool:
        """Put an item into the table.

        Args:
            table: Table name without prefix
            item: Item to store
            condition_expression: Optional condition for write

        Returns:
            True if successful, False if condition failed
        """
        try:
            kwargs: dict[str, Any] = {"Item": item}
            if condition_expression:
                kwargs["ConditionExpression"] = condition_expression

            self._get_table(table).put_item(**kwargs)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def update_item(
        self,
        table: str,
        key: dict[str, Any],
        update_expression: str,
        expression_attribute_values: dict[str, Any],
        expression_attribute_names: dict[str, str] | None = None,
        condition_expression: str | None = None,
    ) -> dict[str, Any] | None:
        """Update an item with expressions.

        Args:
            table: Table name without prefix
            key: Primary key dict
            update_expression: DynamoDB update expression
            expression_attribute_values: Values for expression
            expression_attribute_names: Names for expression (for reserved words)
            condition_expression: Optional condition for update

        Returns:
            Updated attributes or None if condition failed
        """
        try:
            kwargs: dict[str, Any] = {
                "Key": key,
                "UpdateExpression": update_expression,
                "ExpressionAttributeValues": expression_attribute_values,
                "ReturnValues": "ALL_NEW",
            }
            if expression_attribute_names:
                kwargs["ExpressionAttributeNames"] = expression_attribute_names
            if condition_expression:
                kwargs["ConditionExpression"] = condition_expression

            response = self._get_table(table).update_item(**kwargs)
            attrs: dict[str, Any] | None = response.get("Attributes")
            return attrs
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return None
            raise

    def delete_item(
        self,
        table: str,
        key: dict[str, Any],
    ) -> bool:
        """Delete an item by key.

        Args:
            table: Table name without prefix
            key: Primary key dict

        Returns:
            True if deleted (or didn't exist)
        """
        self._get_table(table).delete_item(Key=key)
        return True

    def query(
        self,
        table: str,
        key_condition: Any,
        index_name: str | None = None,
        filter_expression: Any | None = None,
        limit: int | None = None,
        scan_index_forward: bool = True,
    ) -> list[dict[str, Any]]:
        """Query table or GSI.

        Args:
            table: Table name without prefix
            key_condition: Boto3 Key condition
            index_name: GSI name (optional)
            filter_expression: Additional filter (optional)
            limit: Max items to return
            scan_index_forward: Sort order (True=ascending)

        Returns:
            List of items
        """
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": scan_index_forward,
        }
        if index_name:
            kwargs["IndexName"] = index_name
        if filter_expression:
            kwargs["FilterExpression"] = filter_expression
        if limit:
            kwargs["Limit"] = limit

        response = self._get_table(table).query(**kwargs)
        items: list[dict[str, Any]] = response.get("Items", [])
        return items

    def batch_get(
        self,
        table: str,
        keys: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Batch get items by keys.

        Args:
            table: Table name without prefix
            keys: List of primary key dicts

        Returns:
            List of found items
        """
        if not keys:
            return []

        table_name = self._table_name(table)
        response = self._dynamodb.batch_get_item(
            RequestItems={table_name: {"Keys": keys}}
        )
        items: list[dict[str, Any]] = response.get("Responses", {}).get(table_name, [])
        return items

    def transact_write(
        self,
        items: list[dict[str, Any]],
    ) -> bool:
        """Execute transactional write for multiple items.

        Args:
            items: List of TransactWriteItem dicts

        Returns:
            True if successful, False if transaction failed
        """
        try:
            # Cast to satisfy boto3-stubs type checker
            self._client.transact_write_items(TransactItems=items)  # type: ignore[arg-type]
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "TransactionCanceledException":
                return False
            raise

    # Convenience methods for common patterns

    def query_by_gsi(
        self,
        table: str,
        index_name: str,
        partition_key_name: str,
        partition_key_value: str,
        sort_key_condition: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Query a GSI by partition key.

        Args:
            table: Table name without prefix
            index_name: GSI name
            partition_key_name: Name of partition key attribute
            partition_key_value: Value to query
            sort_key_condition: Optional sort key condition

        Returns:
            List of items
        """
        key_condition = Key(partition_key_name).eq(partition_key_value)
        if sort_key_condition:
            key_condition = key_condition & sort_key_condition

        return self.query(table, key_condition, index_name=index_name)

    # =========================================================================
    # Guest-specific methods (T035)
    # =========================================================================

    def get_guest_by_email(self, email: str) -> dict[str, Any] | None:
        """Get a guest by email address using GSI.

        Args:
            email: Guest email address

        Returns:
            Guest dict or None if not found
        """
        results = self.query_by_gsi(
            table="guests",
            index_name="email-index",
            partition_key_name="email",
            partition_key_value=email,
        )
        return results[0] if results else None

    def get_guest_by_cognito_sub(self, cognito_sub: str) -> dict[str, Any] | None:
        """Get a guest by Cognito sub using GSI.

        Args:
            cognito_sub: Cognito user sub (from ID token)

        Returns:
            Guest dict or None if not found
        """
        results = self.query_by_gsi(
            table="guests",
            index_name="cognito_sub-index",
            partition_key_name="cognito_sub",
            partition_key_value=cognito_sub,
        )
        return results[0] if results else None

    def create_guest(self, guest: dict[str, Any]) -> bool:
        """Create a new guest record.

        Args:
            guest: Guest data dict (must include guest_id)

        Returns:
            True if created successfully
        """
        return self.put_item(
            table="guests",
            item=guest,
            condition_expression="attribute_not_exists(guest_id)",
        )

    def update_guest_cognito_sub(
        self, guest_id: str, cognito_sub: str
    ) -> dict[str, Any] | None:
        """Bind a Cognito sub to an existing guest.

        Used when a guest who was created before OAuth2 auth
        logs in for the first time and needs their cognito_sub linked.

        Args:
            guest_id: Guest primary key
            cognito_sub: Cognito user sub to bind

        Returns:
            Updated guest attributes or None if failed
        """
        return self.update_item(
            table="guests",
            key={"guest_id": guest_id},
            update_expression="SET cognito_sub = :sub",
            expression_attribute_values={":sub": cognito_sub},
        )

    # =========================================================================
    # OAuth2 Session methods (T063)
    # =========================================================================

    def create_oauth2_session(
        self, session_data: "OAuth2SessionCreate"
    ) -> "OAuth2Session":
        """Create an OAuth2 session for conversation-to-callback bridge.

        Stores the session_id → guest_email mapping that enables user identity
        verification during the OAuth2 callback flow.

        Sessions expire after 10 minutes via DynamoDB TTL.

        Args:
            session_data: Session creation data with session_id, conversation_id, guest_email

        Returns:
            OAuth2Session model with all fields populated

        Raises:
            ClientError: If DynamoDB write fails
        """
        from src.models.oauth2_session import OAuth2Session, OAuth2SessionStatus

        now = datetime.now(timezone.utc)
        expires_at = int(now.timestamp()) + 600  # 10 minute TTL

        session = OAuth2Session(
            session_id=session_data.session_id,
            conversation_id=session_data.conversation_id,
            guest_email=session_data.guest_email,
            status=OAuth2SessionStatus.PENDING,
            created_at=now,
            expires_at=expires_at,
        )

        # Store in DynamoDB
        item = {
            "session_id": session.session_id,
            "conversation_id": session.conversation_id,
            "guest_email": session.guest_email,
            "status": session.status.value,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at,
        }

        self.put_item(table="oauth2-sessions", item=item)
        return session

    def get_oauth2_session(self, session_id: str) -> "OAuth2Session | None":
        """Get an OAuth2 session by session_id.

        Used by the callback handler to look up guest_email for user verification.

        Args:
            session_id: Session URI from AgentCore

        Returns:
            OAuth2Session if found, None otherwise
        """
        from src.models.oauth2_session import OAuth2Session, OAuth2SessionStatus

        item = self.get_item(table="oauth2-sessions", key={"session_id": session_id})
        if not item:
            return None

        # Parse created_at from ISO format
        created_at_str = item["created_at"]
        if isinstance(created_at_str, str):
            if created_at_str.endswith("Z"):
                created_at_str = created_at_str[:-1] + "+00:00"
            created_at = datetime.fromisoformat(created_at_str)
        else:
            created_at = datetime.now(timezone.utc)

        return OAuth2Session(
            session_id=item["session_id"],
            conversation_id=item["conversation_id"],
            guest_email=item["guest_email"],
            status=OAuth2SessionStatus(item["status"]),
            created_at=created_at,
            expires_at=int(item["expires_at"]),
        )

    def update_oauth2_session_status(
        self, session_id: str, status: "OAuth2SessionStatus"
    ) -> bool:
        """Update the status of an OAuth2 session.

        Used to mark sessions as COMPLETED (successful auth) or FAILED (error/mismatch).

        Args:
            session_id: Session to update
            status: New status (COMPLETED, FAILED, EXPIRED)

        Returns:
            True if update succeeded, False if session not found
        """
        result = self.update_item(
            table="oauth2-sessions",
            key={"session_id": session_id},
            update_expression="SET #status = :status",
            expression_attribute_names={"#status": "status"},
            expression_attribute_values={":status": status.value},
        )
        return result is not None
