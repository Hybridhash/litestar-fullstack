"""Mobile number and Twilio OTP services."""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService

from app.db.models.mobile_number import MobileNumber

if TYPE_CHECKING:
    from twilio.rest import Client as TwilioClient  # type: ignore[import-untyped]

    from app.config.base import TwilioSettings

logger = logging.getLogger(__name__)

__all__ = (
    "OTP_CODE_TTL",
    "OTP_MAX_ATTEMPTS",
    "VERIFIED_MOBILE_TTL",
    "MobileNumberService",
    "TwilioOTPService",
    "_otp_code_ttl",
    "_otp_max_attempts",
    "_verified_mobile_ttl",
    "check_otp_rate_limit",
    "clear_otp_send_cooldown",
    "delete_otp_code",
    "delete_verified_mobile",
    "get_otp_code",
    "get_otp_send_cooldown",
    "get_verified_mobile",
    "get_verified_mobile_ttl",
    "increment_otp_attempts",
    "increment_otp_check_attempts",
    "set_otp_send_cooldown",
    "store_otp_code",
    "store_verified_mobile",
)


@lru_cache(maxsize=1)
def _get_otp_settings() -> TwilioSettings:
    """Lazy-load OTP settings from the app config."""
    from app.config import get_settings  # noqa: PLC0415

    return get_settings().twilio


def _otp_code_ttl() -> int:
    return _get_otp_settings().OTP_CODE_TTL


def _otp_attempts_ttl() -> int:
    return _get_otp_settings().OTP_ATTEMPTS_TTL


def _otp_send_attempts_ttl() -> int:
    return _get_otp_settings().OTP_SEND_ATTEMPTS_TTL


def _otp_max_attempts() -> int:
    return _get_otp_settings().OTP_MAX_ATTEMPTS


def _verified_mobile_ttl() -> int:
    return _get_otp_settings().VERIFIED_MOBILE_TTL


OTP_CODE_TTL = _otp_code_ttl()
OTP_MAX_ATTEMPTS = _otp_max_attempts()
VERIFIED_MOBILE_TTL = _verified_mobile_ttl()


def _mask_mobile(number: str) -> str:
    if len(number) <= 8:
        return number
    return number[:4] + "•" * max(0, len(number) - 8) + number[-4:]


def __getattr__(name: str) -> int:
    """Expose OTP settings as module attributes without freezing values at import."""
    if name == "OTP_CODE_TTL":
        return _otp_code_ttl()
    if name == "OTP_MAX_ATTEMPTS":
        return _otp_max_attempts()
    if name == "VERIFIED_MOBILE_TTL":
        return _verified_mobile_ttl()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


class MobileNumberService(SQLAlchemyAsyncRepositoryService[MobileNumber]):
    """Database operations for mobile numbers."""

    class MobileNumberRepository(SQLAlchemyAsyncRepository[MobileNumber]):
        model_type = MobileNumber

    repository_type = MobileNumberRepository
    match_fields = ["number"]


class TwilioOTPService:
    """Sends backend-generated OTP codes via direct WhatsApp messaging."""

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        whatsapp_from: str,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._whatsapp_from = whatsapp_from
        self._client: TwilioClient | None = None

    @property
    def client(self) -> TwilioClient:
        if self._client is None:
            from twilio.rest import Client  # noqa: PLC0415

            self._client = Client(self._account_sid, self._auth_token)
        return self._client

    @staticmethod
    def _as_whatsapp_address(number: str) -> str:
        return number if number.startswith("whatsapp:") else f"whatsapp:{number}"

    @staticmethod
    def _expiry_text() -> str:
        ttl_seconds = _otp_code_ttl()
        ttl_minutes, remainder = divmod(ttl_seconds, 60)
        if ttl_minutes and remainder == 0:
            unit = "minute" if ttl_minutes == 1 else "minutes"
            return f"{ttl_minutes} {unit}"
        unit = "second" if ttl_seconds == 1 else "seconds"
        return f"{ttl_seconds} {unit}"

    async def send_otp(self, mobile: str, code: str) -> bool:
        """Send an OTP via direct WhatsApp messaging."""
        try:
            message = await asyncio.to_thread(
                self.client.messages.create,
                from_=self._as_whatsapp_address(self._whatsapp_from),
                to=self._as_whatsapp_address(mobile),
                body=f"Your verification code is {code}. It expires in {self._expiry_text()}.",
            )
            return bool(message.sid)
        except Exception:
            logger.exception("Failed to send OTP to %s", _mask_mobile(mobile))
            return False


def _redis_key(*parts: str) -> str:
    return ":".join(("accounts:otp", *parts))


async def check_otp_rate_limit(redis: Any, mobile: str) -> bool:
    """Return True if the mobile has exceeded OTP send attempts. Redis client expected."""
    key = _redis_key("otp_attempts", mobile)
    count = await redis.get(key)
    return count is not None and int(count) >= _otp_max_attempts()


async def increment_otp_attempts(redis: Any, mobile: str) -> None:
    """Increment OTP send attempt counter in Redis."""
    key = _redis_key("otp_attempts", mobile)
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, _otp_send_attempts_ttl())
    await pipe.execute()


async def set_otp_send_cooldown(redis: Any, mobile: str) -> None:
    """Set the resend cooldown key for OTP sends."""
    key = _redis_key("otp_cooldown", mobile)
    await redis.set(key, b"1", ex=_otp_code_ttl())


async def clear_otp_send_cooldown(redis: Any, mobile: str) -> None:
    """Clear OTP resend cooldown to allow a fresh code request immediately."""
    key = _redis_key("otp_cooldown", mobile)
    await redis.delete(key)


async def get_otp_send_cooldown(redis: Any, mobile: str) -> int:
    """Return remaining cooldown seconds for OTP send requests."""
    key = _redis_key("otp_cooldown", mobile)
    ttl = await redis.ttl(key)
    if ttl is None or ttl < 0:
        return 0
    return int(ttl)


async def store_otp_code(redis: Any, verification_key: str, mobile: str, code: str) -> None:
    """Store OTP code in Redis scoped by verification key and mobile."""
    key = _redis_key("otp_code", verification_key, mobile)
    await redis.set(key, code.encode(), ex=_otp_code_ttl())
    await redis.delete(_redis_key("otp_check_attempts", verification_key, mobile))


async def get_otp_code(redis: Any, verification_key: str, mobile: str) -> str | None:
    """Retrieve OTP code from Redis."""
    value = await redis.get(_redis_key("otp_code", verification_key, mobile))
    if value is None:
        return None
    return value.decode() if isinstance(value, bytes) else str(value)


async def delete_otp_code(redis: Any, verification_key: str, mobile: str) -> None:
    """Delete OTP code and related check-attempt key."""
    await redis.delete(_redis_key("otp_code", verification_key, mobile))
    await redis.delete(_redis_key("otp_check_attempts", verification_key, mobile))


async def increment_otp_check_attempts(redis: Any, verification_key: str, mobile: str) -> int:
    """Increment OTP verification-check attempts and return the new count."""
    key = _redis_key("otp_check_attempts", verification_key, mobile)
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, _otp_attempts_ttl())
    results = await pipe.execute()
    return int(results[0]) if results else 0


async def store_verified_mobile(redis: Any, verification_key: str, mobile: str) -> None:
    """Store verified mobile in Redis keyed to a stable verification key."""
    key = _redis_key("verified_mobile", verification_key)
    await redis.set(key, mobile.encode(), ex=_verified_mobile_ttl())


async def get_verified_mobile(redis: Any, verification_key: str) -> str | None:
    """Retrieve verified mobile from Redis. Returns None if expired/missing."""
    key = _redis_key("verified_mobile", verification_key)
    value = await redis.get(key)
    if value is None:
        return None
    return value.decode() if isinstance(value, bytes) else str(value)


async def get_verified_mobile_ttl(redis: Any, verification_key: str) -> int:
    """Return remaining seconds for the verified-mobile pending state."""
    key = _redis_key("verified_mobile", verification_key)
    ttl = await redis.ttl(key)
    if ttl is None or ttl < 0:
        return 0
    return int(ttl)


async def delete_verified_mobile(redis: Any, verification_key: str) -> None:
    """Delete verified mobile from Redis after successful signup."""
    key = _redis_key("verified_mobile", verification_key)
    await redis.delete(key)
