from __future__ import annotations

import asyncio
import binascii
import json
import os
from contextlib import suppress
from dataclasses import dataclass, field
from functools import lru_cache
from ipaddress import ip_network
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

from advanced_alchemy.utils.text import slugify
from litestar.data_extractors import RequestExtractorField
from litestar.serialization import decode_json, encode_json
from litestar.utils.module_loader import module_to_os_path
from redis.asyncio import Redis
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from ._utils import get_env

if TYPE_CHECKING:
    from collections.abc import Callable
    from ipaddress import IPv4Network, IPv6Network

    from litestar.data_extractors import ResponseExtractorField
    from litestar.middleware.rate_limit import DurationUnit

DEFAULT_MODULE_NAME = "app"
BASE_DIR: Final[Path] = module_to_os_path(DEFAULT_MODULE_NAME)


@dataclass
class DatabaseSettings:
    ECHO: bool = field(default_factory=get_env("DATABASE_ECHO", False))
    """Enable SQLAlchemy engine logs."""
    ECHO_POOL: bool = field(default_factory=get_env("DATABASE_ECHO_POOL", False))
    """Enable SQLAlchemy connection pool logs."""
    POOL_DISABLED: bool = field(default_factory=get_env("DATABASE_POOL_DISABLED", False))
    """Disable SQLAlchemy pool configuration."""
    POOL_MAX_OVERFLOW: int = field(default_factory=get_env("DATABASE_MAX_POOL_OVERFLOW", 10))
    """Max overflow for SQLAlchemy connection pool"""
    POOL_SIZE: int = field(default_factory=get_env("DATABASE_POOL_SIZE", 5))
    """Pool size for SQLAlchemy connection pool"""
    POOL_TIMEOUT: int = field(default_factory=get_env("DATABASE_POOL_TIMEOUT", 30))
    """Time in seconds for timing connections out of the connection pool."""
    POOL_RECYCLE: int = field(default_factory=get_env("DATABASE_POOL_RECYCLE", 300))
    """Amount of time to wait before recycling connections."""
    POOL_PRE_PING: bool = field(default_factory=get_env("DATABASE_PRE_POOL_PING", False))
    """Optionally ping database before fetching a session from the connection pool."""
    URL: str = field(default_factory=get_env("DATABASE_URL", "sqlite+aiosqlite:///db.sqlite3"))
    """SQLAlchemy Database URL."""
    MIGRATION_CONFIG: str = field(
        default_factory=get_env("DATABASE_MIGRATION_CONFIG", f"{BASE_DIR}/db/migrations/alembic.ini")
    )
    """The path to the `alembic.ini` configuration file."""
    MIGRATION_PATH: str = field(default_factory=get_env("DATABASE_MIGRATION_PATH", f"{BASE_DIR}/db/migrations"))
    """The path to the `alembic` database migrations."""
    MIGRATION_DDL_VERSION_TABLE: str = field(
        default_factory=get_env("DATABASE_MIGRATION_DDL_VERSION_TABLE", "ddl_version")
    )
    """The name to use for the `alembic` versions table name."""
    FIXTURE_PATH: str = field(default_factory=get_env("DATABASE_FIXTURE_PATH", f"{BASE_DIR}/db/fixtures"))
    """The path to JSON fixture files to load into tables."""
    _engine_instance: AsyncEngine | None = None
    """SQLAlchemy engine instance generated from settings."""

    @property
    def engine(self) -> AsyncEngine:
        return self.get_engine()

    @staticmethod
    def _normalize_url_for_async_engine(url: str) -> str:
        """Normalize postgres DSNs to asyncpg for create_async_engine()."""
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    def get_engine(self) -> AsyncEngine:
        if self._engine_instance is not None:
            return self._engine_instance
        url = self._normalize_url_for_async_engine(self.URL)
        if url.startswith("postgresql+asyncpg"):
            engine = create_async_engine(
                url=url,
                future=True,
                json_serializer=encode_json,
                json_deserializer=decode_json,
                echo=self.ECHO,
                echo_pool=self.ECHO_POOL,
                max_overflow=self.POOL_MAX_OVERFLOW,
                pool_size=self.POOL_SIZE,
                pool_timeout=self.POOL_TIMEOUT,
                pool_recycle=self.POOL_RECYCLE,
                pool_pre_ping=self.POOL_PRE_PING,
                pool_use_lifo=True,  # use lifo to reduce the number of idle connections
                poolclass=NullPool if self.POOL_DISABLED else None,
            )
            """Database session factory.

            See [`async_sessionmaker()`][sqlalchemy.ext.asyncio.async_sessionmaker].
            """

            @event.listens_for(engine.sync_engine, "connect")
            def _sqla_on_connect(dbapi_connection: Any, _: Any) -> Any:  # pragma: no cover
                """Using msgspec for serialization of the json column values means that the
                output is binary, not `str` like `json.dumps` would output.
                SQLAlchemy expects that the json serializer returns `str` and calls `.encode()` on the value to
                turn it to bytes before writing to the JSONB column. I'd need to either wrap `serialization.to_json` to
                return a `str` so that SQLAlchemy could then convert it to binary, or do the following, which
                changes the behaviour of the dialect to expect a binary value from the serializer.
                See Also https://github.com/sqlalchemy/sqlalchemy/blob/14bfbadfdf9260a1c40f63b31641b27fe9de12a0/lib/sqlalchemy/dialects/postgresql/asyncpg.py#L934  pylint: disable=line-too-long
                """

                def encoder(bin_value: bytes) -> bytes:
                    return b"\x01" + encode_json(bin_value)

                def decoder(bin_value: bytes) -> Any:
                    # the byte is the \x01 prefix for jsonb used by PostgreSQL.
                    # asyncpg returns it when format='binary'
                    return decode_json(bin_value[1:])

                dbapi_connection.await_(
                    dbapi_connection.driver_connection.set_type_codec(
                        "jsonb",
                        encoder=encoder,
                        decoder=decoder,
                        schema="pg_catalog",
                        format="binary",
                    ),
                )
                dbapi_connection.await_(
                    dbapi_connection.driver_connection.set_type_codec(
                        "json",
                        encoder=encoder,
                        decoder=decoder,
                        schema="pg_catalog",
                        format="binary",
                    ),
                )
        elif url.startswith("sqlite+aiosqlite"):
            engine = create_async_engine(
                url=url,
                future=True,
                json_serializer=encode_json,
                json_deserializer=decode_json,
                echo=self.ECHO,
                echo_pool=self.ECHO_POOL,
                pool_recycle=self.POOL_RECYCLE,
                pool_pre_ping=self.POOL_PRE_PING,
            )
            """Database session factory.

            See [`async_sessionmaker()`][sqlalchemy.ext.asyncio.async_sessionmaker].
            """

            @event.listens_for(engine.sync_engine, "connect")
            def _sqla_on_connect(dbapi_connection: Any, _: Any) -> Any:  # pragma: no cover
                """Override the default begin statement.  The disables the built in begin execution."""
                dbapi_connection.isolation_level = None

            @event.listens_for(engine.sync_engine, "begin")
            def _sqla_on_begin(dbapi_connection: Any) -> Any:  # pragma: no cover
                """Emits a custom begin"""
                dbapi_connection.exec_driver_sql("BEGIN")
        else:
            engine = create_async_engine(
                url=url,
                future=True,
                json_serializer=encode_json,
                json_deserializer=decode_json,
                echo=self.ECHO,
                echo_pool=self.ECHO_POOL,
                max_overflow=self.POOL_MAX_OVERFLOW,
                pool_size=self.POOL_SIZE,
                pool_timeout=self.POOL_TIMEOUT,
                pool_recycle=self.POOL_RECYCLE,
                pool_pre_ping=self.POOL_PRE_PING,
                pool_use_lifo=True,  # use lifo to reduce the number of idle connections
                poolclass=NullPool if self.POOL_DISABLED else None,
            )
        self._engine_instance = engine
        return self._engine_instance


@dataclass
class ViteSettings:
    """Server configurations."""

    DEV_MODE: bool = field(default_factory=get_env("VITE_DEV_MODE", False))
    """Start `vite` development server."""
    USE_SERVER_LIFESPAN: bool = field(default_factory=get_env("VITE_USE_SERVER_LIFESPAN", True))
    """Auto start and stop `vite` processes when running in development mode.."""
    HOST: str = field(default_factory=get_env("VITE_HOST", "0.0.0.0"))  # noqa: S104
    """The host the `vite` process will listen on.  Defaults to `0.0.0.0`"""
    PORT: int = field(default_factory=get_env("VITE_PORT", 5173))
    """The port to start vite on.  Default to `5173`"""
    HOT_RELOAD: bool = field(default_factory=get_env("VITE_HOT_RELOAD", True))
    """Start `vite` with HMR enabled."""
    """Enable React support in HMR."""
    BUNDLE_DIR: Path = field(default_factory=get_env("VITE_BUNDLE_DIR", Path(f"{BASE_DIR}/domain/web/public")))
    """Bundle directory"""
    RESOURCE_DIR: Path = field(default_factory=get_env("VITE_RESOURCE_DIR", Path("resources")))
    """Resource directory"""
    TEMPLATE_DIR: Path = field(default_factory=get_env("VITE_TEMPLATE_DIR", Path(f"{BASE_DIR}/domain/web/templates")))
    """Template directory."""
    ASSET_URL: str = field(default_factory=get_env("ASSET_URL", "/static/"))
    """Base URL for assets"""

    @property
    def set_static_files(self) -> bool:
        """Serve static assets."""
        return self.ASSET_URL.startswith("/")


@dataclass
class ServerSettings:
    """Server configurations."""

    HOST: str = field(default_factory=get_env("LITESTAR_HOST", "0.0.0.0"))  # noqa: S104
    """Server network host."""
    PORT: int = field(default_factory=get_env("LITESTAR_PORT", 8000))
    """Server port."""
    KEEPALIVE: int = field(default_factory=get_env("LITESTAR_KEEPALIVE", 65))
    """Seconds to hold connections open (65 is > AWS lb idle timeout)."""
    RELOAD: bool = field(default_factory=get_env("LITESTAR_RELOAD", False))
    """Turn on hot reloading."""
    RELOAD_DIRS: list[str] = field(default_factory=get_env("LITESTAR_RELOAD_DIRS", [f"{BASE_DIR}"]))
    """Directories to watch for reloading."""


@dataclass
class SaqSettings:
    """Server configurations."""

    PROCESSES: int = field(default_factory=get_env("SAQ_PROCESSES", 1))
    """The number of worker processes to start.

    Default is set to 1.
    """
    CONCURRENCY: int = field(default_factory=get_env("SAQ_CONCURRENCY", 10))
    """The number of concurrent jobs allowed to execute per worker process.

    Default is set to 10.
    """
    WEB_ENABLED: bool = field(default_factory=get_env("SAQ_WEB_ENABLED", True))
    """If true, the worker admin UI is hosted on worker startup."""
    USE_SERVER_LIFESPAN: bool = field(default_factory=get_env("SAQ_USE_SERVER_LIFESPAN", True))
    """Auto start and stop `saq` processes when starting the Litestar application."""
    DEMO_CRON_ENABLED: bool = field(default_factory=get_env("SAQ_DEMO_CRON_ENABLED", False))
    """Enable demo scheduled jobs. Keep disabled in production to avoid unnecessary worker load."""


@dataclass
class LogSettings:
    """Logger configuration"""

    # https://stackoverflow.com/a/1845097/6560549
    EXCLUDE_PATHS: str = r"\A(?!x)x"
    """Regex to exclude paths from logging."""
    HTTP_EVENT: str = "HTTP"
    """Log event name for logs from Litestar handlers."""
    INCLUDE_COMPRESSED_BODY: bool = False
    """Include 'body' of compressed responses in log output."""
    LEVEL: int = field(default_factory=get_env("LOG_LEVEL", 30))
    """Stdlib log levels.

    Only emit logs at this level, or higher.
    """
    OBFUSCATE_COOKIES: set[str] = field(default_factory=lambda: {"session", "XSRF-TOKEN"})
    """Request cookie keys to obfuscate."""
    OBFUSCATE_HEADERS: set[str] = field(default_factory=lambda: {"Authorization", "X-API-KEY", "X-XSRF-TOKEN"})
    """Request header keys to obfuscate."""
    JOB_FIELDS: list[str] = field(
        default_factory=lambda: [
            "function",
            "kwargs",
            "key",
            "scheduled",
            "attempts",
            "completed",
            "queued",
            "started",
            "result",
            "error",
        ],
    )
    """Attributes of the SAQ.

    [`Job`](https://github.com/tobymao/saq/blob/master/saq/job.py) to be
    logged.
    """
    REQUEST_FIELDS: list[RequestExtractorField] = field(
        default_factory=get_env(
            "LOG_REQUEST_FIELDS",
            [
                "path",
                "method",
                "query",
                "path_params",
            ],
            list[RequestExtractorField],
        ),
    )
    """Attributes of the [Request][litestar.connection.request.Request] to be
    logged."""
    RESPONSE_FIELDS: list[ResponseExtractorField] = field(
        default_factory=cast(
            "Callable[[],list[ResponseExtractorField]]",
            get_env(
                "LOG_RESPONSE_FIELDS",
                ["status_code"],
            ),
        )
    )
    """Attributes of the [Response][litestar.response.Response] to be
    logged."""
    WORKER_EVENT: str = "Worker"
    """Log event name for logs from SAQ worker."""
    SAQ_LEVEL: int = field(default_factory=get_env("SAQ_LOG_LEVEL", 50))
    """Level to log SAQ logs."""
    SQLALCHEMY_LEVEL: int = field(default_factory=get_env("SQLALCHEMY_LOG_LEVEL", 30))
    """Level to log SQLAlchemy logs."""
    ASGI_ACCESS_LEVEL: int = field(default_factory=get_env("ASGI_ACCESS_LOG_LEVEL", 30))
    """Level to log uvicorn access logs."""
    ASGI_ERROR_LEVEL: int = field(default_factory=get_env("ASGI_ERROR_LOG_LEVEL", 30))
    """Level to log uvicorn error logs."""


@dataclass
class RedisSettings:
    URL: str = field(default_factory=get_env("REDIS_URL", "redis://localhost:6379/0"))
    """A Redis connection URL."""
    SOCKET_CONNECT_TIMEOUT: int = field(default_factory=get_env("REDIS_CONNECT_TIMEOUT", 5))
    """Length of time to wait (in seconds) for a connection to become
    active."""
    HEALTH_CHECK_INTERVAL: int = field(default_factory=get_env("REDIS_HEALTH_CHECK_INTERVAL", 5))
    """Length of time to wait (in seconds) before testing connection health."""
    SOCKET_KEEPALIVE: bool = field(default_factory=get_env("REDIS_SOCKET_KEEPALIVE", True))
    """Length of time to wait (in seconds) between keepalive commands."""
    _client: Redis | None = field(default=None, init=False, repr=False)
    """Cached Redis client shared across the application lifecycle."""
    _loop_clients: dict[int, Redis] = field(default_factory=dict, init=False, repr=False)
    """Async-loop scoped Redis clients to avoid cross-loop transport errors."""

    @property
    def client(self) -> Redis:
        return self.get_client()

    def _build_client(self) -> Redis:
        return Redis.from_url(
            url=self.URL,
            encoding="utf-8",
            decode_responses=False,
            socket_connect_timeout=self.SOCKET_CONNECT_TIMEOUT,
            socket_keepalive=self.SOCKET_KEEPALIVE,
            health_check_interval=self.HEALTH_CHECK_INTERVAL,
        )

    def get_client(self) -> Redis:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            if self._client is None:
                self._client = self._build_client()
            return self._client

        loop_id = id(loop)
        client = self._loop_clients.get(loop_id)
        if client is None:
            client = self._build_client()
            self._loop_clients[loop_id] = client
        return client

    async def close_all_clients(self) -> None:
        """Close every cached Redis client owned by this settings instance."""
        seen: set[int] = set()
        clients: list[Redis] = []

        if self._client is not None:
            clients.append(self._client)
            seen.add(id(self._client))

        for client in self._loop_clients.values():
            if id(client) not in seen:
                clients.append(client)
                seen.add(id(client))

        for client in clients:
            with suppress(Exception):
                await cast("Any", client).aclose()

        self._client = None
        self._loop_clients.clear()


@dataclass
class RateLimitSettings:
    """Rate limit middleware configuration."""

    ENABLED: bool = field(default_factory=get_env("RATE_LIMIT_ENABLED", False))
    """Enable rate-limit middleware."""
    UNIT: str = field(default_factory=get_env("RATE_LIMIT_UNIT", "minute"))
    """Rate-limit time unit. Supported values: second, minute, hour, day."""
    REQUESTS: int = field(default_factory=get_env("RATE_LIMIT_REQUESTS", 60))
    """Allowed request count per configured unit."""
    EXCLUDE: list[str] | str = field(
        default_factory=get_env(
            "RATE_LIMIT_EXCLUDE",
            [
                "/health",
                "^/public/",
                "^/saq/static/",
            ],
            list[str],
        ),
    )
    """Path patterns to exclude from rate limiting."""
    EXCLUDE_OPT_KEY: str | None = field(default_factory=get_env("RATE_LIMIT_EXCLUDE_OPT_KEY", "disable_rate_limit"))
    """Route opt key used to disable rate limiting for specific handlers."""
    TRUST_PROXY_IP_HEADERS: bool = field(default_factory=get_env("RATE_LIMIT_TRUST_PROXY_IP_HEADERS", False))
    """Trust proxy-forwarded IP headers for rate-limit identity."""
    TRUSTED_PROXY_CIDRS: list[str] | str = field(
        default_factory=get_env("RATE_LIMIT_TRUSTED_PROXY_CIDRS", [], list[str])
    )
    """Trusted proxy CIDRs allowed to supply forwarded client IP headers."""

    @staticmethod
    def _parse_string_list(value: list[str] | str, env_name: str) -> list[str]:
        if isinstance(value, list):
            return [item.strip() for item in value if item.strip()]
        if value.startswith("[") and value.endswith("]"):
            try:
                parsed_value = cast("list[str]", json.loads(value))
            except (SyntaxError, ValueError) as exc:
                msg = f"{env_name} is not a valid list representation."
                raise ValueError(msg) from exc
            return [item.strip() for item in parsed_value if item.strip()]
        return [item.strip() for item in value.split(",") if item.strip()]

    def __post_init__(self) -> None:
        self.EXCLUDE = self._parse_string_list(self.EXCLUDE, "RATE_LIMIT_EXCLUDE")

        unit = self.UNIT.strip().lower()
        if unit not in {"second", "minute", "hour", "day"}:
            msg = "RATE_LIMIT_UNIT must be one of: second, minute, hour, day."
            raise ValueError(msg)
        self.UNIT = unit

        if self.REQUESTS <= 0:
            msg = "RATE_LIMIT_REQUESTS must be greater than 0."
            raise ValueError(msg)

        if self.EXCLUDE_OPT_KEY is not None:
            opt_key = self.EXCLUDE_OPT_KEY.strip()
            self.EXCLUDE_OPT_KEY = opt_key or None

        self.TRUSTED_PROXY_CIDRS = self._parse_string_list(
            self.TRUSTED_PROXY_CIDRS,
            "RATE_LIMIT_TRUSTED_PROXY_CIDRS",
        )
        for cidr in self.TRUSTED_PROXY_CIDRS:
            try:
                ip_network(cidr, strict=False)
            except ValueError as exc:
                msg = f"RATE_LIMIT_TRUSTED_PROXY_CIDRS contains invalid CIDR: {cidr}"
                raise ValueError(msg) from exc

        if self.TRUST_PROXY_IP_HEADERS and not self.TRUSTED_PROXY_CIDRS:
            msg = "RATE_LIMIT_TRUSTED_PROXY_CIDRS must be set when RATE_LIMIT_TRUST_PROXY_IP_HEADERS=true."
            raise ValueError(msg)

    @property
    def rate_limit(self) -> tuple[DurationUnit, int]:
        return cast("tuple[DurationUnit, int]", (self.UNIT, self.REQUESTS))

    @property
    def trusted_proxy_networks(self) -> tuple[IPv4Network | IPv6Network, ...]:
        return tuple(ip_network(cidr, strict=False) for cidr in self.TRUSTED_PROXY_CIDRS)


@dataclass
class TwilioSettings:
    """Twilio configuration for OTP delivery."""

    ACCOUNT_SID: str = field(default_factory=get_env("TWILIO_ACCOUNT_SID", ""))
    """Twilio Account SID."""
    AUTH_TOKEN: str = field(default_factory=get_env("TWILIO_AUTH_TOKEN", ""))
    """Twilio Auth Token."""
    WHATSAPP_FROM: str = field(default_factory=get_env("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"))
    """Twilio WhatsApp sender (sandbox default)."""
    OTP_CODE_TTL: int = field(default_factory=get_env("OTP_CODE_TTL", 300))
    """Seconds before an OTP code expires in Redis."""
    OTP_ATTEMPTS_TTL: int = field(default_factory=get_env("OTP_ATTEMPTS_TTL", 300))
    """Seconds before OTP verification-check attempts reset."""
    OTP_SEND_ATTEMPTS_TTL: int = field(default_factory=get_env("OTP_SEND_ATTEMPTS_TTL", 3600))
    """Seconds before OTP send-attempt counters reset."""
    OTP_MAX_ATTEMPTS: int = field(default_factory=get_env("OTP_MAX_ATTEMPTS", 3))
    """Maximum OTP verification attempts before lockout."""
    VERIFIED_MOBILE_TTL: int = field(default_factory=get_env("VERIFIED_MOBILE_TTL", 300))
    """Seconds a verified mobile remains valid before registration must complete."""

    @property
    def is_configured(self) -> bool:
        return bool(self.ACCOUNT_SID and self.AUTH_TOKEN and self.WHATSAPP_FROM and "*" not in self.WHATSAPP_FROM)

    @property
    def otp_delivery_label(self) -> str:
        return "WhatsApp"

    @property
    def otp_delivery_message(self) -> str:
        return self.otp_delivery_label

    @property
    def verified_via(self) -> str:
        return "whatsapp"


@dataclass
class AppSettings:
    """Application configuration"""

    APP_LOC: str = "app.asgi:create_app"
    """Path to app executable, or factory."""
    URL: str = field(default_factory=get_env("APP_URL", "http://localhost:8000"))
    """The frontend base URL"""
    DEBUG: bool = field(default_factory=get_env("LITESTAR_DEBUG", False))
    """Run `Litestar` with `debug=True`."""
    SECRET_KEY: str = field(
        default_factory=get_env("SECRET_KEY", binascii.hexlify(os.urandom(32)).decode(encoding="utf-8")),
    )
    """Application secret key."""
    NAME: str = field(default_factory=lambda: "app")
    """Application name."""
    ALLOWED_CORS_ORIGINS: list[str] | str = field(default_factory=get_env("ALLOWED_CORS_ORIGINS", ["*"], list[str]))
    """Allowed CORS Origins"""
    CSRF_COOKIE_NAME: str = field(default_factory=get_env("CSRF_COOKIE_NAME", "XSRF-TOKEN"))
    """CSRF Cookie Name"""
    CSRF_HEADER_NAME: str = field(default_factory=get_env("CSRF_HEADER_NAME", "X-XSRF-TOKEN"))
    """CSRF Header Name"""
    CSRF_COOKIE_SECURE: bool = field(default_factory=get_env("CSRF_COOKIE_SECURE", False))
    """CSRF Secure Cookie"""
    AUTH_COOKIE_SECURE: bool = field(default_factory=get_env("AUTH_COOKIE_SECURE", False))
    """JWT auth cookie secure flag."""
    JWT_ENCRYPTION_ALGORITHM: str = field(default_factory=lambda: "HS256")
    """JWT Encryption Algorithm"""
    GITHUB_OAUTH2_CLIENT_ID: str = field(default_factory=get_env("GITHUB_OAUTH2_CLIENT_ID", ""))
    """Github OAuth2 Client ID"""
    GITHUB_OAUTH2_CLIENT_SECRET: str = field(default_factory=get_env("GITHUB_OAUTH2_CLIENT_SECRET", ""))
    """Github OAuth2 Client Secret"""

    @property
    def slug(self) -> str:
        """Return a slugified name.

        Returns:
            `self.NAME`, all lowercase and hyphens instead of spaces.
        """
        return slugify(self.NAME)

    def __post_init__(self) -> None:
        # Check if the ALLOWED_CORS_ORIGINS is a string.
        if isinstance(self.ALLOWED_CORS_ORIGINS, str):
            # Check if the string starts with "[" and ends with "]", indicating a list.
            if self.ALLOWED_CORS_ORIGINS.startswith("[") and self.ALLOWED_CORS_ORIGINS.endswith("]"):
                try:
                    # Safely evaluate the string as a Python list.
                    self.ALLOWED_CORS_ORIGINS = json.loads(self.ALLOWED_CORS_ORIGINS)
                except (SyntaxError, ValueError):
                    # Handle potential errors if the string is not a valid Python literal.
                    msg = "ALLOWED_CORS_ORIGINS is not a valid list representation."
                    raise ValueError(msg) from None
            else:
                # Split the string by commas into a list if it is not meant to be a list representation.
                self.ALLOWED_CORS_ORIGINS = [host.strip() for host in self.ALLOWED_CORS_ORIGINS.split(",")]

        if not self.CSRF_COOKIE_SECURE and self.URL.lower().startswith("https://"):
            self.CSRF_COOKIE_SECURE = True
        if not self.AUTH_COOKIE_SECURE and self.URL.lower().startswith("https://"):
            self.AUTH_COOKIE_SECURE = True


@dataclass
class Settings:
    app: AppSettings = field(default_factory=AppSettings)
    db: DatabaseSettings = field(default_factory=DatabaseSettings)
    vite: ViteSettings = field(default_factory=ViteSettings)
    server: ServerSettings = field(default_factory=ServerSettings)
    log: LogSettings = field(default_factory=LogSettings)
    redis: RedisSettings = field(default_factory=RedisSettings)
    saq: SaqSettings = field(default_factory=SaqSettings)
    rate_limit: RateLimitSettings = field(default_factory=RateLimitSettings)
    twilio: TwilioSettings = field(default_factory=TwilioSettings)

    @classmethod
    def from_env(cls, dotenv_filename: str = ".env") -> Settings:
        from litestar.cli._utils import console  # noqa: PLC0415

        env_file = Path(f"{os.curdir}/{dotenv_filename}")
        if env_file.is_file():
            from dotenv import load_dotenv  # noqa: PLC0415

            console.print(f"[yellow]Loading environment configuration from {dotenv_filename}[/]")

            load_dotenv(env_file, override=True)
        return Settings()


@lru_cache(maxsize=1, typed=True)
def get_settings() -> Settings:
    return Settings.from_env()
