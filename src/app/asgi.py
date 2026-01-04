from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from litestar import Litestar


def create_app() -> Litestar:
    """Create ASGI application."""

    from litestar import Litestar  # noqa: PLC0415

    from app.server.core import ApplicationCore  # noqa: PLC0415

    return Litestar(plugins=[ApplicationCore()])
