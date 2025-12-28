"""Summerhouse booking agent tools.

This module exports all tools available to the booking agent.
Tools are organized by category:
- Availability: check_availability, get_calendar
- Pricing: get_pricing, calculate_total, get_seasonal_rates, check_minimum_stay, get_minimum_stay_info
- Reservations: create_reservation, get_reservation
- Payments: process_payment, get_payment_status, retry_payment
- Guest: initiate_verification, verify_code, get_guest_info, update_guest_details
- Area Info: get_area_info, get_recommendations
- Property: get_property_details, get_photos
"""

from src.tools.area_info import get_area_info, get_recommendations
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
    # Guest verification tools
    initiate_verification,
    verify_code,
    get_guest_info,
    update_guest_details,
    # Area info tools
    get_area_info,
    get_recommendations,
    # Property tools
    get_property_details,
    get_photos,
]

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
    "get_area_info",
    "get_recommendations",
    "get_property_details",
    "get_photos",
    # Tool collection
    "ALL_TOOLS",
]
