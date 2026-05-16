from __future__ import annotations

import enum


class MobileType(str, enum.Enum):
    """Type of mobile number."""

    PERSONAL = "PERSONAL"
    BUSINESS = "BUSINESS"
