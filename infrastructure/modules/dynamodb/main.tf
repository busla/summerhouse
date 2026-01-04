# DynamoDB Tables for Summerhouse
# Uses terraform-aws-modules/dynamodb-table/aws and cloudposse/label/null
#
# Tables defined per data-model.md specification:
# - reservations: Booking records with GSIs for guest and status queries
# - customers: Customer profiles with email lookup
# - availability: Date-based availability
# - pricing: Seasonal pricing
# - payments: Payment records linked to reservations
# - verification_codes: Auth codes with TTL
#
# Pattern: Single label module with context from root, suffixes for individual tables

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# -----------------------------------------------------------------------------
# CloudPosse Label - inherits context from root, sets component name
# -----------------------------------------------------------------------------

module "label" {
  source  = "cloudposse/label/null"
  version = "~> 0.25"

  # Inherit namespace, environment, tags from root context
  context = var.context

  # Component name for this module
  name = "data"
}

# -----------------------------------------------------------------------------
# Reservations Table
# -----------------------------------------------------------------------------

module "reservations" {
  source  = "terraform-aws-modules/dynamodb-table/aws"
  version = "~> 5.0"

  name     = "${module.label.id}-reservations"
  hash_key = "reservation_id"

  billing_mode = "PAY_PER_REQUEST"

  attributes = [
    { name = "reservation_id", type = "S" },
    { name = "guest_id", type = "S" },
    { name = "status", type = "S" },
    { name = "check_in", type = "S" }
  ]

  # GSI for querying by guest with check_in sort
  global_secondary_indexes = [
    {
      name            = "guest-checkin-index"
      hash_key        = "guest_id"
      range_key       = "check_in"
      projection_type = "ALL"
    },
    {
      name            = "status-index"
      hash_key        = "status"
      range_key       = "check_in"
      projection_type = "ALL"
    }
  ]

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# Customers Table
# -----------------------------------------------------------------------------

module "customers" {
  source  = "terraform-aws-modules/dynamodb-table/aws"
  version = "~> 5.0"

  name     = "${module.label.id}-customers"
  hash_key = "customer_id"

  billing_mode = "PAY_PER_REQUEST"

  attributes = [
    { name = "customer_id", type = "S" },
    { name = "email", type = "S" },
    { name = "cognito_sub", type = "S" }
  ]

  # GSI for querying by email and by cognito_sub (for OAuth2 binding)
  global_secondary_indexes = [
    {
      name            = "email-index"
      hash_key        = "email"
      projection_type = "ALL"
    },
    {
      name            = "cognito-sub-index"
      hash_key        = "cognito_sub"
      projection_type = "ALL"
    }
  ]

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# Availability Table
# -----------------------------------------------------------------------------

module "availability" {
  source  = "terraform-aws-modules/dynamodb-table/aws"
  version = "~> 5.0"

  name     = "${module.label.id}-availability"
  hash_key = "date"

  billing_mode = "PAY_PER_REQUEST"

  attributes = [
    { name = "date", type = "S" }
  ]

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# Pricing Table
# -----------------------------------------------------------------------------

module "pricing" {
  source  = "terraform-aws-modules/dynamodb-table/aws"
  version = "~> 5.0"

  name     = "${module.label.id}-pricing"
  hash_key = "season_id"

  billing_mode = "PAY_PER_REQUEST"

  attributes = [
    { name = "season_id", type = "S" }
  ]

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# Payments Table
# -----------------------------------------------------------------------------

module "payments" {
  source  = "terraform-aws-modules/dynamodb-table/aws"
  version = "~> 5.0"

  name     = "${module.label.id}-payments"
  hash_key = "payment_id"

  billing_mode = "PAY_PER_REQUEST"

  attributes = [
    { name = "payment_id", type = "S" },
    { name = "reservation_id", type = "S" }
  ]

  # GSI for querying by reservation
  global_secondary_indexes = [
    {
      name            = "reservation-index"
      hash_key        = "reservation_id"
      projection_type = "ALL"
    }
  ]

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# Verification Codes Table (with TTL)
# -----------------------------------------------------------------------------

module "verification_codes" {
  source  = "terraform-aws-modules/dynamodb-table/aws"
  version = "~> 5.0"

  name     = "${module.label.id}-verification-codes"
  hash_key = "email"

  billing_mode = "PAY_PER_REQUEST"

  attributes = [
    { name = "email", type = "S" }
  ]

  # TTL for automatic expiration
  ttl_enabled        = true
  ttl_attribute_name = "expires_at"

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# Stripe Webhook Events Table (with TTL)
# -----------------------------------------------------------------------------
# Tracks processed Stripe webhook events for idempotency and auditing.
# TTL set to 90 days (7,776,000 seconds) for compliance record-keeping.

module "stripe_webhook_events" {
  source  = "terraform-aws-modules/dynamodb-table/aws"
  version = "~> 5.0"

  name     = "${module.label.id}-stripe-webhook-events"
  hash_key = "event_id"

  billing_mode = "PAY_PER_REQUEST"

  attributes = [
    { name = "event_id", type = "S" },
    { name = "event_type", type = "S" },
    { name = "processed_at", type = "S" }
  ]

  # GSI for querying by event type (useful for debugging/analytics)
  global_secondary_indexes = [
    {
      name            = "event-type-index"
      hash_key        = "event_type"
      range_key       = "processed_at"
      projection_type = "ALL"
    }
  ]

  # TTL for automatic expiration (90 days)
  ttl_enabled        = true
  ttl_attribute_name = "ttl"

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# OAuth2 Sessions Table (with TTL)
# -----------------------------------------------------------------------------
# Tracks OAuth2 session_id → guest_email mapping for user identity verification
# in the AgentCore two-stage callback flow. AgentCore handles state/PKCE internally.

module "oauth2_sessions" {
  source  = "terraform-aws-modules/dynamodb-table/aws"
  version = "~> 5.0"

  name     = "${module.label.id}-oauth2-sessions"
  hash_key = "session_id"

  billing_mode = "PAY_PER_REQUEST"

  attributes = [
    { name = "session_id", type = "S" }
  ]

  # TTL for automatic expiration (10 minutes)
  ttl_enabled        = true
  ttl_attribute_name = "expires_at"

  tags = module.label.tags
}
