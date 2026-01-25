"""Litestar-saqlalchemy exception types.

Also, defines functions that translate service and repository exceptions
into HTTP exceptions.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from advanced_alchemy.exceptions import IntegrityError
from litestar.enums import MediaType
from litestar.exceptions import (
    HTTPException,
    InternalServerException,
    NotAuthorizedException,
    NotFoundException,
    PermissionDeniedException,
)
from litestar.exceptions.responses import create_debug_response, create_exception_response
from litestar.repository.exceptions import ConflictError, NotFoundError, RepositoryError
from litestar.response import Redirect, Response, Template
from litestar.status_codes import HTTP_409_CONFLICT, HTTP_500_INTERNAL_SERVER_ERROR
from structlog import get_logger
from structlog.contextvars import bind_contextvars

if TYPE_CHECKING:
    from typing import Any

    from litestar.connection import Request
    from litestar.middleware.exceptions.middleware import ExceptionResponseContent
    from litestar.types import Scope

__all__ = (
    "ApplicationError",
    "AuthorizationError",
    "HealthCheckConfigurationError",
    "after_exception_hook_handler",
    "not_authorized_exception_handler",
    "permission_denied_exception_handler",
)


class ApplicationError(Exception):
    """Base exception type for the lib's custom exception types."""

    detail: str

    def __init__(self, *args: Any, detail: str = "") -> None:
        """Initialize ``AdvancedAlchemyException``.

        Args:
            *args: args are converted to :class:`str` before passing to :class:`Exception`
            detail: detail of the exception.
        """
        str_args = [str(arg) for arg in args if arg]
        if not detail:
            if str_args:
                detail, *str_args = str_args
            elif hasattr(self, "detail"):
                detail = self.detail
        self.detail = detail
        super().__init__(*str_args)

    def __repr__(self) -> str:
        if self.detail:
            return f"{self.__class__.__name__} - {self.detail}"
        return self.__class__.__name__

    def __str__(self) -> str:
        return " ".join((*self.args, self.detail)).strip()


class MissingDependencyError(ApplicationError, ImportError):
    """Missing optional dependency.

    This exception is raised only when a module depends on a dependency that has not been installed.
    """


class ApplicationClientError(ApplicationError):
    """Base exception type for client errors."""


class AuthorizationError(ApplicationClientError):
    """A user tried to do something they shouldn't have."""


class HealthCheckConfigurationError(ApplicationError):
    """An error occurred while registering an health check."""


class _HTTPConflictException(HTTPException):
    """Request conflict with the current state of the target resource."""

    status_code = HTTP_409_CONFLICT


async def after_exception_hook_handler(exc: Exception, _scope: Scope) -> None:
    """Binds `exc_info` key with exception instance as value to structlog
    context vars.

    This must be a coroutine so that it is not wrapped in a thread where we'll lose context.

    Args:
        exc: the exception that was raised.
        _scope: scope of the request
    """
    if isinstance(exc, ApplicationError):
        return
    if isinstance(exc, HTTPException) and exc.status_code < HTTP_500_INTERNAL_SERVER_ERROR:
        return
    bind_contextvars(exc_info=sys.exc_info())


def exception_to_http_response(
    request: Request[Any, Any, Any],
    exc: ApplicationError | RepositoryError,
) -> Response[ExceptionResponseContent]:
    """Transform repository exceptions to HTTP exceptions.

    Args:
        request: The request that experienced the exception.
        exc: Exception raised during handling of the request.

    Returns:
        Exception response appropriate to the type of original exception.
    """
    http_exc: type[HTTPException]
    if isinstance(exc, NotFoundError):
        http_exc = NotFoundException
    elif isinstance(exc, ConflictError | RepositoryError | IntegrityError):
        http_exc = _HTTPConflictException
    elif isinstance(exc, AuthorizationError):
        http_exc = PermissionDeniedException
    else:
        http_exc = InternalServerException
    if request.app.debug and http_exc not in (PermissionDeniedException, NotFoundError, AuthorizationError):
        return create_debug_response(request, exc)
    return create_exception_response(request, http_exc(detail=str(exc.__cause__)))


def permission_denied_exception_handler(
    request: Request[Any, Any, Any],
    exc: PermissionDeniedException,
) -> Response[ExceptionResponseContent]:
    detail = str(exc.detail or exc)
    if "csrf" not in detail.lower():
        message = detail or "You do not have permission to access this resource."
        if _is_htmx(request):
            return Response(
                content={"detail": message},
                status_code=exc.status_code,
                media_type=MediaType.JSON,
            )
        if _wants_html(request):
            return Template(
                template_name="site/forbidden.jinja",
                context={"message": message},
                status_code=exc.status_code,
                media_type=MediaType.HTML,
            )
        return create_exception_response(request, exc)

    csrf_config = request.app.csrf_config
    header_name = csrf_config.header_name if csrf_config else "X-XSRF-TOKEN"
    cookie_name = csrf_config.cookie_name if csrf_config else "XSRF-TOKEN"
    logger = get_logger()
    logger.warning(
        "CSRF validation failed",
        path=request.url.path,
        method=request.method,
        csrf_header=_obfuscate_value(request.headers.get(header_name)),
        csrf_cookie=_obfuscate_value(request.cookies.get(cookie_name)),
        htmx=bool(request.headers.get("HX-Request")),
    )
    message = "CSRF validation failed. Please refresh the page and try again."
    return Response(
        content=message,
        media_type=MediaType.TEXT,
        status_code=exc.status_code,
    )


def not_authorized_exception_handler(
    request: Request[Any, Any, Any],
    exc: NotAuthorizedException,
) -> Response[ExceptionResponseContent] | Redirect:
    """Handle NotAuthorizedException (401) by redirecting to login for web requests.

    This handler catches authentication failures (expired/missing JWT tokens)
    and redirects users to the login page for HTML/HTMX requests, providing
    a better user experience when sessions expire.

    Args:
        request: The request that experienced the exception.
        exc: The NotAuthorizedException that was raised.

    Returns:
        A redirect to login for web requests, or a JSON response for API requests.
    """
    detail = str(exc.detail or "Authentication required")

    # For HTMX requests, return a redirect header
    if _is_htmx(request):
        response = Response(
            content={"detail": detail},
            status_code=exc.status_code,
            media_type=MediaType.JSON,
        )
        response.headers["HX-Redirect"] = "/login"
        return response

    # For HTML requests, redirect to login page
    if _wants_html(request):
        return Redirect(path="/login")

    # For API requests, return standard exception response
    return create_exception_response(request, exc)


def _wants_html(request: Request[Any, Any, Any]) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept.lower()


def _is_htmx(request: Request[Any, Any, Any]) -> bool:
    if getattr(request, "htmx", False):
        return True
    return request.headers.get("HX-Request", "").lower() == "true"


def _obfuscate_value(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) < 6:
        return "***"
    return f"{value[:2]}***{value[-2:]}"
