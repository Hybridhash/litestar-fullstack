from __future__ import annotations

import nh3


def clean_text(value: str | None) -> str:
    """Strip unsafe HTML and whitespace from user-provided text."""
    if not value:
        return ""
    return nh3.clean(value, tags=set(), attributes={}).strip()


def escape_like(value: str, escape: str = "\\") -> str:
    """Escape SQL LIKE wildcards for literal matching."""
    if not value:
        return ""
    if escape not in {"\\", "!"}:
        msg = "Unsupported escape character for LIKE."
        raise ValueError(msg)
    escaped = value.replace(escape, escape + escape)
    escaped = escaped.replace("%", escape + "%")
    return escaped.replace("_", escape + "_")
