from __future__ import annotations

import nh3


def clean_text(value: str | None) -> str:
    """Strip unsafe HTML and whitespace from user-provided text."""
    if not value:
        return ""
    return nh3.clean(value, tags=set(), attributes={}).strip()
