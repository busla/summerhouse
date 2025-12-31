"""Property data loading and management service.

Provides data loading utilities for property information.
This module is separate from tools to avoid strands dependency in API layer.
"""

import json
import logging
from pathlib import Path
from typing import Any

from shared.models import (
    Photo,
    PhotoCategory,
    Property,
)

logger = logging.getLogger(__name__)


# In-memory data store for property information
_PROPERTY_DATA: Property | None = None
_DATA_LOADED: bool = False


def get_property_data_store() -> Property | None:
    """Get the current property data store."""
    return _PROPERTY_DATA


def set_property_data_store(data: Property | None) -> None:
    """Set the property data store (for testing or initialization)."""
    global _PROPERTY_DATA, _DATA_LOADED
    _PROPERTY_DATA = data
    # If setting to None, also reset the loaded flag to prevent auto-loading
    if data is None:
        _DATA_LOADED = True  # Prevent auto-loading in tests


def load_property_data_from_dict(data: dict[str, Any]) -> None:
    """Load property data from a dictionary.

    Useful for loading from JSON files or test fixtures.
    """
    global _PROPERTY_DATA

    # Parse photos with category enum conversion
    photos_data = data.get("photos", [])
    photos: list[Photo] = []
    for photo_dict in photos_data:
        photo_dict = photo_dict.copy()
        if isinstance(photo_dict.get("category"), str):
            photo_dict["category"] = PhotoCategory(photo_dict["category"])
        photos.append(Photo(**photo_dict))

    # Build the Property model
    property_data = data.copy()
    property_data["photos"] = photos
    _PROPERTY_DATA = Property(**property_data)


def load_property_data_from_json(json_path: Path | str | None = None) -> Property:
    """Load property data from JSON file.

    Args:
        json_path: Path to JSON file. If None, uses default location.

    Returns:
        The loaded Property model.

    Raises:
        FileNotFoundError: If JSON file doesn't exist.
        json.JSONDecodeError: If JSON is invalid.
    """
    global _DATA_LOADED

    if json_path is None:
        # Default to bundled data file
        json_path = Path(__file__).parent.parent / "data" / "property.json"

    json_path = Path(json_path)

    with open(json_path) as f:
        data = json.load(f)

    property_data = data.get("property", {})
    load_property_data_from_dict(property_data)
    _DATA_LOADED = True

    logger.info(f"Loaded property data from {json_path}")
    return _PROPERTY_DATA  # type: ignore


def ensure_property_data_loaded() -> None:
    """Ensure property data is loaded, loading from default source if needed."""
    global _DATA_LOADED
    if not _DATA_LOADED and _PROPERTY_DATA is None:
        try:
            load_property_data_from_json()
        except FileNotFoundError:
            logger.warning("Property data file not found, starting with empty data")
            _DATA_LOADED = True  # Mark as loaded (empty) to prevent repeated attempts
