"""Quesada Apartment booking agent tools.

This module exports all tools available to the booking agent.
Tools are organized by category:
- Availability: check_availability, get_calendar
- Pricing: get_pricing, calculate_total, get_seasonal_rates, check_minimum_stay, get_minimum_stay_info
- Reservations: create_reservation, get_reservation
- Payments: process_payment, get_payment_status, retry_payment
- Guest: get_guest_info, update_guest_details
- Auth: initiate_cognito_login, verify_cognito_otp, get_authenticated_guest (Cognito EMAIL_OTP + OAuth2 3LO)
- Area Info: get_area_info, get_recommendations
- Property: get_property_details, get_photos
"""

# Force rebuild: 2025-12-29T22:56:00Z
import logging

logger = logging.getLogger(__name__)
logger.info("[TOOLS] Loading tools module v3...")

from src.tools.area_info import get_area_info, get_recommendations
from src.tools.auth import (
    get_authenticated_guest,
    initiate_cognito_login,
    verify_cognito_otp,
)
from src.tools.property import get_photos, get_property_details
from src.tools.availability import check_availability, get_calendar
from src.tools.guest import (
    get_guest_info,
    initiate_verification,
    update_guest_details,
    verify_code,
)
from src.tools.payments import get_payment_status, process_payment, retry_payment
from src.tools.pricing import (
    calculate_total,
    check_minimum_stay,
    get_minimum_stay_info,
    get_pricing,
    get_seasonal_rates,
)
from src.tools.reservations import (
    cancel_reservation,
    create_reservation,
    get_reservation,
    modify_reservation,
)

# All tools for the booking agent
ALL_TOOLS = [
    # Availability tools
    check_availability,
    get_calendar,
    # Pricing tools
    get_pricing,
    calculate_total,
    get_seasonal_rates,
    check_minimum_stay,
    get_minimum_stay_info,
    # Reservation tools
    create_reservation,
    get_reservation,
    modify_reservation,
    cancel_reservation,
    # Payment tools
    process_payment,
    get_payment_status,
    retry_payment,
    # Guest profile tools
    get_guest_info,
    update_guest_details,
    # Auth tools (Cognito EMAIL_OTP passwordless)
    # Uses native Cognito USER_AUTH flow with EMAIL_OTP challenge
    initiate_cognito_login,
    verify_cognito_otp,
    # Area info tools
    get_area_info,
    get_recommendations,
    # Property tools
    get_property_details,
    get_photos,
]

logger.info(f"[TOOLS] ALL_TOOLS loaded with {len(ALL_TOOLS)} tools")
for i, tool in enumerate(ALL_TOOLS):
    logger.info(f"[TOOLS]   {i+1}. {tool.__name__}")

__all__ = [
    # Tool functions
    "check_availability",
    "get_calendar",
    "get_pricing",
    "calculate_total",
    "get_seasonal_rates",
    "check_minimum_stay",
    "get_minimum_stay_info",
    "create_reservation",
    "get_reservation",
    "modify_reservation",
    "cancel_reservation",
    "process_payment",
    "get_payment_status",
    "retry_payment",
    "initiate_verification",
    "verify_code",
    "get_guest_info",
    "update_guest_details",
    "initiate_cognito_login",
    "verify_cognito_otp",
    "get_authenticated_guest",
    "get_area_info",
    "get_recommendations",
    "get_property_details",
    "get_photos",
    # Tool collection
    "ALL_TOOLS",
]
