"""E2E test configuration.

This conftest overrides fixtures from the parent conftest.py that are not
needed for E2E tests (which make HTTP calls to live APIs, not mocked services).
"""

from typing import Generator

import pytest


@pytest.fixture(autouse=True)
def reset_dynamodb_singleton() -> Generator[None, None, None]:
    """Override parent fixture - E2E tests don't use mocked DynamoDB.

    The parent conftest has an autouse fixture that imports shared.services,
    but E2E tests only make HTTP calls to live APIs and don't need the
    shared package in their Python path.
    """
    yield  # No-op: E2E tests use the live deployed API, not mocked DynamoDB
