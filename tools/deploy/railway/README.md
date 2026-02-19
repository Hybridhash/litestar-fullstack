# Railway Multi-Service Setup (Web + Worker)

This project supports running background jobs via SAQ in a dedicated Railway worker service.

## Services

1. **Web service**
   - Config file: `tools/deploy/railway/railway.app.json`
   - Start command: `app database upgrade --no-prompt && app run --wc 2 --host 0.0.0.0 --port $PORT`
2. **Worker service**
   - Config file: `tools/deploy/railway/railway.worker.json`
   - Start command: `app workers run`

## Required Variables

Set these for both services unless noted otherwise:

- `SECRET_KEY` (same value in both services)
- `DATABASE_URL=${{Postgres.DATABASE_URL}}`
- `REDIS_URL=${{Redis.REDIS_URL}}`
- `LITESTAR_DEBUG=false`
- `VITE_DEV_MODE=false`

Web service only:

- `LITESTAR_PORT=${{PORT}}`
- `SAQ_USE_SERVER_LIFESPAN=false`  # prevent duplicate workers in web process

Worker service only:

- `SAQ_USE_SERVER_LIFESPAN=false`
- `SAQ_WEB_ENABLED=false`

## Upstream Difference (Important)

The upstream `src/py` implementation uses `SAQ_REDIS_URL` in SAQ settings.
This repository's current `src/app` implementation uses `REDIS_URL` for SAQ queue DSN
via `settings.redis.URL`, so do not rename it to `SAQ_REDIS_URL` unless the code is migrated.

## Notes

- Keep the worker service **non-sleeping** (`sleepApplication: false`), otherwise queued jobs will not be processed while asleep.
- Worker service has no HTTP health endpoint by default.
