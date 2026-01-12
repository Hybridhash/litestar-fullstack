"""User Account Controllers."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated

from advanced_alchemy.exceptions import DuplicateKeyError
from advanced_alchemy.utils.text import slugify
from litestar import Controller, Response, get, post
from litestar.di import Provide
from litestar.enums import MediaType, RequestEncodingType
from litestar.exceptions import PermissionDeniedException
from litestar.params import Body
from litestar.plugins.htmx import HTMXRequest, HTMXTemplate
from litestar.response import Template
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_409_CONFLICT

from app.domain.accounts import urls
from app.domain.accounts.deps import provide_users_service
from app.domain.accounts.guards import auth, requires_active_user
from app.domain.accounts.schemas import AccountLogin, AccountRegister, User, UserUpdate
from app.domain.accounts.services import RoleService
from app.lib.deps import create_service_provider

if TYPE_CHECKING:
    from litestar.security.jwt import OAuth2Login

    from app.db import models as m
    from app.domain.accounts.services import UserService

EMAIL_BASIC_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AccessController(Controller):
    """User login and registration."""

    tags = ["Access"]
    dependencies = {
        "users_service": Provide(provide_users_service),
        "roles_service": Provide(create_service_provider(RoleService)),
    }

    def _feedback_response(
        self,
        request: HTMXRequest,
        message: str,
        status_code: int = 200,
    ) -> HTMXTemplate | Response:
        if request.htmx:
            return HTMXTemplate(template_name="partials/feedback.jinja", context={"message": message})
        return Response({"message": message}, status_code=status_code)

    @get(operation_id="WebLoginPage", path="/login", exclude_from_auth=True, include_in_schema=False)
    async def login_page(self) -> Template:
        return Template(template_name="site/login.jinja", context={"error": ""}, media_type=MediaType.HTML)

    @get(operation_id="WebRegisterPage", path="/register", exclude_from_auth=True, include_in_schema=False)
    async def register_page(self) -> Template:
        return Template(template_name="site/register.jinja", context={"error": ""}, media_type=MediaType.HTML)

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

    @post(operation_id="AccountRegister", path=urls.ACCOUNT_REGISTER)
    async def signup(
        self,
        request: HTMXRequest,
        users_service: UserService,
        roles_service: RoleService,
        data: Annotated[AccountRegister, Body(title="Account Register", media_type=RequestEncodingType.URL_ENCODED)],
    ) -> User | HTMXTemplate | Response:
        """User Signup."""
        response: User | HTMXTemplate | Response
        # Quick pre-check so we can return a friendly message without a DB constraint error.
        existing_user = await users_service.get_one_or_none(email=data.email)
        if existing_user is not None:
            message = "This user already exists."
            response = self._feedback_response(request, message, HTTP_409_CONFLICT)
        else:
            try:
                user_data = data.to_dict()

                # Default roles live in DB fixtures; run `app database upgrade` then `app users create-roles`.
                role_obj = await roles_service.get_one_or_none(slug=slugify(users_service.default_role))
                if role_obj is not None:
                    user_data.update({"role_id": role_obj.id})

                user = await users_service.create(user_data)
            except DuplicateKeyError as exc:
                message = getattr(exc, "detail", "This user already exists.")
                response = self._feedback_response(request, message, HTTP_409_CONFLICT)
            except Exception as exc:
                if request.htmx:
                    message = getattr(exc, "detail", "Unable to register with those details.")
                    response = HTMXTemplate(template_name="partials/feedback.jinja", context={"message": message})
                else:
                    raise
            else:
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
            # Basic format check to provide quick feedback without adding extra dependencies.
            if not EMAIL_BASIC_PATTERN.fullmatch(trimmed_email):
                message = "Invalid email format."
                status_code = HTTP_400_BAD_REQUEST
            else:
                existing_user = await users_service.get_one_or_none(email=trimmed_email)
                if existing_user is not None:
                    message = "This user already exists."
                    status_code = HTTP_409_CONFLICT
        return self._feedback_response(request, message, status_code)

    @post(operation_id="AccountProfileUpdate", path=urls.ACCOUNT_PROFILE, guards=[requires_active_user])
    async def update_profile(
        self,
        request: HTMXRequest,
        current_user: m.User,
        users_service: UserService,
        data: Annotated[UserUpdate, Body(title="Update Profile", media_type=RequestEncodingType.URL_ENCODED)],
    ) -> User | HTMXTemplate:
        """Update the current user's profile."""

        updated = await users_service.update(item_id=current_user.id, data=data.to_dict())

        if request.htmx:
            return HTMXTemplate(template_name="partials/profile_card.jinja", context={"user": updated})
        return users_service.to_schema(updated, schema_type=User)

    # Json endpoint kept for future API references.
    # @get(operation_id="AccountProfile", path=urls.ACCOUNT_PROFILE, guards=[requires_active_user])
    # async def profile(self, current_user: m.User, users_service: UserService) -> User:
    #     """User Profile."""  # noqa: ERA001
    #     return users_service.to_schema(current_user, schema_type=User)  # noqa: ERA001
    #     return users_service.to_schema(current_user, schema_type=User)  # noqa: ERA001
