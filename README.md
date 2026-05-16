<!-- markdownlint-disable -->
<p align="center">
  <img src="https://raw.githubusercontent.com/litestar-org/branding/1dc4635b192d29d864fcee6f3f73ea0ff6fecf10/assets/Branding%20-%20SVG%20-%20Transparent/Fullstack%20-%20Banner%20-%20Inline%20-%20Light.svg#gh-light-mode-only" alt="Litestar Logo - Light" width="100%" height="auto" />
  <img src="https://raw.githubusercontent.com/litestar-org/branding/1dc4635b192d29d864fcee6f3f73ea0ff6fecf10/assets/Branding%20-%20SVG%20-%20Transparent/Fullstack%20-%20Banner%20-%20Inline%20-%20Dark.svg#gh-dark-mode-only" alt="Litestar Logo - Dark" width="100%" height="auto" />
</p>
<!-- markdownlint-restore -->

<div align="center">
<!-- prettier-ignore-start -->

| Project   |     | Status                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| --------- | :-- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CI/CD     |     | [![Tests and Linting](https://github.com/litestar-org/litestar-fullstack/actions/workflows/ci.yaml/badge.svg)](https://github.com/litestar-org/litestar-fullstack/actions/workflows/ci.yaml) [![Documentation Building](https://github.com/litestar-org/litestar-fullstack/actions/workflows/docs.yaml/badge.svg)](https://github.com/litestar-org/litestar-fullstack/actions/workflows/docs.yaml)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Quality   |     | [![Coverage](https://sonarcloud.io/api/project_badges/measure?project=litestar-org_litestar-fullstack&metric=coverage)](https://sonarcloud.io/summary/new_code?id=litestar-org_litestar) [![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=litestar-org_litestar-fullstack&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=litestar-org_litestar) [![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=litestar-org_litestar-fullstack&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=litestar-org_litestar) [![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=litestar-org_litestar-fullstack&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=litestar-org_litestar) [![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=litestar-org_litestar-fullstack&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=litestar-org_litestar)                                                                                                                                                                                                                     |
| Community |     | [![Reddit](https://img.shields.io/reddit/subreddit-subscribers/litestarapi?label=r%2FLitestar&logo=reddit&labelColor=202235&color=edb641&logoColor=edb641)](https://reddit.com/r/litestarapi) [![Discord](https://img.shields.io/discord/919193495116337154?labelColor=202235&color=edb641&label=chat%20on%20discord&logo=discord&logoColor=edb641)](https://discord.gg/litestar) [![Matrix](https://img.shields.io/badge/chat%20on%20Matrix-bridged-202235?labelColor=202235&color=edb641&logo=matrix&logoColor=edb641)](https://matrix.to/#/#litestar:matrix.org) [![Medium](https://img.shields.io/badge/Medium-202235?labelColor=202235&color=edb641&logo=medium&logoColor=edb641)](https://blog.litestar.dev) [![Twitter](https://img.shields.io/twitter/follow/LitestarAPI?labelColor=202235&color=edb641&logo=twitter&logoColor=edb641&style=flat)](https://twitter.com/LitestarAPI) [![Blog](https://img.shields.io/badge/Blog-litestar.dev-202235?logo=blogger&labelColor=202235&color=edb641&logoColor=edb641)](https://blog.litestar.dev)                                                                                                                                                                                                |
| Meta      |     | [![Litestar Project](https://img.shields.io/badge/Litestar%20Org-%E2%AD%90%20Litestar-202235.svg?logo=python&labelColor=202235&color=edb641&logoColor=edb641)](https://github.com/litestar-org/litestar) [![types - Mypy](https://img.shields.io/badge/types-Mypy-202235.svg?logo=python&labelColor=202235&color=edb641&logoColor=edb641)](https://github.com/python/mypy) [![License - MIT](https://img.shields.io/badge/license-MIT-202235.svg?logo=python&labelColor=202235&color=edb641&logoColor=edb641)](https://spdx.org/licenses/) [![Litestar Sponsors](https://img.shields.io/badge/Sponsor-%E2%9D%A4-%23edb641.svg?&logo=github&logoColor=edb641&labelColor=202235)](https://github.com/sponsors/litestar-org) [![linting - Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json&labelColor=202235)](https://github.com/astral-sh/ruff) [![code style - Black](https://img.shields.io/badge/code%20style-black-000000.svg?logo=python&labelColor=202235&logoColor=edb641)](https://github.com/psf/black) [![All Contributors](https://img.shields.io/github/all-contributors/litestar-org/litestar?labelColor=202235&color=edb641&logoColor=edb641)](#contributors-) |

<!-- prettier-ignore-end -->
</div>

# Litestar Fullstack Reference Application

This is a reference application that you can use to get your next Litestar application running quickly.

It contains most of the boilerplate required for a production web API with features like:

- Latest Litestar configured with best practices
- Integration with [SQLAlchemy 2.0](https://www.sqlalchemy.org/), [SAQ (Simple Asynchronous Queue)](https://saq-py.readthedocs.io/en/latest/), [Structlog](https://www.structlog.org/en/stable/), and [Granian](<(https://www.structlog.org/en/stable/)](https://github.com/emmett-framework/granian)>)
- Extends built-in Litestar click CLI
- Server-rendered frontend with JinjaX components, DaisyUI styling, HTMX interactions, and Alpine.js state, integrated with Vite HMR
- Multi-stage Docker build using a minimal Python 3.13 runtime image.
  - Optional Multi-stage Distroless Docker build.
- Pre-configured user model that includes teams and associated team roles
- Examples of using guards for superuser and team-based auth.
- Examples using raw SQL for more complex queries

Take what you need and adapt it to your own projects

## Quick Start

To quickly get a development environment running, run the following:

```shell
make install
. .venv/bin/activate
```

### Local Development

```bash
cp .env.local.example .env
make start-infra # this starts a database and redis instance only
make configure-twilio # optional: prompts for Twilio WhatsApp OTP settings and writes them to .env
# Note: the Postgres Docker image and data mount support Postgres 18+ by default. The image version is controlled by POSTGRES_VERSION (default: 18); if you have an existing DB volume created by an older Postgres version, back it up before switching or set POSTGRES_VERSION to the older version (e.g., 15).
# this will start the SAQ worker, Vite development process, and Litestar
uv run app run

# to stop the database and redis, run
make stop-infra
```

Notes:

- `make configure-twilio` updates `.env` by default. Use `ENV_FILE=.env.somefile` if you keep a different local env file.
- The helper prompts for a real `TWILIO_AUTH_TOKEN` without echoing it back to the terminal.
- The helper configures the direct WhatsApp OTP sender used by the application.

### Docker

If you want to run the entire development environment containerized, you can run the following:

```bash
docker compose up
```

### Railway (CLI Deploy)

This repository includes a Railway deploy helper for a split runtime:

- `Litestar Web Frontend` (HTTP app)
- `SAQ Worker` (background jobs)
- `Postgres` + `Redis` managed services

First-time setup (creates/links services and configures variables):

```bash
railway login
./tools/deploy/railway/deploy.sh --project-name "<your-project-name>"
```

Subsequent deploys (stream logs):

```bash
./tools/deploy/railway/deploy.sh --ci
```

Useful checks:

```bash
railway service link "Litestar Web Frontend" && railway service status --json
railway service link "SAQ Worker" && railway service status --json
railway domain --service "Litestar Web Frontend" --json
```

Create or promote a superuser in Railway production:

```bash
railway ssh \
  --environment production \
  --service "Litestar Web Frontend" \
  'bash -lc "/opt/venv/bin/app users create-user --email \"YOUR_ADMIN_EMAIL\" --name \"YOUR_ADMIN_NAME\" --password \"YOUR_STRONG_PASSWORD\" --superuser"'
```

If the user already exists:

```bash
railway ssh \
  --environment production \
  --service "Litestar Web Frontend" \
  'bash -lc "/opt/venv/bin/app users promote-to-superuser --email \"YOUR_ADMIN_EMAIL\""'
```

Why this pattern is required:

- Replace the placeholder admin values before running the command, and use a strong unique password.
- Run `railway link` first so the CLI targets the correct project. If you manage multiple Railway projects, add `--project <your-project-id>` explicitly.
- `railway ssh ... 'bash -lc ...'` ensures Nix profile libraries are loaded (required for `greenlet` / SQLAlchemy async path).
- `/opt/venv/bin/app` avoids PATH issues inside non-interactive container commands.
- Avoid running `railway run ... uv run app ...` from repository root when `.env` exists; this project loads `.env` with override and may point commands to your local database.

Operational notes for the current setup:

- Deploys are currently CLI-triggered; `git push` does not auto-deploy unless Railway GitHub source wiring is enabled.
- Web startup runs migrations first (`app database upgrade --no-prompt && app run ...`), then starts the server.
- With `numReplicas: 1`, brief downtime can occur during rollout.
- Postgres/Redis data, env vars, and domain config persist across app deploys (data loss risk is mainly destructive actions like deleting a service/volume or destructive migrations).

Railway hardening backlog:

- [ ] GitHub auto-deploy wiring check (optional switch from manual CLI deploys)
- [ ] Safer migration strategy for scale-out (dedicated release job or migration guard for multi-replica startups)
- [ ] Near-zero downtime pattern (replica strategy + rollout tuning)

### Details

We have documented the process to help you get the repository up and running.
Check out the [documentation][docs] for more information.

[//]: # "links"
[docs]: https://docs.fullstack.litestar.dev/

---

## Production Deployment: Cloudflare + Railway

### Rate Limiting

This application includes a configurable rate-limiting middleware built on Litestar's `RateLimitConfig`. It throttles requests per client IP to protect against abuse and brute-force attacks.

#### Default Settings

| Environment Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT_ENABLED` | `false` | Master switch for rate limiting |
| `RATE_LIMIT_UNIT` | `minute` | Time window: `second`, `minute`, `hour`, or `day` |
| `RATE_LIMIT_REQUESTS` | `60` | Max requests allowed per unit per client |
| `RATE_LIMIT_EXCLUDE` | `/health,^/public/,^/saq/static/` | Comma-separated paths excluded from limiting |
| `RATE_LIMIT_EXCLUDE_OPT_KEY` | `disable_rate_limit` | Route opt key to exempt individual handlers |

#### Cloudflare Proxy Trust (Required for Correct Per-User Limiting)

When deployed behind Cloudflare, the app sees Cloudflare's edge server IPs instead of real client IPs. Without proxy trust configured, all users share rate-limit buckets grouped by proxy IP, making the limiter ineffective.

| Environment Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT_TRUST_PROXY_IP_HEADERS` | `false` | Enable reading real client IP from proxy headers |
| `RATE_LIMIT_TRUSTED_PROXY_CIDRS` | (empty) | Comma-separated CIDR ranges of trusted proxies |

When `TRUST_PROXY_IP_HEADERS=true`, the identifier reads the real client IP from `CF-Connecting-IP` (Cloudflare) or `X-Real-IP` (Railway/nginx), but **only if** the direct connection IP is within `TRUSTED_PROXY_CIDRS`. Requests from untrusted IPs have their headers ignored (anti-spoofing).

**Recommended production values:**

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_TRUST_PROXY_IP_HEADERS=true
RATE_LIMIT_TRUSTED_PROXY_CIDRS=0.0.0.0/0,::/0
```

#### Security Risks to Consider

> **Important:** The `0.0.0.0/0,::/0` CIDR setting trusts proxy headers from **any** source. This is only safe if all traffic is forced through Cloudflare.

**Before enabling permissive proxy trust, you must:**

1. **Disable the Railway default public domain.** Railway generates a `*.up.railway.app` domain for every service. If this is still active, attackers can bypass Cloudflare and hit your app directly with spoofed `CF-Connecting-IP` headers. Go to Railway dashboard → Web service → Settings → Networking → remove or disable the `*.up.railway.app` domain. Keep only your custom domain (e.g., `kipeer.com`, `www.kipeer.com`) which routes through Cloudflare.

2. **Verify DNS points to Cloudflare, not Railway.** Your domain's DNS A/CNAME records should point to Cloudflare (orange cloud enabled), not directly to Railway's IP.

**Optional hardening:**

- Add a Cloudflare Transform Rule that injects a secret header (e.g., `X-Origin-Verify: <secret>`) on every request. Validate this header in your app before trusting forwarded IP headers. This prevents spoofing even if the origin IP is discovered.

**If you cannot close the Railway bypass path**, use Cloudflare's published IP ranges instead of `0.0.0.0/0`:

```bash
RATE_LIMIT_TRUSTED_PROXY_CIDRS=173.245.48.0/20,103.21.244.0/22,103.22.200.0/22,103.31.4.0/22,141.101.64.0/18,108.162.192.0/18,190.93.240.0/20,188.114.96.0/20,197.234.240.0/22,198.41.128.0/17,162.158.0.0/15,104.16.0.0/13,104.24.0.0/14,172.64.0.0/13,131.0.72.0/22
```

Note: With Railway's internal load balancer between Cloudflare and your app, the immediate peer IP may not match Cloudflare's ranges. In this case, the strict CIDR list won't work and you need the permissive `0.0.0.0/0` setting with the Railway domain disabled.

#### Protection Stack Summary

| Layer | What It Stops | Configuration |
|---|---|---|
| Cloudflare (edge) | L3/L4 DDoS, bot traffic, known bad IPs | Cloudflare dashboard |
| Railway (infra) | Network floods, 10k connection limit, 11k req/sec | Automatic |
| App rate limiter | Per-IP request abuse, brute force | `RATE_LIMIT_*` env vars |
| CSRF protection | Cross-site request forgery | Built-in (enabled by default) |
| CORS | Unauthorized cross-origin requests | `ALLOWED_CORS_ORIGINS` env var |

---

### SAQ Worker: Cost Optimization

The SAQ (Simple Asynchronous Queue) worker runs as a separate Railway service for background job processing. The default template includes **demo scheduled tasks** that can cause unexpectedly high costs if left running in production.

#### The Problem

The demo tasks in `src/app/domain/system/tasks.py` are placeholders that do no real work — they just `asyncio.sleep()` and log messages:

- `system_upkeep`: Runs every hour, sleeps for 180 seconds total
- `background_worker_task`: Runs every minute, sleeps for 20 seconds

Combined with the default `SAQ_CONCURRENCY=10` (10 concurrent polling slots), this creates constant CPU and memory usage. Railway bills cumulative resource-hours, so a worker using 200 MB 24/7 shows up as ~140 GB on the monthly bill.

**Observed cost impact:** ~$33/month for the SAQ Worker alone (90% of total bill), doing zero useful work.

#### Recommended Railway Settings

| Environment Variable | Value | Why |
|---|---|---|
| `SAQ_PROCESSES` | `1` | Single worker process |
| `SAQ_CONCURRENCY` | `1` | Single job slot (not 10) |
| `SAQ_WEB_ENABLED` | `false` | Disable the admin dashboard |
| `SAQ_DEMO_CRON_ENABLED` | `false` | Disable demo scheduled tasks |
| `SAQ_USE_SERVER_LIFESPAN` | `false` | **Set this if you have no real background tasks.** Stops the worker process entirely. Cost goes to $0. |

#### When to Re-enable

When you build real features that need background processing (sending emails, generating reports, processing uploads):

1. Replace the demo tasks in `tasks.py` with real implementations
2. Set `SAQ_DEMO_CRON_ENABLED=false` (keep demos off)
3. Set `SAQ_USE_SERVER_LIFESPAN=true`
4. Configure `SAQ_CONCURRENCY` based on your workload
5. Add your own `CronJob` entries or enqueue jobs from your route handlers

---

<details>

<summary>Command Examples</summary>

## App Commands

```bash
❯ app

 Usage: app [OPTIONS] COMMAND [ARGS]...

 Litestar CLI.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --app          TEXT       Module path to a Litestar application (TEXT)       │
│ --app-dir      DIRECTORY  Look for APP in the specified directory, by adding │
│                           this to the PYTHONPATH. Defaults to the current    │
│                           working directory.                                 │
│                           (DIRECTORY)                                        │
│ --help     -h             Show this message and exit.                        │
╰──────────────────────────────────────────────────────────────────────────────╯
Using Litestar app from env: 'app.asgi:app'
Loading environment configuration from .env
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ assets       Manage Vite Tasks.                                              │
│ database     Manage SQLAlchemy database components.                          │
│ info         Show information about the detected Litestar app.               │
│ routes       Display information about the application's routes.             │
│ run          Run a Litestar app.                                             │
│ schema       Manage server-side OpenAPI schemas.                             │
│ sessions     Manage server-side sessions.                                    │
│ users        Manage application users and roles.                             │
│ version      Show the currently installed Litestar version.                  │
│ workers      Manage background task workers.                                 │
╰──────────────────────────────────────────────────────────────────────────────╯

```

## Database Commands

Alembic integration is built directly into the CLI under the `database` command.

The following shows the commands available with the `database` CLI command.

```bash
❯ app database
Using Litestar app from env: 'app.asgi:create_app'

 Usage: app database [OPTIONS] COMMAND [ARGS]...

 Manage SQLAlchemy database components.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help  -h    Show this message and exit.                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ downgrade              Downgrade database to a specific revision.            │
│ init                   Initialize migrations for the project.                │
│ make-migrations        Create a new migration revision.                      │
│ merge-migrations       Merge multiple revisions into a single new revision.  │
│ show-current-revision  Shows the current revision for the database.          │
│ stamp-migration        Mark (Stamp) a specific revision as current without   │
│                        applying the migrations.                              │
│ upgrade                Upgrade database to a specific revision.              │
╰──────────────────────────────────────────────────────────────────────────────╯

```

### Upgrading the Database

To upgrade the database to the latest revision, you can use the following command:

```bash
❯ app database upgrade
Using Litestar app from env: 'app.asgi:create_app'
Starting database upgrade process ───────────────────────────────────────────────
Are you sure you you want migrate the database to the "head" revision? [y/n]: y
2023-10-01T19:44:13.536101Z [debug    ] Using selector: EpollSelector
2023-10-01T19:44:13.623437Z [info     ] Context impl PostgresqlImpl.
2023-10-01T19:44:13.623617Z [info     ] Will assume transactional DDL.
2023-10-01T19:44:13.667920Z [info     ] Running upgrade  -> c3a9a11cc35d, init
2023-10-01T19:44:13.774932Z [debug    ] new branch insert c3a9a11cc35d
2023-10-01T19:44:13.783804Z [info     ] Pool disposed. Pool size: 5  Connections
 in pool: 0 Current Overflow: -5 Current Checked out connections: 0
2023-10-01T19:44:13.784013Z [info     ] Pool recreating
```

After the upgrade, load the default roles so signup can assign the configured role:

```bash
❯ app users create-roles
```

## Worker Commands

The following shows the commands available with the `workers` CLI command. This controls the `saq` worker processes. However, when using the `SAQ_USE_SERVER_LIFESPAN=True` environment variable, the background workers are automatically started and stopped with the Litestar HTTP server.

```bash
❯ app workers
Using Litestar app from env: 'app.asgi:create_app'

 Usage: app workers [OPTIONS] COMMAND [ARGS]...

 Manage application background workers.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help  -h    Show this message and exit.                                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ run       Run background worker processes.                                   │
│ status    Check the status of currently configured workers and queues.       │
╰──────────────────────────────────────────────────────────────────────────────╯

```

## Run Commands

To run the application through Granian (HTTP1 or HTTP2) using the standard Litestar CLI, you can use the following:

```bash
❯ app run --help
Using Litestar app from env: 'app.asgi:app'
Loading environment configuration from .env

 Usage: app run [OPTIONS]

 Run a Litestar app.
 The app can be either passed as a module path in the form of <module
 name>.<submodule>:<app instance or factory>, set as an environment variable
 LITESTAR_APP with the same format or automatically discovered from one of
 these canonical paths: app.py, asgi.py, application.py or app/__init__.py.
 When auto-discovering application factories, functions with the name
 ``create_app`` are considered, or functions that are annotated as returning a
 ``Litestar`` instance.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --port                   -p  INTEGER                 Serve under this port   │
│                                                      (INTEGER)               │
│                                                      [default: 8000]         │
│ --wc,--web-concurrency…  -W  INTEGER RANGE           The number of processes │
│                              [1<=x<=7]               to start.               │
│                                                      (INTEGER RANGE)         │
│                                                      [default: 1; 1<=x<=7]   │
│ --threads                    INTEGER RANGE [x>=1]    The number of threads.  │
│                                                      (INTEGER RANGE)         │
│                                                      [default: 1; x>=1]      │
│ --blocking-threads           INTEGER RANGE [x>=1]    The number of blocking  │
│                                                      threads.                │
│                                                      (INTEGER RANGE)         │
│                                                      [default: 1; x>=1]      │
│ --threading-mode             THREADMODES             Threading mode to use.  │
│                                                      (THREADMODES)           │
│ --http                       HTTPMODES               HTTP Version to use     │
│                                                      (HTTP or HTTP2)         │
│                                                      (HTTPMODES)             │
│ --opt                                                Enable additional event │
│                                                      loop optimizations      │
│ --backlog                    INTEGER RANGE [x>=128]  Maximum number of       │
│                                                      connections to hold in  │
│                                                      backlog.                │
│                                                      (INTEGER RANGE)         │
│                                                      [default: 1024; x>=128] │
│ --host                   -H  TEXT                    Server under this host  │
│                                                      (TEXT)                  │
│                                                      [default: 127.0.0.1]    │
│ --ssl-keyfile                FILE                    SSL key file (FILE)     │
│ --ssl-certificate            FILE                    SSL certificate file    │
│                                                      (FILE)                  │
│ --create-self-signed-c…                              If certificate and key  │
│                                                      are not found at        │
│                                                      specified locations,    │
│                                                      create a self-signed    │
│                                                      certificate and a key   │
│ --http1-buffer-size          INTEGER RANGE           Set the maximum buffer  │
│                              [x>=8192]               size for HTTP/1         │
│                                                      connections             │
│                                                      (INTEGER RANGE)         │
│                                                      [default: 417792;       │
│                                                      x>=8192]                │
│ --http1-keep-alive/--n…                              Enables or disables     │
│                                                      HTTP/1 keep-alive       │
│                                                      [default:               │
│                                                      http1-keep-alive]       │
│ --http1-pipeline-flush…                              Aggregates HTTP/1       │
│                                                      flushes to better       │
│                                                      support pipelined       │
│                                                      responses               │
│                                                      (experimental)          │
│ --http2-adaptive-windo…                              Sets whether to use an  │
│                                                      adaptive flow control   │
│                                                      for HTTP2               │
│ --http2-initial-connec…      INTEGER                 Sets the max            │
│                                                      connection-level flow   │
│                                                      control for HTTP2       │
│                                                      (INTEGER)               │
│ --http2-initial-stream…      INTEGER                 Sets the                │
│                                                      `SETTINGS_INITIAL_WIND… │
│                                                      option for HTTP2        │
│                                                      stream-level flow       │
│                                                      control                 │
│                                                      (INTEGER)               │
│ --http2-keep-alive-int…      OPTIONAL                Sets an interval for    │
│                                                      HTTP2 Ping frames       │
│                                                      should be sent to keep  │
│                                                      a connection alive      │
│                                                      (OPTIONAL)              │
│ --http2-keep-alive-tim…      INTEGER                 Sets a timeout for      │
│                                                      receiving an            │
│                                                      acknowledgement of the  │
│                                                      HTTP2 keep-alive ping   │
│                                                      (INTEGER)               │
│ --http2-max-concurrent…      INTEGER                 Sets the                │
│                                                      SETTINGS_MAX_CONCURREN… │
│                                                      option for HTTP2        │
│                                                      connections             │
│                                                      (INTEGER)               │
│ --http2-max-frame-size       INTEGER                 Sets the maximum frame  │
│                                                      size to use for HTTP2   │
│                                                      (INTEGER)               │
│ --http2-max-headers-si…      INTEGER                 Sets the max size of    │
│                                                      received header frames  │
│                                                      (INTEGER)               │
│ --http2-max-send-buffe…      INTEGER                 Set the maximum write   │
│                                                      buffer size for each    │
│                                                      HTTP/2 stream           │
│                                                      (INTEGER)               │
│ --url-path-prefix            TEXT                    URL path prefix the app │
│                                                      is mounted on           │
│                                                      (TEXT)                  │
│ --debug                  -d                          Run app in debug mode   │
│ --pdb,--use-pdb          -P                          Drop into PDB on an     │
│                                                      exception               │
│ --respawn-failed-worke…                              Enable workers respawn  │
│                                                      on unexpected exit      │
│ --reload                 -r                          Reload server on        │
│                                                      changes                 │
│ --help                   -h                          Show this message and   │
│                                                      exit.                   │
╰──────────────────────────────────────────────────────────────────────────────╯

```
