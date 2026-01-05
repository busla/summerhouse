#!/usr/bin/env python3
"""Seed development database with test data.

This script populates DynamoDB tables with realistic test data for local
development and testing. Per FR-003 and data-model.md requirements:
- Seasonal pricing for 2+ years with different rates and minimum stays
- 2 years of individual availability date records (status='available' by default)
- Sample customer records (optional)

Usage:
    python scripts/seed_data.py --env dev
    python scripts/seed_data.py --env dev --pricing-only
    python scripts/seed_data.py --env dev --clear-first
    python scripts/seed_data.py --env dev --skip-customers
    python scripts/seed_data.py --env dev --e2e-mode

Or via Taskfile:
    task seed:dev
    task seed:dev:e2e    # E2E mode: clear all reservations, all dates available

E2E Mode (--e2e-mode):
    For Playwright E2E tests that need to book arbitrary dates without conflicts.
    - Clears the reservations table
    - Makes ALL dates available (no blocked periods)
    - Each test can book unique future dates without cleanup
"""

import argparse
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import boto3  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402

# Global region setting (set by main() from args)
_AWS_REGION: str | None = None

# Cognito User Pool ID (matches frontend E2E tests)
COGNITO_USER_POOL_ID = "eu-west-1_VEgg3Z7oI"

# E2E test user email (must match SSM param /booking/e2e/test-user-email)
E2E_TEST_USER_EMAIL = "e2e-test@levy.apro.work"


def get_dynamodb_resource():
    """Get DynamoDB resource with configured region."""
    if _AWS_REGION:
        return boto3.resource("dynamodb", region_name=_AWS_REGION)
    return boto3.resource("dynamodb")


def get_table_name(env: str, table: str) -> str:
    """Get full table name with environment prefix."""
    return f"booking-{env}-{table}"


def get_cognito_user_sub(email: str) -> str | None:
    """Get a Cognito user's sub (unique ID) by email.

    This is used to link seeded customer records to their Cognito identity,
    enabling the fast lookup path via cognito-sub-index GSI.

    Args:
        email: The user's email address (Cognito username)

    Returns:
        The user's sub (UUID) if found, None otherwise
    """
    try:
        client = boto3.client("cognito-idp", region_name=_AWS_REGION)
        response = client.admin_get_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=email,
        )
        # Find the 'sub' attribute
        for attr in response.get("UserAttributes", []):
            if attr.get("Name") == "sub":
                return attr.get("Value")
        return None
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "UserNotFoundException":
            print(f"  ⚠️  Cognito user not found: {email}")
            print("      Run 'yarn test:e2e:setup-user' first to create the user")
        else:
            print(f"  ⚠️  Could not get Cognito user {email}: {e}")
        return None


def create_seasonal_pricing(env: str) -> list[dict]:
    """Create realistic seasonal pricing data for 2025.

    Pricing structure for a vacation rental in Greece:
    - Low Season: Winter months (cheaper, shorter minimum stay)
    - Mid Season: Spring/Fall (moderate pricing)
    - High Season: Summer peak (premium pricing, longer minimum stay)
    - Peak Season: Holidays (highest pricing)
    """
    seasons = [
        {
            "season_id": "low-winter-2025",
            "season_name": "Low Season (Winter)",
            "start_date": "2025-01-01",
            "end_date": "2025-03-31",
            "nightly_rate": 8000,  # €80.00
            "minimum_nights": 3,
            "cleaning_fee": 5000,  # €50.00
            "is_active": "true",  # DynamoDB string for GSI
        },
        {
            "season_id": "mid-spring-2025",
            "season_name": "Mid Season (Spring)",
            "start_date": "2025-04-01",
            "end_date": "2025-06-30",
            "nightly_rate": 10000,  # €100.00
            "minimum_nights": 5,
            "cleaning_fee": 5000,
            "is_active": "true",
        },
        {
            "season_id": "high-summer-2025",
            "season_name": "High Season (Summer)",
            "start_date": "2025-07-01",
            "end_date": "2025-08-31",
            "nightly_rate": 15000,  # €150.00
            "minimum_nights": 7,
            "cleaning_fee": 6000,  # €60.00
            "is_active": "true",
        },
        {
            "season_id": "mid-fall-2025",
            "season_name": "Mid Season (Fall)",
            "start_date": "2025-09-01",
            "end_date": "2025-11-30",
            "nightly_rate": 10000,  # €100.00
            "minimum_nights": 5,
            "cleaning_fee": 5000,
            "is_active": "true",
        },
        {
            "season_id": "peak-christmas-2025",
            "season_name": "Peak Season (Christmas & New Year)",
            "start_date": "2025-12-01",
            "end_date": "2025-12-31",
            "nightly_rate": 18000,  # €180.00
            "minimum_nights": 7,
            "cleaning_fee": 6000,
            "is_active": "true",
        },
        # 2026 seasons for cross-year bookings (full year coverage)
        {
            "season_id": "low-winter-2026",
            "season_name": "Low Season (Winter 2026)",
            "start_date": "2026-01-01",
            "end_date": "2026-03-31",
            "nightly_rate": 8500,  # €85.00 (slight increase)
            "minimum_nights": 3,
            "cleaning_fee": 5000,
            "is_active": "true",
        },
        {
            "season_id": "mid-spring-2026",
            "season_name": "Mid Season (Spring 2026)",
            "start_date": "2026-04-01",
            "end_date": "2026-06-30",
            "nightly_rate": 10500,  # €105.00
            "minimum_nights": 5,
            "cleaning_fee": 5000,
            "is_active": "true",
        },
        {
            "season_id": "high-summer-2026",
            "season_name": "High Season (Summer 2026)",
            "start_date": "2026-07-01",
            "end_date": "2026-08-31",
            "nightly_rate": 16000,  # €160.00
            "minimum_nights": 7,
            "cleaning_fee": 6000,
            "is_active": "true",
        },
        {
            "season_id": "mid-fall-2026",
            "season_name": "Mid Season (Fall 2026)",
            "start_date": "2026-09-01",
            "end_date": "2026-11-30",
            "nightly_rate": 10500,  # €105.00
            "minimum_nights": 5,
            "cleaning_fee": 5000,
            "is_active": "true",
        },
        {
            "season_id": "peak-christmas-2026",
            "season_name": "Peak Season (Christmas 2026)",
            "start_date": "2026-12-01",
            "end_date": "2026-12-31",
            "nightly_rate": 19000,  # €190.00
            "minimum_nights": 7,
            "cleaning_fee": 6000,
            "is_active": "true",
        },
        # 2027 Q1 for 2-year coverage
        {
            "season_id": "low-winter-2027",
            "season_name": "Low Season (Winter 2027)",
            "start_date": "2027-01-01",
            "end_date": "2027-03-31",
            "nightly_rate": 9000,  # €90.00
            "minimum_nights": 3,
            "cleaning_fee": 5500,
            "is_active": "true",
        },
    ]

    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(get_table_name(env, "data-pricing"))

    print(f"Seeding pricing table: {table.name}")

    for season in seasons:
        table.put_item(Item=season)
        rate_eur = season["nightly_rate"] / 100
        print(f"  ✓ {season['season_name']}: €{rate_eur:.2f}/night, min {season['minimum_nights']} nights")

    return seasons


def create_availability(env: str, years: int = 2, e2e_mode: bool = False) -> int:
    """Create availability records for the next N years.

    Per FR-003 and data-model.md, pre-populates availability table with
    individual date records. Each date has PK='date' (YYYY-MM-DD format)
    and status='available' by default.

    Args:
        env: Target environment
        years: Number of years to seed (default: 2)
        e2e_mode: If True, ALL dates are available (no blocked periods)

    Returns:
        Number of records created
    """
    from datetime import timedelta

    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(get_table_name(env, "data-availability"))

    print(f"Seeding availability table: {table.name}")
    print(f"  Creating {years} years of availability records...")
    if e2e_mode:
        print("  ℹ️  E2E mode: ALL dates will be available (no blocked periods)")

    # Start from today
    today = date.today()
    end_date = today + timedelta(days=365 * years)

    # Sample blocked periods (existing bookings) for realistic test data
    # In E2E mode, skip these so tests can book any date without conflicts
    blocked_dates: dict[str, str] = {}  # date_str -> reservation_id

    if not e2e_mode:
        # IMPORTANT: E2E tests book June 16-30, 2026. These blocked periods must NOT overlap.
        # Using relative dates from today for variety in dev environment.
        blocked_periods = [
            # Week blocked soon (days 14-20) - before E2E test range
            (today + timedelta(days=14), today + timedelta(days=20), "RES-TEST-SOON"),
            # Long weekend blocked later (days 75-78) - after E2E test range
            (today + timedelta(days=75), today + timedelta(days=78), "RES-TEST-LATER"),
            # Week blocked in ~4 months (days 120-127) - well after E2E test range
            (today + timedelta(days=120), today + timedelta(days=127), "RES-TEST-FAR"),
            # Another blocked period at ~6 months (days 180-187)
            (today + timedelta(days=180), today + timedelta(days=187), "RES-TEST-SUMMER"),
        ]

        # Build set of blocked dates for quick lookup
        for start, end, res_id in blocked_periods:
            current = start
            while current < end:
                blocked_dates[current.isoformat()] = res_id
                current += timedelta(days=1)

    # Generate all dates and write in batches
    count = 0
    current_date = today

    with table.batch_writer() as batch:
        while current_date < end_date:
            date_str = current_date.isoformat()

            # Check if date is blocked (only in non-E2E mode)
            if date_str in blocked_dates:
                record = {
                    "date": date_str,
                    "status": "booked",
                    "reservation_id": blocked_dates[date_str],
                    "updated_at": today.isoformat() + "T00:00:00Z",
                }
            else:
                record = {
                    "date": date_str,
                    "status": "available",
                    "updated_at": today.isoformat() + "T00:00:00Z",
                }

            batch.put_item(Item=record)
            count += 1
            current_date += timedelta(days=1)

    # Print summary
    booked_count = len(blocked_dates)
    available_count = count - booked_count
    print(f"  ✓ Created {count} availability records")
    print(f"    - {available_count} available dates")
    if booked_count > 0:
        print(f"    - {booked_count} booked dates (test reservations)")

    return count


def create_sample_customers(env: str) -> list[dict]:
    """Create sample customer records for testing.

    Schema matches customer.py tool requirements:
    - customer_id (PK)
    - email (with email-index GSI)
    - cognito_sub (with cognito-sub-index GSI) - links to Cognito identity
    - email_verified, name, phone, preferred_language
    - first_verified_at, total_bookings, created_at, updated_at
    """
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    # Get the E2E test user's cognito_sub if they exist in Cognito
    # This enables the fast lookup path in the API
    e2e_cognito_sub = get_cognito_user_sub(E2E_TEST_USER_EMAIL)

    # Build E2E test user customer record
    e2e_customer: dict = {
        "customer_id": str(uuid.uuid4()),
        "email": E2E_TEST_USER_EMAIL,
        "name": "Automated Test User",
        "phone": "+34 600 123 456",
        "email_verified": True,
        "preferred_language": "en",
        "total_bookings": 0,
        "first_verified_at": now,
        "created_at": now,
        "updated_at": now,
    }

    # Add cognito_sub if available (enables fast path lookup)
    if e2e_cognito_sub:
        e2e_customer["cognito_sub"] = e2e_cognito_sub
        print(f"  ℹ️  E2E user cognito_sub: {e2e_cognito_sub[:8]}...")

    customers = [
        # E2E Test User - linked to Cognito user created by setup-test-user.ts
        e2e_customer,
        {
            "customer_id": str(uuid.uuid4()),
            "email": "john.smith@example.com",
            "name": "John Smith",
            "phone": "+1-555-0101",
            "email_verified": True,
            "preferred_language": "en",
            "total_bookings": 2,
            "first_verified_at": "2025-01-15T10:30:00Z",
            "created_at": "2025-01-15T10:30:00Z",
            "updated_at": now,
        },
        {
            "customer_id": str(uuid.uuid4()),
            "email": "maria.garcia@example.com",
            "name": "Maria Garcia",
            "phone": "+34-600-123456",
            "email_verified": True,
            "preferred_language": "es",
            "total_bookings": 1,
            "first_verified_at": "2025-02-01T14:20:00Z",
            "created_at": "2025-02-01T14:20:00Z",
            "updated_at": now,
        },
        {
            "customer_id": str(uuid.uuid4()),
            "email": "test.user@example.com",
            "name": "Test User",
            "phone": "+44-7700-900123",
            "email_verified": False,
            "preferred_language": "en",
            "total_bookings": 0,
            "created_at": "2025-02-20T09:00:00Z",
            "updated_at": now,
        },
    ]

    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(get_table_name(env, "data-customers"))

    print(f"Seeding customers table: {table.name}")

    for customer in customers:
        table.put_item(Item=customer)
        status = "✓" if customer["email_verified"] else "○"
        print(f"  {status} {customer['name']} ({customer['email']})")

    return customers


def clear_table(env: str, table_name: str) -> int:
    """Clear all items from a table.

    Returns:
        Number of items deleted
    """
    dynamodb = get_dynamodb_resource()
    table = dynamodb.Table(get_table_name(env, table_name))

    # Scan and delete all items
    response = table.scan()
    items = response.get("Items", [])

    # Get key schema to determine primary key attributes
    key_attrs = [k["AttributeName"] for k in table.key_schema]

    with table.batch_writer() as batch:
        for item in items:
            key = {k: item[k] for k in key_attrs if k in item}
            batch.delete_item(Key=key)

    # Handle pagination for large tables
    while response.get("LastEvaluatedKey"):
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))
        with table.batch_writer() as batch:
            for item in response.get("Items", []):
                key = {k: item[k] for k in key_attrs if k in item}
                batch.delete_item(Key=key)

    return len(items)


def main() -> int:
    """Run the seed script."""
    global _AWS_REGION

    parser = argparse.ArgumentParser(description="Seed development database with test data")
    parser.add_argument(
        "--env",
        choices=["dev", "staging", "prod"],
        default="dev",
        help="Target environment (default: dev)",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_DEFAULT_REGION", "eu-west-1"),
        help="AWS region (default: eu-west-1 or AWS_DEFAULT_REGION env var)",
    )
    parser.add_argument(
        "--pricing-only",
        action="store_true",
        help="Only seed pricing data",
    )
    parser.add_argument(
        "--clear-first",
        action="store_true",
        help="Clear existing data before seeding",
    )
    parser.add_argument(
        "--skip-customers",
        action="store_true",
        help="Skip seeding customer data",
    )
    parser.add_argument(
        "--e2e-mode",
        action="store_true",
        help="E2E test mode: clears reservations table and makes ALL dates available",
    )

    args = parser.parse_args()

    # Set global region for boto3 calls
    _AWS_REGION = args.region

    # Safety check for production
    if args.env == "prod":
        confirm = input("⚠️  WARNING: You are about to modify PRODUCTION data. Type 'yes' to continue: ")
        if confirm.lower() != "yes":
            print("Aborted.")
            return 1

    print(f"\n🌱 Seeding {args.env} environment (region: {args.region})\n")

    # Optionally clear existing data
    if args.clear_first or args.e2e_mode:
        print("Clearing existing data...")
        if args.pricing_only:
            tables = ["data-pricing"]
        elif args.e2e_mode:
            # E2E mode: also clear reservations to ensure ALL dates can be booked
            tables = ["data-pricing", "data-availability", "data-customers", "data-reservations"]
        else:
            tables = ["data-pricing", "data-availability", "data-customers"]
        for table in tables:
            try:
                count = clear_table(args.env, table)
                print(f"  ✓ Cleared {count} items from {table}")
            except Exception as e:
                print(f"  ⚠️  Could not clear {table}: {e}")
        print()

    # Seed pricing (always)
    try:
        create_seasonal_pricing(args.env)
    except Exception as e:
        print(f"  ❌ Failed to seed pricing: {e}")
        return 1

    if args.pricing_only:
        print("\n✅ Pricing seeded successfully!")
        return 0

    # Seed availability (2 years of dates per FR-003)
    print()
    try:
        create_availability(args.env, years=2, e2e_mode=args.e2e_mode)
    except Exception as e:
        print(f"  ❌ Failed to seed availability: {e}")
        # Non-fatal, continue

    # Seed customers (optional)
    if not args.skip_customers:
        print()
        try:
            create_sample_customers(args.env)
        except Exception as e:
            print(f"  ❌ Failed to seed customers: {e}")
            # Non-fatal, continue

    print("\n✅ Seed completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
