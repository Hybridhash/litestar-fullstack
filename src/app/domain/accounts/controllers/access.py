"""User Account Controllers."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, cast

from advanced_alchemy.exceptions import DuplicateKeyError
from advanced_alchemy.utils.text import slugify
from litestar import Controller, Response, get, post
from litestar.di import Provide
from litestar.enums import MediaType, RequestEncodingType
from litestar.exceptions import PermissionDeniedException
from litestar.params import Body
from litestar.plugins.htmx import HTMXRequest, HTMXTemplate
from litestar.response import Template
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_409_CONFLICT, HTTP_429_TOO_MANY_REQUESTS

from app.config.base import get_settings
from app.domain.accounts import urls
from app.domain.accounts.deps import provide_users_service
from app.domain.accounts.guards import auth, requires_active_user
from app.domain.accounts.mobile_service import (
    MobileNumberService,
    TwilioOTPService,
    _otp_code_ttl,
    _otp_max_attempts,
    _verified_mobile_ttl,
    check_otp_rate_limit,
    clear_otp_send_cooldown,
    delete_otp_code,
    delete_verified_mobile,
    get_otp_code,
    get_otp_send_cooldown,
    get_verified_mobile,
    get_verified_mobile_ttl,
    increment_otp_attempts,
    increment_otp_check_attempts,
    set_otp_send_cooldown,
    store_otp_code,
    store_verified_mobile,
)
from app.domain.accounts.schemas import (
    AccountLogin,
    AccountRegister,
    OTPCheckRequest,
    OTPSendRequest,
    User,
    UserProfileUpdate,
)
from app.domain.accounts.services import RoleService
from app.lib.deps import create_service_provider
from app.lib.phone import format_e164, get_region_code, validate_mobile

if TYPE_CHECKING:
    from litestar.security.jwt import OAuth2Login
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db import models as m
    from app.domain.accounts.services import UserService


EMAIL_BASIC_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
logger = logging.getLogger(__name__)

settings = get_settings()
_twilio_otp = TwilioOTPService(
    account_sid=settings.twilio.ACCOUNT_SID,
    auth_token=settings.twilio.AUTH_TOKEN,
    whatsapp_from=settings.twilio.WHATSAPP_FROM,
)
VERIFICATION_COOKIE_NAME = "registration_verification_key"
_VERIFICATION_KEY_BYTES = 32
_VERIFICATION_SIGNATURE_SEPARATOR = "."


def _verification_key_signature(token: str) -> str:
    return hmac.new(
        settings.app.SECRET_KEY.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _new_verification_key() -> str:
    token = secrets.token_urlsafe(_VERIFICATION_KEY_BYTES)
    return f"{token}{_VERIFICATION_SIGNATURE_SEPARATOR}{_verification_key_signature(token)}"


def _validated_verification_key(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    token, separator, signature = raw_value.partition(_VERIFICATION_SIGNATURE_SEPARATOR)
    if separator != _VERIFICATION_SIGNATURE_SEPARATOR or len(token) < 43 or len(signature) != 64:
        return None
    expected_signature = _verification_key_signature(token)
    if not hmac.compare_digest(signature, expected_signature):
        return None
    return raw_value


def _get_verification_key(request: object) -> str | None:
    """Get a stable key used to bind mobile verification state across requests."""
    cookies = cast("dict[str, str]", getattr(request, "cookies", {}))
    return _validated_verification_key(cookies.get(VERIFICATION_COOKIE_NAME))


def _is_mobile_duplicate_error(exc: Exception) -> bool:
    """Return True when a duplicate-key error points to mobile number uniqueness."""
    detail = str(getattr(exc, "detail", exc)).lower()
    return "mobile_number" in detail or "ix_mobile_number_number" in detail


def _first_form_value(value: str | list[str]) -> str:
    """Normalize repeated form keys to the first submitted value."""
    if isinstance(value, list):
        return value[0] if value else ""
    return value


def _set_verification_cookie(response: Template | HTMXTemplate | Response, verification_key: str) -> None:
    """Persist a stable verification key cookie for registration OTP state."""
    response.set_cookie(
        VERIFICATION_COOKIE_NAME,
        verification_key,
        httponly=True,
        path="/",
        samesite="lax",
    )


def _allow_dev_otp_fallback() -> bool:
    app_url = settings.app.URL.lower()
    return not settings.twilio.is_configured and (
        settings.app.DEBUG or "localhost" in app_url or "127.0.0.1" in app_url
    )


class AccessController(Controller):
    """User login and registration."""

    tags = ["Access"]
    dependencies = {
        "users_service": Provide(provide_users_service),
        "roles_service": Provide(create_service_provider(RoleService)),
        "mobile_service": Provide(create_service_provider(MobileNumberService)),
    }

    def _feedback_response(
        self,
        request: HTMXRequest,
        message: str,
        status_code: int = 200,
    ) -> HTMXTemplate | Response:
        if request.htmx:
            return HTMXTemplate(
                template_name="partials/feedback.jinja", context={"message": message}, status_code=status_code
            )
        return Response({"message": message}, status_code=status_code)

    def _mobile_availability_response(
        self,
        request: HTMXRequest,
        *,
        message: str,
        exists: bool,
        valid: bool,
        status_code: int,
    ) -> HTMXTemplate | Response:
        if request.htmx:
            response = HTMXTemplate(
                template_name="partials/feedback.jinja",
                context={"message": message},
                status_code=200,
            )
            response.headers["HX-Trigger"] = json.dumps({"mobile-availability": {"exists": exists, "valid": valid}})
            return response
        return Response({"message": message, "exists": exists, "valid": valid}, status_code=status_code)

    def _otp_section_response(
        self,
        *,
        mobile: str,
        message: str,
        status_code: int = 200,
        variant: str = "info",
        dev_code: str | None = None,
    ) -> HTMXTemplate:
        return HTMXTemplate(
            template_name="partials/otp_input.jinja",
            context={
                "mobile": mobile,
                "message": message,
                "variant": variant,
                "dev_code": dev_code,
                "otp_delivery_label": settings.twilio.otp_delivery_label,
                "otp_delivery_message": settings.twilio.otp_delivery_message,
            },
            status_code=status_code,
        )

    def _already_verified_mobile_response(
        self,
        request: HTMXRequest,
        *,
        remaining: int,
    ) -> HTMXTemplate | Response:
        message = (
            "This phone number is already verified for this registration. "
            f"Complete account creation now or re-verify in {remaining} seconds."
        )
        if request.htmx:
            response = HTMXTemplate(
                template_name="partials/feedback.jinja",
                context={"message": message},
                status_code=200,
            )
            response.headers["HX-Trigger"] = json.dumps({"mobile-verified": {"seconds": remaining}})
            return response
        return Response({"message": message, "seconds": remaining}, status_code=200)

    async def _otp_cooldown_response(
        self,
        request: HTMXRequest,
        *,
        redis: object,
        verification_key: str,
        mobile: str,
        cooldown_remaining: int,
    ) -> HTMXTemplate | Response:
        message = f"Code already sent. Please wait {cooldown_remaining} seconds before requesting a new code."
        if not request.htmx:
            return Response({"message": message}, status_code=HTTP_429_TOO_MANY_REQUESTS)

        stored_code = await get_otp_code(redis, verification_key, mobile)
        if stored_code is not None:
            response = self._otp_section_response(
                mobile=mobile,
                message=message,
                status_code=200,
                variant="warning",
            )
        else:
            response = HTMXTemplate(
                template_name="partials/feedback.jinja",
                context={"message": message},
                status_code=200,
            )
        response.headers["HX-Trigger"] = json.dumps({"otp-cooldown": {"seconds": cooldown_remaining}})
        return response

    @get(operation_id="WebLoginPage", path="/login", exclude_from_auth=True, include_in_schema=False)
    async def login_page(self) -> Template:
        return Template(template_name="site/login.jinja", context={"error": ""}, media_type=MediaType.HTML)

    @get(operation_id="WebRegisterPage", path="/register", exclude_from_auth=True, include_in_schema=False)
    async def register_page(self, request: HTMXRequest) -> Template:
        verification_key = _get_verification_key(request) or _new_verification_key()
        mobile_verified = False
        mobile_verified_ttl = 0
        masked_mobile = ""
        redis = settings.redis.client
        verified_number = await get_verified_mobile(redis, verification_key)
        if verified_number:
            mobile_verified = True
            mobile_verified_ttl = await get_verified_mobile_ttl(redis, verification_key)
            # Mask number for display: +966•••••5678
            masked_mobile = (
                verified_number[:4] + "•" * max(0, len(verified_number) - 8) + verified_number[-4:]
                if len(verified_number) > 8
                else verified_number
            )
        response = Template(
            template_name="site/register.jinja",
            context={
                "error": "",
                "mobile_verified": mobile_verified,
                "mobile_verified_ttl": mobile_verified_ttl,
                "masked_mobile": masked_mobile,
                "otp_delivery_label": settings.twilio.otp_delivery_label,
            },
            media_type=MediaType.HTML,
        )
        _set_verification_cookie(response, verification_key)
        return response

    @post(operation_id="AccountLogin", path=urls.ACCOUNT_LOGIN, exclude_from_auth=True)
    async def login(
        self,
        request: HTMXRequest,
        users_service: UserService,
        data: Annotated[AccountLogin, Body(title="OAuth2 Login", media_type=RequestEncodingType.URL_ENCODED)],
    ) -> Response[OAuth2Login] | HTMXTemplate:
        """Authenticate a user."""
        try:
            user = await users_service.authenticate(data.username, data.password)
        except PermissionDeniedException as exc:
            if request.htmx:
                message = getattr(exc, "detail", "Unable to sign in with those credentials.")
                return HTMXTemplate(template_name="partials/feedback.jinja", context={"message": message})
            raise

        response = auth.login(user.email)
        if request.htmx:
            response.headers["HX-Redirect"] = "/dashboard"
        return response

    @post(operation_id="AccountLogout", path=urls.ACCOUNT_LOGOUT, exclude_from_auth=True)
    async def logout(self, request: HTMXRequest) -> Response:
        """Account Logout"""

        request.cookies.pop(auth.key, None)
        request.clear_session()

        response = Response({"message": "OK"}, status_code=200)
        response.delete_cookie(auth.key)

        if request.htmx:
            response.headers["HX-Redirect"] = "/login"
        return response

    # ── OTP Verification ──────────────────────────────────────────────

    @post(operation_id="OTPSend", path=urls.ACCOUNT_VERIFY_SEND_OTP, exclude_from_auth=True)
    async def send_otp(  # noqa: PLR0911
        self,
        request: HTMXRequest,
        mobile_service: MobileNumberService,
        data: Annotated[OTPSendRequest, Body(media_type=RequestEncodingType.URL_ENCODED)],
    ) -> HTMXTemplate | Response:
        """Send OTP to a mobile number via WhatsApp."""
        redis = settings.redis.client
        mobile_raw = _first_form_value(data.mobile).strip()
        verification_key = _get_verification_key(request)
        if not verification_key:
            return self._feedback_response(
                request, "Session expired. Refresh the page and try again.", HTTP_400_BAD_REQUEST
            )

        # Validate format
        if not validate_mobile(mobile_raw):
            return self._feedback_response(
                request,
                "Invalid mobile number format. Use international format with country code (e.g. +966512345678).",
                HTTP_400_BAD_REQUEST,
            )

        mobile = format_e164(mobile_raw)

        verified_mobile = await get_verified_mobile(redis, verification_key)
        if verified_mobile is not None:
            remaining = await get_verified_mobile_ttl(redis, verification_key)
            return self._already_verified_mobile_response(request, remaining=remaining)

        # Check if number already registered
        existing = await mobile_service.get_one_or_none(number=mobile)
        if existing is not None:
            return self._mobile_availability_response(
                request,
                message="This mobile number is already registered.",
                exists=True,
                valid=True,
                status_code=HTTP_409_CONFLICT,
            )

        cooldown_remaining = await get_otp_send_cooldown(redis, mobile)
        if cooldown_remaining > 0:
            return await self._otp_cooldown_response(
                request,
                redis=redis,
                verification_key=verification_key,
                mobile=mobile,
                cooldown_remaining=cooldown_remaining,
            )

        if await check_otp_rate_limit(redis, mobile):
            return self._feedback_response(
                request,
                "Too many verification codes requested. Please try again later.",
                HTTP_429_TOO_MANY_REQUESTS,
            )

        otp_code = f"{secrets.randbelow(1_000_000):06d}"
        dev_code: str | None = None
        if _allow_dev_otp_fallback():
            dev_code = otp_code
            sent = True
            logger.warning("Using development OTP fallback for %s", mobile)
        else:
            sent = await _twilio_otp.send_otp(mobile, otp_code)
        if not sent:
            return self._feedback_response(
                request, "Failed to send verification code. Please try again.", HTTP_400_BAD_REQUEST
            )

        await store_otp_code(redis, verification_key, mobile, otp_code)
        await increment_otp_attempts(redis, mobile)
        await set_otp_send_cooldown(redis, mobile)

        if request.htmx:
            response = self._otp_section_response(
                mobile=mobile,
                message=f"A verification code has been sent by {settings.twilio.otp_delivery_message}.",
                dev_code=dev_code,
            )
            response.headers["HX-Trigger"] = json.dumps(
                {
                    "otp-cooldown": {"seconds": _otp_code_ttl()},
                    "otp-sent": {"mobile": mobile},
                    "mobile-availability": {"exists": False, "valid": True},
                }
            )
            return response
        return Response({"message": "OTP sent"}, status_code=200)

    @post(operation_id="OTPCheck", path=urls.ACCOUNT_VERIFY_CHECK_OTP, exclude_from_auth=True)
    async def check_otp(  # noqa: PLR0911
        self,
        request: HTMXRequest,
        data: Annotated[OTPCheckRequest, Body(media_type=RequestEncodingType.URL_ENCODED)],
    ) -> HTMXTemplate | Response:
        """Verify an OTP code."""
        redis = settings.redis.client
        mobile_raw = _first_form_value(data.mobile).strip()
        code = _first_form_value(data.code).strip()
        verification_key = _get_verification_key(request)
        if not verification_key:
            return self._feedback_response(
                request, "Session expired. Refresh the page and try again.", HTTP_400_BAD_REQUEST
            )

        if not validate_mobile(mobile_raw):
            return self._feedback_response(request, "Invalid mobile number.", HTTP_400_BAD_REQUEST)

        if not code.isdigit() or len(code) != 6:
            if request.htmx:
                return self._otp_section_response(
                    mobile=mobile_raw,
                    message="Please enter a valid 6-digit code.",
                    status_code=HTTP_400_BAD_REQUEST,
                    variant="error",
                )
            return self._feedback_response(request, "Please enter a valid 6-digit code.", HTTP_400_BAD_REQUEST)

        mobile = format_e164(mobile_raw)
        stored_code = await get_otp_code(redis, verification_key, mobile)
        if stored_code is None:
            if request.htmx:
                return self._otp_section_response(
                    mobile=mobile,
                    message="Invalid or expired code. Please try again.",
                    status_code=HTTP_400_BAD_REQUEST,
                    variant="error",
                )
            return self._feedback_response(request, "Invalid or expired code. Please try again.", HTTP_400_BAD_REQUEST)
        attempt_count = await increment_otp_check_attempts(redis, verification_key, mobile)
        if attempt_count >= _otp_max_attempts():
            await delete_otp_code(redis, verification_key, mobile)
            await clear_otp_send_cooldown(redis, mobile)
            message = "Too many incorrect codes. Please request a new code."
            if request.htmx:
                response = HTMXTemplate(
                    template_name="partials/feedback.jinja",
                    context={"message": message, "variant": "warning"},
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                )
                response.headers["HX-Trigger"] = json.dumps({"otp-cooldown": {"seconds": 0}})
                return response
            return self._feedback_response(request, message, HTTP_429_TOO_MANY_REQUESTS)
        is_valid_code = secrets.compare_digest(stored_code, code)
        if not is_valid_code:
            if request.htmx:
                return self._otp_section_response(
                    mobile=mobile,
                    message="Invalid or expired code. Please try again.",
                    status_code=HTTP_400_BAD_REQUEST,
                    variant="error",
                )
            return self._feedback_response(request, "Invalid or expired code. Please try again.", HTTP_400_BAD_REQUEST)

        # Store verified mobile in Redis keyed to a stable verification token.
        await delete_otp_code(redis, verification_key, mobile)
        await store_verified_mobile(redis, verification_key, mobile)

        if request.htmx:
            masked = mobile[:4] + "•" * max(0, len(mobile) - 8) + mobile[-4:] if len(mobile) > 8 else mobile
            response = HTMXTemplate(
                template_name="partials/otp_verified.jinja", context={"mobile": mobile, "masked_mobile": masked}
            )
            response.headers["HX-Trigger"] = json.dumps({"mobile-verified": {"seconds": _verified_mobile_ttl()}})
            return response
        return Response({"message": "Mobile verified"}, status_code=200)

    @post(operation_id="OTPReset", path=urls.ACCOUNT_VERIFY_RESET, exclude_from_auth=True)
    async def reset_otp_verification(
        self,
        request: HTMXRequest,
    ) -> HTMXTemplate | Response:
        """Clear pending verified-mobile state so user can re-verify."""
        verification_key = _get_verification_key(request)
        if not verification_key:
            return self._feedback_response(
                request, "Session expired. Refresh the page and try again.", HTTP_400_BAD_REQUEST
            )

        redis = settings.redis.client
        await delete_verified_mobile(redis, verification_key)

        if request.htmx:
            response = HTMXTemplate(
                template_name="partials/feedback.jinja",
                context={"message": "Verification cleared. Please verify your mobile number again."},
                status_code=200,
            )
            response.headers["HX-Trigger"] = "mobile-verification-reset"
            return response
        return Response({"message": "Verification cleared."}, status_code=200)

    # ── Registration ──────────────────────────────────────────────────

    @post(operation_id="AccountRegister", path=urls.ACCOUNT_REGISTER, exclude_from_auth=True)
    async def signup(  # noqa: PLR0912
        self,
        request: HTMXRequest,
        users_service: UserService,
        roles_service: RoleService,
        mobile_service: MobileNumberService,
        db_session: AsyncSession,
        data: Annotated[AccountRegister, Body(title="Account Register", media_type=RequestEncodingType.URL_ENCODED)],
    ) -> User | HTMXTemplate | Response:
        """User Signup — requires a verified mobile number in the session."""
        redis = settings.redis.client
        response: User | HTMXTemplate | Response

        # Gate: check server-side verified mobile
        verification_key = _get_verification_key(request)
        if not verification_key:
            return self._feedback_response(
                request, "Session expired. Refresh the page and try again.", HTTP_400_BAD_REQUEST
            )
        verified_mobile = await get_verified_mobile(redis, verification_key)
        if not verified_mobile:
            return self._feedback_response(
                request, "Mobile verification required. Please verify your number first.", HTTP_400_BAD_REQUEST
            )

        # Quick pre-check so we can return a friendly message without a DB constraint error.
        existing_user = await users_service.get_one_or_none(email=data.email)
        if existing_user is not None:
            message = "This user already exists."
            response = self._feedback_response(request, message, HTTP_409_CONFLICT)
        elif await mobile_service.get_one_or_none(number=verified_mobile) is not None:
            response = self._feedback_response(request, "This mobile number is already registered.", HTTP_409_CONFLICT)
        else:
            try:
                user_data = data.to_dict()

                # Default roles live in DB fixtures; run `app database upgrade` then `app users create-roles`.
                role_obj = await roles_service.get_one_or_none(slug=slugify(users_service.default_role))
                if role_obj is not None:
                    user_data.update({"role_id": role_obj.id})
                user_data.update({"is_verified": True, "verified_at": datetime.now(UTC).date()})

                tx_ctx = db_session.begin_nested() if db_session.in_transaction() else db_session.begin()
                async with tx_ctx:
                    user = await users_service.create(user_data)

                    # Create verified mobile record atomically with user creation.
                    await mobile_service.create(
                        {
                            "user_id": user.id,
                            "number": verified_mobile,
                            "country_code": get_region_code(verified_mobile),
                            "type": "PERSONAL",
                            "verified_via": settings.twilio.verified_via,
                            "is_verified": True,
                            "verified_at": datetime.now(UTC).date(),
                        }
                    )

            except DuplicateKeyError as exc:
                if _is_mobile_duplicate_error(exc):
                    message = "This mobile number is already registered."
                else:
                    message = getattr(exc, "detail", "This user already exists.")
                response = self._feedback_response(request, message, HTTP_409_CONFLICT)
            except Exception as exc:
                if request.htmx:
                    message = getattr(exc, "detail", "Unable to register with those details.")
                    response = HTMXTemplate(template_name="partials/feedback.jinja", context={"message": message})
                else:
                    raise
            else:
                # Clean up Redis verification state
                await delete_verified_mobile(redis, verification_key)
                request.app.emit(event_id="user_created", user_id=user.id)

                if request.htmx:
                    response = Response({"message": "OK"}, status_code=200)
                    response.headers["HX-Redirect"] = "/login"
                else:
                    response = users_service.to_schema(user, schema_type=User)
        return response

    @get(
        operation_id="AccountRegisterEmailCheck",
        path="/api/access/signup/email",
        exclude_from_auth=True,
        include_in_schema=False,
    )
    async def signup_email_check(
        self,
        request: HTMXRequest,
        users_service: UserService,
        email: str | None = None,
    ) -> HTMXTemplate | Response:
        """Check whether an email is already registered."""
        message = ""
        status_code = 200
        if email:
            trimmed_email = email.strip()
            if not EMAIL_BASIC_PATTERN.fullmatch(trimmed_email):
                message = "Invalid email format."
                status_code = HTTP_400_BAD_REQUEST
            else:
                existing_user = await users_service.get_one_or_none(email=trimmed_email)
                if existing_user is not None:
                    message = "This user already exists."
                    status_code = HTTP_409_CONFLICT
        return self._feedback_response(request, message, status_code)

    @get(
        operation_id="AccountRegisterMobileCheck",
        path=urls.ACCOUNT_REGISTER_MOBILE_CHECK,
        exclude_from_auth=True,
        include_in_schema=False,
    )
    async def signup_mobile_check(
        self,
        request: HTMXRequest,
        mobile_service: MobileNumberService,
        mobile: str | None = None,
    ) -> HTMXTemplate | Response:
        """Check whether a mobile number is already registered."""
        if not mobile:
            return self._mobile_availability_response(request, message="", exists=False, valid=False, status_code=200)

        trimmed_mobile = mobile.strip()
        if not validate_mobile(trimmed_mobile):
            return self._mobile_availability_response(
                request,
                message="Enter a valid mobile number in international format (e.g. +966512345678).",
                exists=False,
                valid=False,
                status_code=HTTP_400_BAD_REQUEST,
            )

        formatted_mobile = format_e164(trimmed_mobile)
        existing = await mobile_service.get_one_or_none(number=formatted_mobile)
        if existing is not None:
            return self._mobile_availability_response(
                request,
                message="This mobile number is already registered.",
                exists=True,
                valid=True,
                status_code=HTTP_409_CONFLICT,
            )
        return self._mobile_availability_response(request, message="", exists=False, valid=True, status_code=200)

    @post(operation_id="AccountProfileUpdate", path=urls.ACCOUNT_PROFILE, guards=[requires_active_user])
    async def update_profile(
        self,
        request: HTMXRequest,
        current_user: m.User,
        users_service: UserService,
        data: Annotated[UserProfileUpdate, Body(title="Update Profile", media_type=RequestEncodingType.URL_ENCODED)],
    ) -> User | HTMXTemplate:
        """Update the current user's profile."""

        updated = await users_service.update(item_id=current_user.id, data=data.to_dict())

        if request.htmx:
            return HTMXTemplate(template_name="partials/profile_card.jinja", context={"user": updated})
        return users_service.to_schema(updated, schema_type=User)
