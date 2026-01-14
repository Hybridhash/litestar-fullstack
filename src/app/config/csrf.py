"""CSRF configuration and validation."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog
from jinja2 import pass_context
from litestar.config.csrf import CSRFConfig

if TYPE_CHECKING:
    from app.config.base import AppSettings


def validate_csrf_settings(app_settings: AppSettings) -> None:
    """Validate CSRF configuration and log warnings for potential security issues.

    Args:
        app_settings: Application settings instance to validate.
    """
    logger = structlog.get_logger()

    if len(app_settings.SECRET_KEY) < 32:
        logger.warning(
            "CSRF secret key length below recommended minimum",
            length=len(app_settings.SECRET_KEY),
            recommended_minimum=32,
        )

    if app_settings.URL.lower().startswith("https://") and not app_settings.CSRF_COOKIE_SECURE:
        logger.warning(
            "CSRF cookie secure flag should be enabled for HTTPS URLs",
            url=app_settings.URL,
            csrf_cookie_secure=app_settings.CSRF_COOKIE_SECURE,
        )


def create_csrf_config(app_settings: AppSettings) -> CSRFConfig:
    """Create CSRF configuration from application settings.

    Args:
        app_settings: Application settings instance.

    Returns:
        Configured CSRFConfig instance.
    """
    validate_csrf_settings(app_settings)

    return CSRFConfig(
        secret=app_settings.SECRET_KEY,
        header_name=app_settings.CSRF_HEADER_NAME,
        cookie_secure=app_settings.CSRF_COOKIE_SECURE,
        cookie_name=app_settings.CSRF_COOKIE_NAME,
    )


@pass_context
def csrf_token(context: dict[str, object]) -> str:
    """Extract the CSRF token value from a rendered input in the Jinja context."""
    csrf_input = context.get("csrf_input")
    if not csrf_input:
        return ""
    match = re.search(r"value=[\"']([^\"']+)[\"']", str(csrf_input))
    return match.group(1) if match else ""
