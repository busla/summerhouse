#!/usr/bin/env python3
"""
Cleanup script for development data.

Aggressively deletes all transactional/user data from DynamoDB tables
and Cognito users. Preserves configuration data (availability, pricing).

Usage:
    uv run python scripts/cleanup_data.py --env dev --region eu-west-1
    uv run python scripts/cleanup_data.py --env dev --region eu-west-1 --dry-run
    uv run python scripts/cleanup_data.py --env dev --region eu-west-1 --include-cognito
"""

import argparse
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError


# Tables containing transactional/user data (will be cleaned)
TRANSACTIONAL_TABLES = [
    "reservations",
    "customers",
    "payments",
    "verification-codes",
    "stripe-webhook-events",
    "oauth2-sessions",
]

# Tables containing configuration data (will NOT be cleaned)
CONFIG_TABLES = [
    "availability",
    "pricing",
]

# Primary key definitions for each table
TABLE_KEYS = {
    "reservations": ["reservation_id"],
    "customers": ["customer_id"],
    "payments": ["payment_id"],
    "verification-codes": ["email"],
    "stripe-webhook-events": ["event_id"],
    "oauth2-sessions": ["session_id"],
}


def get_table_prefix(env: str) -> str:
    """Get table name prefix based on environment."""
    return f"booking-{env}-data"


def delete_all_items_from_table(
    dynamodb: Any,
    table_name: str,
    key_names: list[str],
    dry_run: bool = False,
) -> int:
    """
    Delete all items from a DynamoDB table.

    Returns the count of items deleted.
    """
    table = dynamodb.Table(table_name)
    deleted_count = 0

    try:
        # Scan all items (paginated)
        scan_kwargs: dict[str, Any] = {
            "ProjectionExpression": ", ".join(key_names),
        }

        while True:
            response = table.scan(**scan_kwargs)
            items = response.get("Items", [])

            if not items:
                break

            if dry_run:
                deleted_count += len(items)
                print(f"    [DRY RUN] Would delete {len(items)} items")
            else:
                # Batch delete (max 25 items per request)
                with table.batch_writer() as batch:
                    for item in items:
                        key = {k: item[k] for k in key_names}
                        batch.delete_item(Key=key)
                        deleted_count += 1

                print(f"    Deleted {len(items)} items")

            # Check for more pages
            if "LastEvaluatedKey" not in response:
                break
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        return deleted_count

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"    Table not found (skipping)")
            return 0
        raise


def cleanup_dynamodb(env: str, region: str, dry_run: bool = False) -> dict[str, int]:
    """
    Clean up all transactional DynamoDB tables.

    Returns dict of table name -> items deleted.
    """
    dynamodb = boto3.resource("dynamodb", region_name=region)
    prefix = get_table_prefix(env)
    results: dict[str, int] = {}

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Cleaning DynamoDB tables (prefix: {prefix})...")
    print(f"  Tables to clean: {', '.join(TRANSACTIONAL_TABLES)}")
    print(f"  Tables preserved: {', '.join(CONFIG_TABLES)}")

    for table_suffix in TRANSACTIONAL_TABLES:
        table_name = f"{prefix}-{table_suffix}"
        key_names = TABLE_KEYS.get(table_suffix, ["id"])

        print(f"\n  Processing {table_name}...")
        count = delete_all_items_from_table(dynamodb, table_name, key_names, dry_run)
        results[table_name] = count

    return results


def get_cognito_user_pool_id(env: str, region: str) -> str | None:
    """
    Get Cognito User Pool ID from Terraform outputs.

    Falls back to known dev pool ID if terraform output fails.
    """
    import subprocess
    import json

    try:
        # Try to get from terraform output
        result = subprocess.run(
            ["terraform", "output", "-json", "cognito_user_pool_id"],
            cwd="infrastructure",
            capture_output=True,
            text=True,
            env={
                **dict(__import__("os").environ),
                "TF_DATA_DIR": f"infrastructure/.terraform-{env}",
            },
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass

    # Fallback for dev environment
    if env == "dev":
        return "eu-west-1_VEgg3Z7oI"

    return None


def cleanup_cognito(env: str, region: str, dry_run: bool = False) -> int:
    """
    Delete all users from the Cognito User Pool.

    Returns count of users deleted.
    """
    user_pool_id = get_cognito_user_pool_id(env, region)

    if not user_pool_id:
        print(f"\n  Could not determine Cognito User Pool ID for {env}")
        return 0

    cognito = boto3.client("cognito-idp", region_name=region)
    deleted_count = 0

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Cleaning Cognito User Pool: {user_pool_id}...")

    try:
        # List all users (paginated)
        paginator = cognito.get_paginator("list_users")

        for page in paginator.paginate(UserPoolId=user_pool_id):
            users = page.get("Users", [])

            for user in users:
                username = user["Username"]
                email = next(
                    (attr["Value"] for attr in user.get("Attributes", []) if attr["Name"] == "email"),
                    "unknown"
                )

                if dry_run:
                    print(f"    [DRY RUN] Would delete user: {username} ({email})")
                else:
                    try:
                        cognito.admin_delete_user(
                            UserPoolId=user_pool_id,
                            Username=username,
                        )
                        print(f"    Deleted user: {username} ({email})")
                    except ClientError as e:
                        print(f"    Failed to delete {username}: {e}")
                        continue

                deleted_count += 1

        return deleted_count

    except ClientError as e:
        print(f"  Error listing users: {e}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean up development data from DynamoDB and Cognito"
    )
    parser.add_argument(
        "--env",
        required=True,
        choices=["dev", "prod"],
        help="Environment to clean",
    )
    parser.add_argument(
        "--region",
        default="eu-west-1",
        help="AWS region (default: eu-west-1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--include-cognito",
        action="store_true",
        help="Also delete all Cognito users (default: DynamoDB only)",
    )
    parser.add_argument(
        "--cognito-only",
        action="store_true",
        help="Only delete Cognito users (skip DynamoDB)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt (required for prod)",
    )

    args = parser.parse_args()

    # Safety check for prod
    if args.env == "prod" and not args.force:
        print("⚠️  WARNING: You are about to delete PRODUCTION data!")
        print("    This action is IRREVERSIBLE.")
        response = input("    Type 'DELETE PROD' to confirm: ")
        if response != "DELETE PROD":
            print("Aborted.")
            return 1

    action = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{'='*60}")
    print(f"{action}Cleaning up {args.env} environment data")
    print(f"{'='*60}")

    total_dynamodb = 0
    total_cognito = 0

    # Clean DynamoDB
    if not args.cognito_only:
        results = cleanup_dynamodb(args.env, args.region, args.dry_run)
        total_dynamodb = sum(results.values())

    # Clean Cognito
    if args.include_cognito or args.cognito_only:
        total_cognito = cleanup_cognito(args.env, args.region, args.dry_run)

    # Summary
    print(f"\n{'='*60}")
    print(f"{action}Cleanup Summary")
    print(f"{'='*60}")
    print(f"  DynamoDB items {'would be ' if args.dry_run else ''}deleted: {total_dynamodb}")
    if args.include_cognito or args.cognito_only:
        print(f"  Cognito users {'would be ' if args.dry_run else ''}deleted: {total_cognito}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
