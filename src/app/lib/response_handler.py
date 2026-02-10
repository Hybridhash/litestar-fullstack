"""Unified response handling for HTMX/HTML/JSON request patterns.

This module provides a single ResponseHandler class to consolidate the common
three-way response logic (HTMX fragments, HTML templates/redirects, JSON schema
responses) across controllers and exception handlers.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast
from urllib.parse import urlparse

from litestar.enums import MediaType
from litestar.plugins.htmx import HTMXTemplate
from litestar.response import Redirect, Response, Template
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_302_FOUND,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from structlog import get_logger

if TYPE_CHECKING:
    from litestar.connection import Request

ResponseFormatter = Callable[[Any, int, Mapping[str, str] | None], Response]
RedirectStatusCode = Literal[301, 302, 303, 307, 308]

_REDIRECT_STATUS_CODES: set[int] = {301, 302, 303, 307, 308}


@dataclass(frozen=True)
class ErrorTemplates:
    """Mapping of default error templates by response type."""

    htmx: str | None = None
    html: str | None = "site/error.jinja"


DEFAULT_STATUS_ERROR_TEMPLATES: dict[int, ErrorTemplates] = {
    HTTP_403_FORBIDDEN: ErrorTemplates(htmx=None, html="site/forbidden.jinja"),
    HTTP_404_NOT_FOUND: ErrorTemplates(htmx=None, html="site/not_found.jinja"),
    HTTP_500_INTERNAL_SERVER_ERROR: ErrorTemplates(
        htmx=None,
        html="site/server_error.jinja",
    ),
}


class ResponseHandler:
    """Unified response handler for HTMX/HTML/JSON request patterns.

    Usage example:
        handler = ResponseHandler(request)
        return handler.respond(
            data=team,
            htmx_template="partials/team_card.jinja",
            html_template="site/team_detail.jinja",
            html_context={"team": team},
            json_schema_type=Team,
            service=teams_service,
        )

    Migration example:
        # Before: scattered per-request checks in controllers.
        # After: single handler call per route or exception handler.
    """

    def __init__(
        self,
        request: Request[Any, Any, Any],
        *,
        error_templates: Mapping[int, ErrorTemplates] | None = None,
        default_error_templates: ErrorTemplates | None = None,
        default_htmx_template: str | None = None,
        default_html_template: str | None = None,
        allowed_template_prefixes: tuple[str, ...] | None = None,
        allowed_template_names: set[str] | None = None,
        allowed_redirect_hosts: set[str] | None = None,
        response_formatters: Mapping[str, ResponseFormatter] | None = None,
        htmx_detector: Callable[[Request[Any, Any, Any]], bool] | None = None,
        html_detector: Callable[[Request[Any, Any, Any]], bool] | None = None,
        json_detector: Callable[[Request[Any, Any, Any]], bool] | None = None,
    ) -> None:
        """Initialize ResponseHandler.

        Args:
            request: Current request instance.
            error_templates: Optional mapping for status-code-specific templates.
            default_error_templates: Fallback templates when status code mapping is missing.
            default_htmx_template: Default HTMX success template when none is provided.
            default_html_template: Default HTML success template when none is provided.
            allowed_template_prefixes: Allowed template path prefixes.
            allowed_template_names: Additional explicit template names to allow.
            allowed_redirect_hosts: Additional redirect hosts to allow.
            response_formatters: Custom response formatters keyed by media type string.
            htmx_detector: Optional override for HTMX detection.
            html_detector: Optional override for HTML detection.
            json_detector: Optional override for JSON detection.
        """

        self.request = request
        self.error_templates = dict(error_templates or DEFAULT_STATUS_ERROR_TEMPLATES)
        self.default_error_templates = default_error_templates or ErrorTemplates()
        self.default_htmx_template = default_htmx_template
        self.default_html_template = default_html_template
        self.allowed_template_prefixes = allowed_template_prefixes or ("site/", "partials/")
        self.allowed_template_names = allowed_template_names or set()
        self.allowed_redirect_hosts = allowed_redirect_hosts or set()
        self.response_formatters = dict(response_formatters or {})
        self._htmx_detector = htmx_detector
        self._html_detector = html_detector
        self._json_detector = json_detector

    def is_htmx(self) -> bool:
        """Return True when the request is an HTMX request.

        Example:
            if response_handler.is_htmx():
                return HTMXTemplate(template_name="partials/item.jinja", context={"item": item})
        """

        if self._htmx_detector is not None:
            return self._htmx_detector(self.request)
        if getattr(self.request, "htmx", False):
            return True
        return self.request.headers.get("HX-Request", "").lower() == "true"

    def is_html(self) -> bool:
        """Return True when the request expects HTML via Accept header."""

        if self._html_detector is not None:
            return self._html_detector(self.request)
        accept = self.request.headers.get("accept", "")
        return "text/html" in accept.lower()

    def is_json(self) -> bool:
        """Return True when the request expects JSON or no type is detected.

        JSON is the fallback when the request is not HTMX or HTML.
        """

        if self._json_detector is not None:
            return self._json_detector(self.request)
        if self.is_htmx() or self.is_html():
            return False
        accept = self.request.headers.get("accept", "")
        accept_lower = accept.lower()
        return "application/json" in accept_lower or "text/html" not in accept_lower

    def respond(  # noqa: PLR0911
        self,
        data: Any = None,
        *,
        htmx_template: str | None = None,
        htmx_context: dict[str, Any] | None = None,
        htmx_status_code: int | None = None,
        html_redirect: str | None = None,
        html_template: str | None = None,
        html_context: dict[str, Any] | None = None,
        html_status_code: int | None = None,
        json_schema_type: type | None = None,
        service: Any | None = None,
        status_code: int = HTTP_200_OK,
        json_status_code: int | None = None,
        headers: Mapping[str, str] | None = None,
        schema_kwargs: Mapping[str, Any] | None = None,
        **template_kwargs: Any,
    ) -> HTMXTemplate | Template | Redirect | Response | Any:
        """Return HTMX, HTML, or JSON responses based on request type.

        Examples:
            return handler.respond(
                data=user,
                htmx_template="partials/profile_card.jinja",
                html_template="site/profile.jinja",
                html_context={"user": user},
                json_schema_type=UserSchema,
                service=user_service,
            )
        """

        htmx_status = htmx_status_code or status_code
        html_status = html_status_code or status_code
        json_status = json_status_code or status_code

        if self.is_htmx():
            template_name = htmx_template or self.default_htmx_template
            if template_name:
                if not self._is_template_name_allowed(template_name):
                    return self._invalid_template_response(headers)
                htmx_response = HTMXTemplate(
                    template_name=template_name,
                    context=htmx_context or {},
                    status_code=htmx_status,
                    **template_kwargs,
                )
                return self._apply_headers(htmx_response, headers)
            return self._json_response(data or {}, status_code=htmx_status, headers=headers)

        if self.is_html():
            if html_redirect:
                return self._redirect_response(html_redirect, html_status, headers)
            template_name = html_template or self.default_html_template
            if template_name:
                if not self._is_template_name_allowed(template_name):
                    return self._invalid_template_response(headers)
                html_response = Template(
                    template_name=template_name,
                    context=html_context or {},
                    status_code=html_status,
                    media_type=MediaType.HTML,
                    **template_kwargs,
                )
                return self._apply_headers(html_response, headers)
            return self._json_response(data or {}, status_code=html_status, headers=headers)

        return self._schema_or_json_response(
            data=data,
            json_schema_type=json_schema_type,
            service=service,
            status_code=json_status,
            headers=headers,
            schema_kwargs=schema_kwargs,
        )

    def error(  # noqa: PLR0911
        self,
        message: str,
        *,
        status_code: int,
        htmx_template: str | None = None,
        html_template: str | None = None,
        context: dict[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        **template_kwargs: Any,
    ) -> HTMXTemplate | Template | Response:
        """Return a unified error response for HTMX/HTML/JSON.

        Example:
            return handler.error("Not found", status_code=404)
        """

        if self.is_htmx():
            if htmx_template:
                if not self._is_template_name_allowed(htmx_template):
                    return self._invalid_template_response(headers)
                htmx_response = HTMXTemplate(
                    template_name=htmx_template,
                    context={"message": message, **(context or {})},
                    status_code=status_code,
                    **template_kwargs,
                )
                return self._apply_headers(htmx_response, headers)
            return self._json_response({"detail": message}, status_code=status_code, headers=headers)

        if self.is_html():
            template_name = html_template or self._error_template(status_code, "html")
            if template_name:
                if not self._is_template_name_allowed(template_name):
                    return self._invalid_template_response(headers)
                html_response = Template(
                    template_name=template_name,
                    context={"message": message, **(context or {})},
                    status_code=status_code,
                    media_type=MediaType.HTML,
                )
                return self._apply_headers(html_response, headers)
            return self._json_response({"detail": message}, status_code=status_code, headers=headers)

        return self._json_response({"detail": message}, status_code=status_code, headers=headers)

    def redirect(
        self,
        url: str,
        *,
        status_code: int = HTTP_302_FOUND,
        detail: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response | Redirect:
        """Return an HTMX redirect (HX-Redirect) or HTML redirect."""

        if not self._is_redirect_url_allowed(url):
            return self._invalid_redirect_response(headers)

        if self.is_htmx():
            htmx_payload = {"detail": detail} if detail else {}
            htmx_response = self._json_response(htmx_payload, status_code=status_code, headers=headers)
            htmx_response.headers["HX-Redirect"] = url
            return htmx_response

        if self.is_html():
            return self._redirect_response(url, status_code, headers)

        json_payload: MutableMapping[str, Any] = {"redirect": url}
        if detail:
            json_payload["detail"] = detail
        return self._json_response(json_payload, status_code=status_code, headers=headers)

    def feedback(
        self,
        message: str,
        *,
        status_code: int = HTTP_200_OK,
        htmx_template: str = "partials/feedback.jinja",
        headers: Mapping[str, str] | None = None,
        **template_kwargs: Any,
    ) -> HTMXTemplate | Response:
        """Return a feedback response for HTMX or JSON requests.

        Example:
            return handler.feedback("Saved!", status_code=200)
        """

        if self.is_htmx():
            if not self._is_template_name_allowed(htmx_template):
                return self._invalid_template_response(headers)
            htmx_response = HTMXTemplate(
                template_name=htmx_template,
                context={"message": message},
                status_code=status_code,
                **template_kwargs,
            )
            return self._apply_headers(htmx_response, headers)
        return self._json_response({"message": message}, status_code=status_code, headers=headers)

    def apply_htmx_redirect(self, response: Response, url: str) -> Response:
        """Attach an HTMX redirect header to an existing response."""

        if not self._is_redirect_url_allowed(url):
            msg = "Invalid redirect URL"
            raise ValueError(msg)
        response.headers["HX-Redirect"] = url
        return response

    def _schema_or_json_response(
        self,
        *,
        data: Any,
        json_schema_type: type | None,
        service: Any | None,
        status_code: int,
        headers: Mapping[str, str] | None,
        schema_kwargs: Mapping[str, Any] | None,
    ) -> Response | Any:
        if service and json_schema_type and data is not None:
            kwargs = dict(schema_kwargs or {})
            try:
                schema_result = service.to_schema(schema_type=json_schema_type, data=data, **kwargs)
            except Exception as exc:  # noqa: BLE001
                logger = get_logger()
                logger.warning(
                    "response_handler.to_schema_failed",
                    exc_type=type(exc).__name__,
                    path=self.request.url.path,
                    method=self.request.method,
                )
                error_status = getattr(exc, "status_code", None)
                if not isinstance(error_status, int):
                    error_status = HTTP_500_INTERNAL_SERVER_ERROR
                return self._json_response(
                    {"detail": "Response serialization failed."},
                    status_code=error_status,
                    headers=headers,
                )
            if isinstance(schema_result, Response):
                if status_code != HTTP_200_OK:
                    schema_result.status_code = status_code
                if headers:
                    schema_result.headers.update(self._sanitize_headers(headers))
                return schema_result
            if status_code != HTTP_200_OK or headers:
                return self._json_response(schema_result, status_code=status_code, headers=headers)
            return schema_result
        return self._json_response(data or {}, status_code=status_code, headers=headers)

    def _json_response(
        self,
        content: Any,
        *,
        status_code: int,
        headers: Mapping[str, str] | None,
        media_type: MediaType = MediaType.JSON,
    ) -> Response:
        media_key = getattr(media_type, "value", str(media_type))
        formatter = self.response_formatters.get(media_key)
        if formatter:
            return formatter(content, status_code, self._sanitize_headers(headers))
        return Response(
            content=content,
            status_code=status_code,
            media_type=media_type,
            headers=self._sanitize_headers(headers),
        )

    def _apply_headers(
        self,
        response: Response | Template | Redirect | HTMXTemplate,
        headers: Mapping[str, str] | None,
    ) -> Response | Template | Redirect | HTMXTemplate:
        if headers:
            response.headers.update(self._sanitize_headers(headers))
        return response

    def _redirect_response(
        self,
        url: str,
        status_code: int,
        headers: Mapping[str, str] | None,
    ) -> Response | Redirect:
        if not self._is_redirect_url_allowed(url):
            return self._invalid_redirect_response(headers)
        redirect_response = Redirect(
            path=url,
            status_code=cast("RedirectStatusCode", status_code),
        )
        return self._apply_headers(redirect_response, headers)

    def _sanitize_headers(self, headers: Mapping[str, str] | None) -> dict[str, str]:
        if not headers:
            return {}
        sanitized: dict[str, str] = {}
        for key, value in headers.items():
            if any(token in key for token in ("\r", "\n")):
                continue
            if any(token in value for token in ("\r", "\n")):
                continue
            sanitized[key] = value
        return sanitized

    def _is_template_name_allowed(self, template_name: str) -> bool:
        if template_name in self.allowed_template_names:
            return True
        if not template_name:
            return False
        if ".." in template_name:
            return False
        if template_name.startswith(("/", "\\")):
            return False
        if ":" in template_name:
            return False
        return any(template_name.startswith(prefix) for prefix in self.allowed_template_prefixes)

    def _invalid_template_response(self, headers: Mapping[str, str] | None) -> Response:
        return self._json_response(
            {"detail": "Invalid template name."},
            status_code=400,
            headers=headers,
        )

    def _invalid_redirect_response(self, headers: Mapping[str, str] | None) -> Response:
        return self._json_response(
            {"detail": "Invalid redirect URL."},
            status_code=400,
            headers=headers,
        )

    def _is_redirect_url_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.scheme and not parsed.netloc:
            if not url.startswith("/"):
                return False
            return not url.startswith("//")
        if parsed.scheme not in {"http", "https"}:
            return False
        host = parsed.hostname
        if not host:
            return False
        if host == self.request.url.hostname:
            return True
        return host in self.allowed_redirect_hosts

    def _error_template(self, status_code: int, kind: str) -> str | None:
        template_pair = self.error_templates.get(status_code)
        if template_pair is None:
            template_pair = self.default_error_templates
        return getattr(template_pair, kind, None)


def provide_response_handler(request: Request[Any, Any, Any]) -> ResponseHandler:
    """Dependency provider for ResponseHandler."""

    return ResponseHandler(request)
