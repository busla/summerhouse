"""Unit tests for Customer Pydantic models (T006a).

TDD Red Phase: Tests define expected behavior before implementation.

Tests CustomerCreate and CustomerUpdate models from customers.py route,
validating:
- Field validation rules (min/max length constraints)
- Optional fields and defaults
- Strict mode behavior
"""

import pytest
from pydantic import ValidationError


class TestCustomerCreateModel:
    """Test suite for CustomerCreate Pydantic model."""

    def test_import_model(self) -> None:
        """CustomerCreate can be imported from customers route."""
        from api.routes.customers import CustomerCreate

        assert CustomerCreate is not None

    def test_all_fields_optional(self) -> None:
        """All fields in CustomerCreate are optional."""
        from api.routes.customers import CustomerCreate

        # Should create successfully with no arguments
        customer = CustomerCreate()
        assert customer is not None

    def test_default_preferred_language_is_en(self) -> None:
        """preferred_language defaults to 'en' when not provided."""
        from api.routes.customers import CustomerCreate

        customer = CustomerCreate()
        assert customer.preferred_language == "en"

    def test_accepts_valid_name(self) -> None:
        """Accepts name within 2-100 character range."""
        from api.routes.customers import CustomerCreate

        customer = CustomerCreate(name="John Doe")
        assert customer.name == "John Doe"

    def test_name_minimum_length_2_chars(self) -> None:
        """Name must be at least 2 characters."""
        from api.routes.customers import CustomerCreate

        # Single character should fail
        with pytest.raises(ValidationError) as exc_info:
            CustomerCreate(name="J")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("name",)
        assert "at least 2" in errors[0]["msg"].lower()

    def test_name_maximum_length_100_chars(self) -> None:
        """Name must not exceed 100 characters."""
        from api.routes.customers import CustomerCreate

        # 101 characters should fail
        long_name = "A" * 101
        with pytest.raises(ValidationError) as exc_info:
            CustomerCreate(name=long_name)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("name",)
        assert "100" in errors[0]["msg"]

    def test_name_exactly_2_chars_valid(self) -> None:
        """Name with exactly 2 characters is valid."""
        from api.routes.customers import CustomerCreate

        customer = CustomerCreate(name="Jo")
        assert customer.name == "Jo"

    def test_name_exactly_100_chars_valid(self) -> None:
        """Name with exactly 100 characters is valid."""
        from api.routes.customers import CustomerCreate

        name_100 = "A" * 100
        customer = CustomerCreate(name=name_100)
        assert customer.name == name_100

    def test_accepts_valid_phone(self) -> None:
        """Accepts phone within 7-20 character range."""
        from api.routes.customers import CustomerCreate

        customer = CustomerCreate(phone="+34 612 345 678")
        assert customer.phone == "+34 612 345 678"

    def test_phone_minimum_length_7_chars(self) -> None:
        """Phone must be at least 7 characters."""
        from api.routes.customers import CustomerCreate

        # 6 characters should fail
        with pytest.raises(ValidationError) as exc_info:
            CustomerCreate(phone="123456")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("phone",)
        assert "at least 7" in errors[0]["msg"].lower()

    def test_phone_maximum_length_20_chars(self) -> None:
        """Phone must not exceed 20 characters."""
        from api.routes.customers import CustomerCreate

        # 21 characters should fail
        long_phone = "1" * 21
        with pytest.raises(ValidationError) as exc_info:
            CustomerCreate(phone=long_phone)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("phone",)
        assert "20" in errors[0]["msg"]

    def test_phone_exactly_7_chars_valid(self) -> None:
        """Phone with exactly 7 characters is valid."""
        from api.routes.customers import CustomerCreate

        customer = CustomerCreate(phone="1234567")
        assert customer.phone == "1234567"

    def test_phone_exactly_20_chars_valid(self) -> None:
        """Phone with exactly 20 characters is valid."""
        from api.routes.customers import CustomerCreate

        phone_20 = "1" * 20
        customer = CustomerCreate(phone=phone_20)
        assert customer.phone == phone_20

    def test_preferred_language_accepts_en(self) -> None:
        """preferred_language accepts 'en'."""
        from api.routes.customers import CustomerCreate

        customer = CustomerCreate(preferred_language="en")
        assert customer.preferred_language == "en"

    def test_preferred_language_accepts_es(self) -> None:
        """preferred_language accepts 'es'."""
        from api.routes.customers import CustomerCreate

        customer = CustomerCreate(preferred_language="es")
        assert customer.preferred_language == "es"

    def test_preferred_language_rejects_invalid(self) -> None:
        """preferred_language rejects values other than 'en' or 'es'."""
        from api.routes.customers import CustomerCreate

        with pytest.raises(ValidationError) as exc_info:
            CustomerCreate(preferred_language="fr")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("preferred_language",)

    def test_accepts_all_fields_together(self) -> None:
        """Accepts all fields when provided together."""
        from api.routes.customers import CustomerCreate

        customer = CustomerCreate(
            name="John Doe",
            phone="+34 612 345 678",
            preferred_language="es",
        )
        assert customer.name == "John Doe"
        assert customer.phone == "+34 612 345 678"
        assert customer.preferred_language == "es"

    def test_name_can_be_none(self) -> None:
        """name field accepts None explicitly."""
        from api.routes.customers import CustomerCreate

        customer = CustomerCreate(name=None)
        assert customer.name is None

    def test_phone_can_be_none(self) -> None:
        """phone field accepts None explicitly."""
        from api.routes.customers import CustomerCreate

        customer = CustomerCreate(phone=None)
        assert customer.phone is None


class TestCustomerUpdateModel:
    """Test suite for CustomerUpdate Pydantic model."""

    def test_import_model(self) -> None:
        """CustomerUpdate can be imported from customers route."""
        from api.routes.customers import CustomerUpdate

        assert CustomerUpdate is not None

    def test_all_fields_optional(self) -> None:
        """All fields in CustomerUpdate are optional."""
        from api.routes.customers import CustomerUpdate

        # Should create successfully with no arguments
        customer = CustomerUpdate()
        assert customer is not None

    def test_no_default_for_preferred_language(self) -> None:
        """preferred_language has no default (partial updates only set what's provided)."""
        from api.routes.customers import CustomerUpdate

        customer = CustomerUpdate()
        assert customer.preferred_language is None

    def test_accepts_valid_name(self) -> None:
        """Accepts name within 2-100 character range."""
        from api.routes.customers import CustomerUpdate

        customer = CustomerUpdate(name="Jane Doe")
        assert customer.name == "Jane Doe"

    def test_name_minimum_length_2_chars(self) -> None:
        """Name must be at least 2 characters."""
        from api.routes.customers import CustomerUpdate

        with pytest.raises(ValidationError) as exc_info:
            CustomerUpdate(name="J")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("name",)

    def test_name_maximum_length_100_chars(self) -> None:
        """Name must not exceed 100 characters."""
        from api.routes.customers import CustomerUpdate

        long_name = "A" * 101
        with pytest.raises(ValidationError) as exc_info:
            CustomerUpdate(name=long_name)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("name",)

    def test_accepts_valid_phone(self) -> None:
        """Accepts phone within 7-20 character range."""
        from api.routes.customers import CustomerUpdate

        customer = CustomerUpdate(phone="+34 612 345 678")
        assert customer.phone == "+34 612 345 678"

    def test_phone_minimum_length_7_chars(self) -> None:
        """Phone must be at least 7 characters."""
        from api.routes.customers import CustomerUpdate

        with pytest.raises(ValidationError) as exc_info:
            CustomerUpdate(phone="123456")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("phone",)

    def test_phone_maximum_length_20_chars(self) -> None:
        """Phone must not exceed 20 characters."""
        from api.routes.customers import CustomerUpdate

        long_phone = "1" * 21
        with pytest.raises(ValidationError) as exc_info:
            CustomerUpdate(phone=long_phone)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("phone",)

    def test_preferred_language_accepts_en(self) -> None:
        """preferred_language accepts 'en'."""
        from api.routes.customers import CustomerUpdate

        customer = CustomerUpdate(preferred_language="en")
        assert customer.preferred_language == "en"

    def test_preferred_language_accepts_es(self) -> None:
        """preferred_language accepts 'es'."""
        from api.routes.customers import CustomerUpdate

        customer = CustomerUpdate(preferred_language="es")
        assert customer.preferred_language == "es"

    def test_preferred_language_rejects_invalid(self) -> None:
        """preferred_language rejects values other than 'en' or 'es'."""
        from api.routes.customers import CustomerUpdate

        with pytest.raises(ValidationError) as exc_info:
            CustomerUpdate(preferred_language="de")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("preferred_language",)

    def test_accepts_partial_update_single_field(self) -> None:
        """Accepts partial update with only one field."""
        from api.routes.customers import CustomerUpdate

        customer = CustomerUpdate(name="Updated Name")
        assert customer.name == "Updated Name"
        assert customer.phone is None
        assert customer.preferred_language is None

    def test_model_dump_exclude_unset(self) -> None:
        """model_dump(exclude_unset=True) only includes provided fields."""
        from api.routes.customers import CustomerUpdate

        customer = CustomerUpdate(name="Updated Name")
        data = customer.model_dump(exclude_unset=True)

        assert data == {"name": "Updated Name"}
        assert "phone" not in data
        assert "preferred_language" not in data


class TestCustomerModelStrictMode:
    """Test that Customer models use strict mode."""

    def test_customer_create_rejects_wrong_type_for_name(self) -> None:
        """CustomerCreate rejects non-string for name (strict mode)."""
        from api.routes.customers import CustomerCreate

        with pytest.raises(ValidationError):
            CustomerCreate(name=123)  # type: ignore

    def test_customer_create_rejects_wrong_type_for_phone(self) -> None:
        """CustomerCreate rejects non-string for phone (strict mode)."""
        from api.routes.customers import CustomerCreate

        with pytest.raises(ValidationError):
            CustomerCreate(phone=1234567)  # type: ignore

    def test_customer_update_rejects_wrong_type_for_name(self) -> None:
        """CustomerUpdate rejects non-string for name (strict mode)."""
        from api.routes.customers import CustomerUpdate

        with pytest.raises(ValidationError):
            CustomerUpdate(name=123)  # type: ignore

    def test_customer_update_rejects_wrong_type_for_phone(self) -> None:
        """CustomerUpdate rejects non-string for phone (strict mode)."""
        from api.routes.customers import CustomerUpdate

        with pytest.raises(ValidationError):
            CustomerUpdate(phone=1234567)  # type: ignore
