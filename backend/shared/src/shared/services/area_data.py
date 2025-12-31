"""Area data loading and management service.

Provides data loading utilities for area information (local attractions, etc.).
This module is separate from tools to avoid strands dependency in API layer.
"""

import json
import logging
from pathlib import Path
from typing import Any

from shared.models import (
    AreaCategory,
    AreaInfo,
)

logger = logging.getLogger(__name__)


# In-memory data store for area information
# This can be loaded from JSON or DynamoDB in production
_AREA_DATA: list[AreaInfo] = []
_DATA_LOADED: bool = False


def get_area_data_store() -> list[AreaInfo]:
    """Get the current area data store."""
    return _AREA_DATA


def set_area_data_store(data: list[AreaInfo]) -> None:
    """Set the area data store (for testing or initialization)."""
    global _AREA_DATA
    _AREA_DATA = data


def load_area_data_from_dicts(data: list[dict[str, Any]]) -> None:
    """Load area data from a list of dictionaries.

    Useful for loading from JSON files or test fixtures.
    """
    global _AREA_DATA
    _AREA_DATA = []
    for item in data:
        # Convert category string to enum if needed
        if isinstance(item.get("category"), str):
            item = item.copy()
            item["category"] = AreaCategory(item["category"])
        _AREA_DATA.append(AreaInfo(**item))


def load_area_data_from_json(json_path: Path | str | None = None) -> int:
    """Load area data from JSON file.

    Args:
        json_path: Path to JSON file. If None, uses default location.

    Returns:
        Number of places loaded.

    Raises:
        FileNotFoundError: If JSON file doesn't exist.
        json.JSONDecodeError: If JSON is invalid.
    """
    global _DATA_LOADED

    if json_path is None:
        # Default to bundled data file
        json_path = Path(__file__).parent.parent / "data" / "area_info.json"

    json_path = Path(json_path)

    with open(json_path) as f:
        data = json.load(f)

    places = data.get("places", [])
    load_area_data_from_dicts(places)
    _DATA_LOADED = True

    logger.info(f"Loaded {len(places)} area info places from {json_path}")
    return len(places)


def ensure_area_data_loaded() -> None:
    """Ensure area data is loaded, loading from default source if needed."""
    global _DATA_LOADED
    if not _DATA_LOADED and len(_AREA_DATA) == 0:
        try:
            load_area_data_from_json()
        except FileNotFoundError:
            logger.warning("Area info data file not found, starting with empty data")
            _DATA_LOADED = True  # Mark as loaded (empty) to prevent repeated attempts
