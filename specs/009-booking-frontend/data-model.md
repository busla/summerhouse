# Data Model: Complete Booking Frontend

**Feature**: 009-booking-frontend
**Date**: 2026-01-01
**Storage**: AWS DynamoDB (Pay-Per-Request)

## Overview

This document defines the **new data entities** required for the booking frontend feature. It extends the existing data model from `specs/001-agent-booking-platform/data-model.md` with a single new table for Points of Interest (POIs) used by the interactive map.

## Existing Entities (Unchanged)

The following existing entities are **reused without modification**:

| Entity | Table | Used By |
|--------|-------|---------|
| Reservation | `booking-{env}-reservations` | Booking form submission (FR-014) |
| Guest | `booking-{env}-guests` | Guest details form (FR-012) |
| Availability | `booking-{env}-availability` | Date picker blocked dates (FR-008) |
| Pricing | `booking-{env}-pricing` | Price calculation (FR-009, FR-010) |
| Verification Codes | `booking-{env}-verification-codes` | Email verification (FR-013a) |

**No schema changes** are required to existing tables.

---

## New Entity: Points of Interest (POI)

**Purpose**: Store map markers for nearby attractions displayed on the location page (FR-025, FR-026).

### Entity Relationship

```
┌─────────────────┐
│   Apartment     │
│   (static)      │
└────────┬────────┘
         │
         │ nearby (implicit)
         ▼
┌─────────────────┐
│      POI        │──────▶ Displayed on map
│  (DynamoDB)     │        via API endpoint
└─────────────────┘
```

### DynamoDB Table: POIs

**Table Name**: `booking-{env}-pois`

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| `poi_id` | String | PK | Unique POI ID (UUID or slug) |
| `category` | String | GSI-PK | Category for filtering (`beach`, `golf`, `restaurant`, `attraction`, `shopping`, `transport`) |
| `name` | String | | Display name |
| `description` | String | | Brief description (1-2 sentences) |
| `latitude` | Number | | GPS latitude coordinate |
| `longitude` | Number | | GPS longitude coordinate |
| `distance_km` | Number | | Distance from property in kilometers |
| `distance_text` | String | | Human-readable distance (e.g., "15 min drive") |
| `icon` | String | | Optional icon identifier for map marker |
| `url` | String | | Optional external link (website, Google Maps) |
| `is_active` | Boolean | | Whether to display on map |
| `display_order` | Number | | Sort order within category |
| `created_at` | String | | ISO 8601 timestamp |
| `updated_at` | String | | ISO 8601 timestamp |

### Indexes

- **Primary Key**: `poi_id` (PK)
- **GSI: category-order-index**: `category` (PK), `display_order` (SK) - List POIs by category

### Access Patterns

| Pattern | Index | Query |
|---------|-------|-------|
| Get POI by ID | Primary | `PK = poi_id` |
| List all active POIs | Primary | Scan with filter `is_active = true` |
| List POIs by category | category-order-index | `category = X AND is_active = true` |
| List beaches | category-order-index | `category = 'beach'` |
| List golf courses | category-order-index | `category = 'golf'` |

### Pydantic Model

```python
from pydantic import BaseModel, ConfigDict, Field
from enum import Enum
from datetime import datetime
from typing import Optional

class POICategory(str, Enum):
    BEACH = "beach"
    GOLF = "golf"
    RESTAURANT = "restaurant"
    ATTRACTION = "attraction"
    SHOPPING = "shopping"
    TRANSPORT = "transport"

class POI(BaseModel):
    """Point of Interest for the location map."""
    model_config = ConfigDict(strict=True)

    poi_id: str
    category: POICategory
    name: str
    description: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    distance_km: float = Field(ge=0)
    distance_text: Optional[str] = None
    icon: Optional[str] = None
    url: Optional[str] = None
    is_active: bool = True
    display_order: int = 0
    created_at: datetime
    updated_at: datetime


class POIResponse(BaseModel):
    """API response model for POI list."""
    model_config = ConfigDict(strict=True)

    pois: list[POI]
    total: int
```

### TypeScript Type (Generated)

The frontend TypeScript type will be auto-generated from the OpenAPI spec, but for reference:

```typescript
export type POICategory =
  | 'beach'
  | 'golf'
  | 'restaurant'
  | 'attraction'
  | 'shopping'
  | 'transport';

export interface POI {
  poi_id: string;
  category: POICategory;
  name: string;
  description: string;
  latitude: number;
  longitude: number;
  distance_km: number;
  distance_text?: string;
  icon?: string;
  url?: string;
  is_active: boolean;
  display_order: number;
  created_at: string; // ISO 8601
  updated_at: string; // ISO 8601
}

export interface POIResponse {
  pois: POI[];
  total: number;
}
```

### Sample Data

```json
[
  {
    "poi_id": "beach-guardamar",
    "category": "beach",
    "name": "Guardamar Beach",
    "description": "Long sandy beach with pine-backed dunes and Blue Flag status.",
    "latitude": 38.0873,
    "longitude": -0.6556,
    "distance_km": 15,
    "distance_text": "20 min drive",
    "icon": "beach",
    "url": "https://goo.gl/maps/guardamar",
    "is_active": true,
    "display_order": 1,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z"
  },
  {
    "poi_id": "beach-la-mata",
    "category": "beach",
    "name": "La Mata Beach",
    "description": "Family-friendly beach with calm waters and nearby amenities.",
    "latitude": 37.9784,
    "longitude": -0.6932,
    "distance_km": 12,
    "distance_text": "15 min drive",
    "icon": "beach",
    "is_active": true,
    "display_order": 2,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z"
  },
  {
    "poi_id": "golf-la-marquesa",
    "category": "golf",
    "name": "La Marquesa Golf",
    "description": "18-hole course with stunning views and well-maintained greens.",
    "latitude": 38.0523,
    "longitude": -0.7834,
    "distance_km": 3,
    "distance_text": "5 min drive",
    "icon": "golf",
    "url": "https://lamarquesagolf.com",
    "is_active": true,
    "display_order": 1,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z"
  },
  {
    "poi_id": "golf-vistabella",
    "category": "golf",
    "name": "Vistabella Golf",
    "description": "Championship course designed by Manuel Piñero.",
    "latitude": 38.0112,
    "longitude": -0.8234,
    "distance_km": 8,
    "distance_text": "12 min drive",
    "icon": "golf",
    "is_active": true,
    "display_order": 2,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z"
  },
  {
    "poi_id": "attraction-salt-lakes",
    "category": "attraction",
    "name": "Torrevieja Salt Lakes",
    "description": "Famous pink salt lakes, perfect for photos and therapeutic mud.",
    "latitude": 37.9667,
    "longitude": -0.7000,
    "distance_km": 10,
    "distance_text": "15 min drive",
    "icon": "camera",
    "is_active": true,
    "display_order": 1,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z"
  },
  {
    "poi_id": "restaurant-la-taberna",
    "category": "restaurant",
    "name": "La Taberna",
    "description": "Traditional Spanish tapas in the heart of Quesada.",
    "latitude": 38.0741,
    "longitude": -0.8145,
    "distance_km": 1,
    "distance_text": "5 min walk",
    "icon": "restaurant",
    "is_active": true,
    "display_order": 1,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z"
  }
]
```

---

## Frontend State Models

These models are **transient client-side state** (not persisted to DynamoDB):

### Booking Widget State

```typescript
/**
 * Transient state for the booking widget component.
 * Not persisted - reconstructed from user interaction.
 */
interface BookingWidgetState {
  // Date selection
  selectedRange: {
    from: Date | null;
    to: Date | null;
  };

  // Calculated from selected dates
  nights: number | null;

  // Fetched from pricing API
  pricing: {
    nightlyRate: number;      // EUR cents
    cleaningFee: number;      // EUR cents
    totalAmount: number;      // EUR cents
    minimumNights: number;
    seasonName: string;
  } | null;

  // UI state
  isLoading: boolean;
  error: string | null;
}
```

### Booking Form State

```typescript
/**
 * Form state for guest details.
 * Validated before submission to create_reservation API.
 */
interface BookingFormState {
  // Guest details (FR-012)
  name: string;
  email: string;
  phone: string;
  numGuests: number;  // 1-4 (FR-013)

  // Optional
  specialRequests?: string;

  // Form state
  isSubmitting: boolean;
  errors: Record<string, string>;
}
```

### Gallery State

```typescript
/**
 * State for the photo gallery/lightbox.
 * Reuses existing PhotoGallery component logic.
 */
interface GalleryState {
  images: Array<{
    id: string;
    url: string;
    caption: string;
    category: string;
  }>;
  currentIndex: number;
  isLightboxOpen: boolean;
}
```

---

## Terraform Resources (New)

Add to `infrastructure/modules/dynamodb/poi-table.tf`:

```hcl
module "poi_table_label" {
  source  = "cloudposse/label/null"
  version = "~> 0.25"

  namespace   = "booking"
  environment = var.environment
  name        = "pois"
}

module "poi_table" {
  source  = "terraform-aws-modules/dynamodb-table/aws"
  version = "~> 4.0"

  name         = module.poi_table_label.id
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "poi_id"

  attributes = [
    {
      name = "poi_id"
      type = "S"
    },
    {
      name = "category"
      type = "S"
    },
    {
      name = "display_order"
      type = "N"
    }
  ]

  global_secondary_indexes = [
    {
      name            = "category-order-index"
      hash_key        = "category"
      range_key       = "display_order"
      projection_type = "ALL"
    }
  ]

  tags = module.poi_table_label.tags
}

output "poi_table_name" {
  description = "Name of the POI DynamoDB table"
  value       = module.poi_table.dynamodb_table_id
}

output "poi_table_arn" {
  description = "ARN of the POI DynamoDB table"
  value       = module.poi_table.dynamodb_table_arn
}
```

---

## Data Migration

### Initial POI Seed

POI data can be seeded via a new Taskfile command:

```yaml
# In Taskfile.yaml
seed:pois:dev:
  desc: Seed POI data for dev environment
  cmds:
    - uv run python -m shared.scripts.seed_pois --env dev
```

The seed script reads from `backend/shared/data/pois.json` and writes to DynamoDB.

---

## Requirements Traceability

| Requirement | Data Entity | Notes |
|-------------|-------------|-------|
| FR-008 (blocked dates) | Availability | Existing table, no changes |
| FR-009 (price calculation) | Pricing | Existing table, no changes |
| FR-012 (guest details) | Guest | Existing table, no changes |
| FR-014 (backend integration) | All | Via generated OpenAPI client |
| FR-025 (POI markers) | **POI (new)** | New table required |
| FR-026 (POI details popup) | **POI (new)** | `description`, `distance_text` fields |
