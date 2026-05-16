from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from litestar.enums import ScopeType

if TYPE_CHECKING:
    from litestar.types import BeforeMessageSendHookHandler
    from litestar.types.asgi_types import Message, Scope

    from app.config.base import ViteSettings


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _join_directive(name: str, values: list[str]) -> str:
    return f"{name} {' '.join(values)}"


def _vite_dev_sources(vite_settings: ViteSettings) -> list[str]:
    if not vite_settings.DEV_MODE:
        return []

    host_candidates = ["localhost", "127.0.0.1"]
    if vite_settings.HOST and vite_settings.HOST != "0.0.0.0" and vite_settings.HOST not in host_candidates:  # noqa: S104
        host_candidates.insert(0, vite_settings.HOST)

    script_sources = [f"http://{host}:{vite_settings.PORT}" for host in host_candidates]
    connect_sources = [f"ws://{host}:{vite_settings.PORT}" for host in host_candidates]
    return _dedupe(script_sources + connect_sources)


def build_content_security_policy(vite_settings: ViteSettings) -> str:
    """Build the CSP header value used by the application."""

    dev_sources = _vite_dev_sources(vite_settings)
    http_dev_sources = [source for source in dev_sources if source.startswith("http://")]
    script_sources = ["'self'", *http_dev_sources]
    connect_sources = ["'self'", *[source for source in dev_sources if source.startswith("ws://")]]
    style_sources = ["'self'", "https://fonts.googleapis.com", *http_dev_sources]

    directives = [
        _join_directive("default-src", ["'self'"]),
        _join_directive("base-uri", ["'self'"]),
        _join_directive("object-src", ["'none'"]),
        _join_directive("frame-ancestors", ["'self'"]),
        _join_directive("form-action", ["'self'"]),
        _join_directive("script-src", script_sources),
        _join_directive("script-src-attr", ["'none'"]),
        _join_directive("style-src-elem", _dedupe(style_sources)),
        _join_directive("style-src-attr", ["'unsafe-inline'"]),
        _join_directive("font-src", ["'self'", "https://fonts.gstatic.com", "data:"]),
        _join_directive("img-src", ["'self'", "data:"]),
        _join_directive("connect-src", connect_sources),
    ]
    return "; ".join(directives)


def create_csp_before_send_hook(policy: str, *, report_only: bool = False) -> BeforeMessageSendHookHandler:
    """Build a duplicate-safe before_send hook that attaches the CSP header."""
    header_name = ("content-security-policy-report-only" if report_only else "content-security-policy").encode("ascii")
    header_value = policy.encode("utf-8")

    def _apply_header(message: Message) -> None:
        if message["type"] != "http.response.start":
            return
        headers = list(message.get("headers", []))
        if not any(existing_name.lower() == header_name for existing_name, _ in headers):
            headers.append((header_name, header_value))
        message["headers"] = headers

    async def _before_send(message: Message, scope: Scope) -> None:
        if scope.get("type") == ScopeType.HTTP:
            _apply_header(message)

    return _before_send


@dataclass(frozen=True)
class CSPConfig:
    policy: str
    before_send: BeforeMessageSendHookHandler


def create_csp_config(vite_settings: ViteSettings) -> CSPConfig:
    policy = build_content_security_policy(vite_settings)
    return CSPConfig(policy=policy, before_send=create_csp_before_send_hook(policy))
