import logging
import sys
from functools import lru_cache
from pathlib import Path
from typing import cast

import jinjax
import structlog
from httpx_oauth.clients.github import GitHubOAuth2
from jinja2 import Environment, FileSystemLoader, pass_context
from litestar.config.compression import CompressionConfig
from litestar.config.cors import CORSConfig
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.logging.config import (
    LoggingConfig,
    StructLoggingConfig,
    default_logger_factory,
    default_structlog_processors,
    default_structlog_standard_lib_processors,
)
from litestar.middleware.logging import LoggingMiddlewareConfig
from litestar.middleware.rate_limit import RateLimitConfig, get_remote_address
from litestar.plugins.problem_details import ProblemDetailsConfig
from litestar.plugins.sqlalchemy import AlembicAsyncConfig, AsyncSessionConfig, SQLAlchemyAsyncConfig
from litestar.plugins.structlog import StructlogConfig
from litestar.template import TemplateConfig
from litestar_saq import CronJob, QueueConfig, SAQConfig
from litestar_vite import ViteConfig
from litestar_vite.config import PathConfig, RuntimeConfig
from litestar_vite.loader import render_asset_tag, render_hmr_client, render_routes, render_static_asset

from .base import get_settings
from .csrf import create_csrf_config, csrf_token

settings = get_settings()


compression = CompressionConfig(backend="gzip")
csrf = create_csrf_config(settings.app)
cors = CORSConfig(allow_origins=cast("list[str]", settings.app.ALLOWED_CORS_ORIGINS))
alchemy = SQLAlchemyAsyncConfig(
    engine_instance=settings.db.get_engine(),
    before_send_handler="autocommit",
    session_config=AsyncSessionConfig(expire_on_commit=False),
    alembic_config=AlembicAsyncConfig(
        version_table_name=settings.db.MIGRATION_DDL_VERSION_TABLE,
        script_config=settings.db.MIGRATION_CONFIG,
        script_location=settings.db.MIGRATION_PATH,
    ),
)
_template_loader = FileSystemLoader([str(settings.vite.TEMPLATE_DIR)])
_jinja_env = Environment(loader=_template_loader, autoescape=True, auto_reload=settings.vite.DEV_MODE, cache_size=0)

_jinja_env.globals["vite_hmr"] = pass_context(render_hmr_client)
_jinja_env.globals["vite"] = pass_context(render_asset_tag)
_jinja_env.globals["vite_static"] = pass_context(render_static_asset)
_jinja_env.globals["vite_routes"] = pass_context(render_routes)


_jinja_env.globals.setdefault("csrf_token", csrf_token)
_jinja_env.add_extension(jinjax.JinjaX)
_jinjax_catalog = jinjax.Catalog(jinja_env=_jinja_env)
_components_dir = Path(settings.vite.TEMPLATE_DIR).parent / "components"
_jinjax_catalog.add_folder(str(_components_dir))
_jinjax_catalog.add_folder(str(settings.vite.TEMPLATE_DIR))
_jinja_env.globals["catalog"] = _jinjax_catalog
templates: TemplateConfig = TemplateConfig(instance=JinjaTemplateEngine.from_environment(_jinja_env))
problem_details = ProblemDetailsConfig(enable_for_all_http_exceptions=True)
rate_limit = RateLimitConfig(
    rate_limit=settings.rate_limit.rate_limit,
    exclude=cast("list[str]", settings.rate_limit.EXCLUDE),
    exclude_opt_key=settings.rate_limit.EXCLUDE_OPT_KEY,
    identifier_for_request=get_remote_address,
)


vite = ViteConfig(
    mode="htmx",
    paths=PathConfig(
        bundle_dir=settings.vite.BUNDLE_DIR,
        resource_dir=settings.vite.RESOURCE_DIR,
        asset_url=settings.vite.ASSET_URL,
    ),
    runtime=RuntimeConfig(
        dev_mode=settings.vite.DEV_MODE,
        start_dev_server=settings.vite.USE_SERVER_LIFESPAN,
        host=settings.vite.HOST,
        port=settings.vite.PORT,
        # is_react=settings.vite.ENABLE_REACT_HELPERS, Excluded for HTMX mode
        # If hot_reload is disabled, set proxy_mode=None to disable HMR
        proxy_mode=None if not settings.vite.HOT_RELOAD else "vite",
    ),
    dev_mode=settings.vite.DEV_MODE,
)
github_oauth = GitHubOAuth2(
    client_id=settings.app.GITHUB_OAUTH2_CLIENT_ID,
    client_secret=settings.app.GITHUB_OAUTH2_CLIENT_SECRET,
)

saq = SAQConfig(
    web_enabled=settings.saq.WEB_ENABLED,
    worker_processes=settings.saq.PROCESSES,
    use_server_lifespan=settings.saq.USE_SERVER_LIFESPAN,
    queue_configs=[
        QueueConfig(
            dsn=settings.redis.URL,
            name="system-tasks",
            tasks=["app.domain.system.tasks.system_task", "app.domain.system.tasks.system_upkeep"],
            scheduled_tasks=[
                CronJob(
                    function="app.domain.system.tasks.system_upkeep",
                    unique=True,
                    cron="0 * * * *",
                    timeout=500,
                ),
            ],
        ),
        QueueConfig(
            dsn=settings.redis.URL,
            name="background-tasks",
            tasks=["app.domain.system.tasks.background_worker_task"],
            scheduled_tasks=[
                CronJob(
                    function="app.domain.system.tasks.background_worker_task",
                    unique=True,
                    cron="* * * * *",
                    timeout=300,
                ),
            ],
        ),
    ],
)


@lru_cache
def _is_tty() -> bool:
    return bool(sys.stderr.isatty() or sys.stdout.isatty())


_render_as_json = not _is_tty()
_structlog_default_processors = default_structlog_processors(as_json=_render_as_json)
_structlog_default_processors.insert(1, structlog.processors.EventRenamer("message"))
_structlog_standard_lib_processors = default_structlog_standard_lib_processors(as_json=_render_as_json)
_structlog_standard_lib_processors.insert(1, structlog.processors.EventRenamer("message"))

log = StructlogConfig(
    structlog_logging_config=StructLoggingConfig(
        log_exceptions="always",
        processors=_structlog_default_processors,
        logger_factory=default_logger_factory(as_json=_render_as_json),
        standard_lib_logging_config=LoggingConfig(
            root={"level": logging.getLevelName(settings.log.LEVEL), "handlers": ["queue_listener"]},
            formatters={
                "standard": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processors": _structlog_standard_lib_processors,
                },
            },
            loggers={
                "_granian": {
                    "propagate": False,
                    "level": settings.log.ASGI_ERROR_LEVEL,
                    "handlers": ["queue_listener"],
                },
                "granian.server": {
                    "propagate": False,
                    "level": settings.log.ASGI_ERROR_LEVEL,
                    "handlers": ["queue_listener"],
                },
                "granian.access": {
                    "propagate": False,
                    "level": settings.log.ASGI_ACCESS_LEVEL,
                    "handlers": ["queue_listener"],
                },
                "saq": {
                    "propagate": False,
                    "level": settings.log.SAQ_LEVEL,
                    "handlers": ["queue_listener"],
                },
                "sqlalchemy.engine": {
                    "propagate": False,
                    "level": settings.log.SQLALCHEMY_LEVEL,
                    "handlers": ["queue_listener"],
                },
                "sqlalchemy.pool": {
                    "propagate": False,
                    "level": settings.log.SQLALCHEMY_LEVEL,
                    "handlers": ["queue_listener"],
                },
            },
        ),
    ),
    middleware_logging_config=LoggingMiddlewareConfig(
        request_log_fields=settings.log.REQUEST_FIELDS,
        response_log_fields=settings.log.RESPONSE_FIELDS,
    ),
)
