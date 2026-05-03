# api

FastAPI service for the property valuations model.

## Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv)
- Docker (for the Supabase CLI local stack)
- [Supabase CLI](https://supabase.com/docs/guides/cli)

## Local dev

```bash
# From repo root
supabase start

# In packages/api
cp .env.example .env
uv sync
uv run uvicorn api.main:app --reload
```

API runs on `http://localhost:8000`; Supabase Studio on `http://localhost:54323`.

## Tests

```bash
# Fast unit tests (no Docker required)
uv run pytest -m "not integration"

# All tests (requires `supabase start` running)
uv run pytest
```

## Environment

See `.env.example` for the full list. Required in production:

- `DATABASE_URL` — asyncpg DSN (service-role)
- `SUPABASE_URL`
- `SUPABASE_JWT_SECRET` — HS256 secret for JWT verification
- `ALLOWED_ORIGINS` — comma-separated CORS whitelist

## Deploy

Render Web Service using `Dockerfile` + `render.yaml`. Run `scripts/smoke.sh <BASE_URL> <JWT>` post-deploy.

## Engine dependency

Dev uses the local editable engine via `[tool.uv.sources]`. Release builds (`uv sync --no-sources` or pip with the tagged git ref) resolve to the pinned version from `[project.dependencies]`.
