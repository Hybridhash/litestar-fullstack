"""Phone number validation and formatting utilities using the phonenumbers library."""

from __future__ import annotations

import phonenumbers


def validate_mobile(number: str) -> bool:
    """Validate that a string is a valid phone number."""
    try:
        parsed = phonenumbers.parse(number, None)
        return phonenumbers.is_valid_number(parsed)
    except phonenumbers.NumberParseException:
        return False


def format_e164(number: str) -> str:
    """Normalize a phone number to E.164 format (e.g. +966512345678)."""
    parsed = phonenumbers.parse(number, None)
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def get_region_code(number: str) -> str:
    """Extract ISO 3166-1 alpha-2 country code from a phone number (e.g. 'SA')."""
    try:
        parsed = phonenumbers.parse(number, None)
        region = phonenumbers.region_code_for_number(parsed)
    except phonenumbers.NumberParseException:
        return "UNKNOWN"
    else:
        return region or "UNKNOWN"
