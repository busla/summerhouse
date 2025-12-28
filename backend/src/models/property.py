"""Property models for apartment details and photos.

These models represent the static property information for the
Summerhouse vacation rental apartment.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PhotoCategory(str, Enum):
    """Photo category enumeration."""

    EXTERIOR = "exterior"
    LIVING_ROOM = "living_room"
    BEDROOM = "bedroom"
    BATHROOM = "bathroom"
    KITCHEN = "kitchen"
    TERRACE = "terrace"
    POOL = "pool"
    GARDEN = "garden"
    VIEW = "view"
    OTHER = "other"


class Address(BaseModel):
    """Property address."""

    model_config = ConfigDict(strict=True)

    street: str
    city: str
    region: str
    country: str
    postal_code: str


class Coordinates(BaseModel):
    """Geographic coordinates."""

    model_config = ConfigDict(strict=True)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class Photo(BaseModel):
    """Property photo."""

    model_config = ConfigDict(strict=True)

    id: str
    url: str
    caption: str
    category: PhotoCategory
    display_order: int = 0

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class Property(BaseModel):
    """Complete property details."""

    model_config = ConfigDict(strict=True)

    property_id: str
    name: str
    description: str
    address: Address
    coordinates: Coordinates
    bedrooms: int = Field(ge=0)
    bathrooms: int = Field(ge=0)
    max_guests: int = Field(ge=1)
    amenities: list[str] = Field(default_factory=list)
    photos: list[Photo] = Field(default_factory=list)
    check_in_time: str = "15:00"
    check_out_time: str = "10:00"
    house_rules: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class PropertySummary(BaseModel):
    """Summary of property for quick reference."""

    model_config = ConfigDict(strict=True)

    property_id: str
    name: str
    bedrooms: int
    bathrooms: int
    max_guests: int
    amenities_count: int
    photo_count: int


class PropertyDetailsResponse(BaseModel):
    """Response model for property details."""

    model_config = ConfigDict(strict=True)

    property: Property
    status: str = "success"
    message: str = ""


class PhotosResponse(BaseModel):
    """Response model for photo requests."""

    model_config = ConfigDict(strict=True)

    photos: list[Photo]
    category: PhotoCategory | None = None
    total_count: int
    status: str = "success"
    message: str = ""
