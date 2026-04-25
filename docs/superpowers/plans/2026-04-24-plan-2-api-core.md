# Plan 2 — API Core (FastAPI service) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Status (as of 2026-04-25)

**✅ COMPLETE + LIVE-VERIFIED — all 31 tasks delivered + 4 post-plan fixes/features on branch `plan-2-api-core` (47 commits ahead of `main`).**

The branch was stood up against a real hosted Supabase project (`lftvhwprprlgclhbxjqf`, region `af-south-1`) and exercised end-to-end via Swagger UI. Two real bugs and two usability features landed during the live-test session — see the **Post-plan-completion log** below.

- `cd packages/api && uv run pytest -m "not integration"` — 38 passed.
- `uv run ruff check src tests` — clean.
- `uv run mypy src` — clean (34 source files).
- `uv run mypy tests/integration` — clean (10 files).
- Integration tests (`@pytest.mark.integration`, 7 files) require `supabase start` from repo root; NOT run in the authoring sandbox. Verify locally before merging.

### Tomorrow — resuming from here

1. Optionally bring up the stack and run integration tests locally:
   ```bash
   supabase start                 # repo root, needs Docker
   cd packages/api
   export DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres
   export SUPABASE_URL=http://localhost:54321
   export SUPABASE_JWT_SECRET=super-secret-jwt-token-with-at-least-32-characters-long
   uv run pytest                  # runs both unit and integration
   ```
2. Review the 40-commit trail on `plan-2-api-core` (`git log --oneline main..plan-2-api-core`).
3. Merge to `main` (regular merge or squash) and push.
4. Optional: deploy to Render using `packages/api/Dockerfile` + `packages/api/render.yaml`, then `packages/api/scripts/smoke.sh <BASE_URL> <JWT>`.
5. Start Plan 3 (imports + PDF/XLSX exports) via the brainstorming → writing-plans → subagent-driven flow.

### Known follow-ups (flagged during review, not blocking)

- `src/api/db.py` — `pool.acquire()` has no timeout; add before production traffic. TODO comment in place.
- `src/api/errors.py` — `ValueError → 422 engine_validation_error` is a global catch; narrow to the `/calculate` call site once it's the only ValueError source.
- Python 3.11 vs 3.12: CI workflow only targets 3.11; consider matrix if supporting 3.12.

### Post-plan-completion log (live-test session, 2026-04-25)

After the plan was marked complete, the API was stood up against a hosted Supabase project. Live testing produced 4 additional commits.

**Real bugs found during live testing**:

1. `4cb8ca2` `_json_default` did not handle `UUID`. Audit-row serialisation crashed on every successful entity/property mutation. The unit test `test_uuid_isoformatted` had been *documenting* the gap (asserting `TypeError`); rewritten to assert `_json_default(uuid) == str(uuid)`.
2. `ae58afa` asyncpg returns `jsonb` columns as JSON-encoded `str` by default. The `/audit` endpoint blew up validating `before_json` / `after_json` because the Pydantic model expected `dict[str, Any]`. Registered a pool-level codec via `init=_init_connection` (in `db.py`) so jsonb / json columns return as Python dicts everywhere. The defensive `json.loads` fallback in `routers/snapshots.py::_row_to_schema` is now redundant but kept as a belt-and-braces guard.

**Usability features added during live testing**:

3. `e5d253d` `GET /` redirects to `/docs` (307). Hitting the bare URL in a browser now lands on Swagger UI instead of a `not_found` envelope.
4. `41b00d1` `bearerAuth` security scheme injected into the OpenAPI document via a custom `app.openapi` override. Swagger UI now renders the green "Authorize" button so a JWT can be pasted once and auto-attached to every "Try it out" call. `/` and `/healthz` declared explicitly public to keep the lock icons accurate.

**Operational notes from live setup (these tripped me up — flag for tomorrow)**:

- The hosted Supabase project (`lftvhwprprlgclhbxjqf`) uses the modern **JWT Signing Keys** + **Dedicated Pooler** stack. Two pitfalls:
  - The dedicated pooler is **IPv6-only by default**. Most home networks are IPv4-only — DNS appears to NXDOMAIN until you click **"Enable IPv4 add-on"** in Project Settings → Database → Connection pooling (paid).
  - The legacy `db.<ref>.supabase.co` host only resolves *after* the IPv4 add-on is enabled. We used that direct host successfully; the URL is `postgresql://postgres:<encoded-password>@db.lftvhwprprlgclhbxjqf.supabase.co:5432/postgres` (port 5432, asyncpg-compatible).
  - Password contains `@` → URL-encode as `%40`.
- Both auth modes work:
  - HS256 with the legacy JWT secret → set `SUPABASE_JWT_SECRET` in `.env`. Fast, tested by 39 unit tests.
  - JWKS (RS256/ES256) via `https://<SUPABASE_URL>/auth/v1/.well-known/jwks.json` → leave `SUPABASE_JWT_SECRET` unset; `verify_jwt` automatically uses the `PyJWKClient` initialised in lifespan. Live test ran on HS256; JWKS path was implemented but not exercised end-to-end.

### Real bugs caught by the review loop during this plan

1. Supabase CLI `jwt_secret` was unpinned — would silently desync from `.env.example` and 401 every integration test (fixed `f04b1c2`).
2. `SUPABASE_JWT_SECRET: str` leaked in `repr()` and `model_dump()` — switched to `SecretStr` (`ceec971`).
3. No JWT leeway → intermittent 401s under Docker/Windows clock skew — added 10s (`fddb644`).
4. `HTTPException(500)` produced `code="error"` — added 500/429/503 to status-code map (`f1f6b3f`).
5. `RequestValidationError` and `pydantic.ValidationError` were conflated in tests — renamed + added coverage for both.
6. Pydantic `gt=Decimal("0")` validator context broke JSON serialization in 422 responses — wrapped with `jsonable_encoder` in `errors.py`.
7. `tests/integration/conftest.py` imported `api.main` at module level, which forced `Settings()` construction at test-collection time — moved the import inside the `app` fixture (`08ae56c`).
8. Plan's `_mint_token` passed `SecretStr` object to `jwt.encode` — implementer caught and unwrapped via `.get_secret_value()`.

---

**Goal:** Ship `packages/api/` — a FastAPI service backed by Supabase Postgres that exposes the full CRUD surface for entities, properties, valuation snapshots, portfolio summaries, audit log, and users, with HS256 JWT auth, a two-role (valuer/viewer) permission model, an audited mutation trail, unit + integration tests, GitHub Actions CI, and Render deploy artifacts.

**Architecture:** `src/api/` is a FastAPI app factory pattern with narrow responsibilities per module: `schemas/` owns Pydantic request/response shapes, `queries/` owns async SQL via asyncpg (one file per table), `routers/` owns HTTP. `auth.py` is the only JWT verifier; `audit.py` is the only audit-row writer. Migrations are hand-written SQL in `supabase/migrations/`. Two test layers: fast unit tests (no DB) and `@pytest.mark.integration` tests against a live Supabase CLI local stack. No deploy is automated — Plan 2 produces Render deploy *artifacts* only.

**Tech Stack:** Python 3.11+, FastAPI 0.110+, asyncpg, Pydantic v2, pydantic-settings, PyJWT (HS256), uv, hatchling, pytest + pytest-asyncio + httpx, Supabase CLI (local Postgres + GoTrue), GitHub Actions.

**Spec reference:** [`docs/superpowers/specs/2026-04-24-api-core-design.md`](../specs/2026-04-24-api-core-design.md).

---

## File Structure

```text
property-valuations-model/
├── supabase/
│   ├── config.toml                               # NEW
│   └── migrations/                               # NEW
│       ├── 20260424000001_app_user.sql
│       ├── 20260424000002_entity.sql
│       ├── 20260424000003_property.sql
│       ├── 20260424000004_valuation_snapshot.sql
│       ├── 20260424000005_audit_log.sql
│       └── 20260424000006_rls_policies.sql
├── packages/api/                                 # NEW
│   ├── pyproject.toml
│   ├── README.md
│   ├── Dockerfile
│   ├── render.yaml
│   ├── .env.example
│   ├── src/api/
│   │   ├── __init__.py
│   │   ├── _version.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── auth.py
│   │   ├── audit.py
│   │   ├── errors.py
│   │   ├── logging.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── common.py
│   │   │   ├── entity.py
│   │   │   ├── property.py
│   │   │   ├── snapshot.py
│   │   │   ├── portfolio.py
│   │   │   ├── user.py
│   │   │   └── audit.py
│   │   ├── queries/
│   │   │   ├── __init__.py
│   │   │   ├── app_user.py
│   │   │   ├── entity.py
│   │   │   ├── property.py
│   │   │   ├── snapshot.py
│   │   │   ├── audit.py
│   │   │   └── portfolio.py
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── health.py
│   │       ├── me.py
│   │       ├── entities.py
│   │       ├── properties.py
│   │       ├── snapshots.py
│   │       ├── calculate.py
│   │       ├── portfolio.py
│   │       ├── users.py
│   │       └── audit.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── unit/
│   │   │   ├── __init__.py
│   │   │   ├── test_auth.py
│   │   │   ├── test_errors.py
│   │   │   ├── test_calculate_router.py
│   │   │   └── test_schemas.py
│   │   └── integration/
│   │       ├── __init__.py
│   │       ├── conftest.py
│   │       ├── test_health.py
│   │       ├── test_me.py
│   │       ├── test_entities.py
│   │       ├── test_properties.py
│   │       ├── test_snapshots.py
│   │       ├── test_portfolio.py
│   │       ├── test_audit.py
│   │       └── test_users.py
│   └── scripts/
│       └── smoke.sh
└── .github/workflows/api.yml                     # NEW
```

**Boundaries.**

- `schemas/` is pure data shape. No SQL, no asyncpg types.
- `queries/` is pure SQL. One file per table. Accepts an `asyncpg.Connection` or transaction, returns `asyncpg.Record` or domain dicts.
- `routers/` wires HTTP. Depends on `schemas/` and `queries/`; never writes SQL.
- `auth.py` is the sole JWT verifier. `audit.py` is the sole audit-row writer.
- `valuation_engine` is imported only in `routers/calculate.py` and `routers/snapshots.py`.

---

## Task 0: Directory Bootstrap & `supabase init`

**Files:**
- Create: `supabase/config.toml`
- Create: `packages/api/` directory tree
- Create: `packages/api/.env.example`
- Modify: `.gitignore` (add API-specific entries)

- [ ] **Step 1: Create directories**

From the project root:

```bash
mkdir -p packages/api/src/api/{schemas,queries,routers}
mkdir -p packages/api/tests/{unit,integration}
mkdir -p packages/api/scripts
mkdir -p supabase/migrations
mkdir -p .github/workflows
```

- [ ] **Step 2: Add API-specific entries to `.gitignore`**

Append to the existing `.gitignore` at the project root:

```gitignore

# API
packages/api/.venv/
packages/api/dist/
packages/api/build/
packages/api/*.egg-info/
packages/api/.env
packages/api/.ruff_cache/
packages/api/.mypy_cache/
packages/api/.pytest_cache/

# Supabase CLI
supabase/.branches/
supabase/.temp/
supabase/.env
```

- [ ] **Step 3: Write `supabase/config.toml`**

This is the minimum Supabase CLI config for local dev. Port 54321 = API gateway, 54322 = Postgres, 54323 = Studio.

```toml
project_id = "property-valuations-model"

[api]
enabled = true
port = 54321
schemas = ["public"]
extra_search_path = ["public", "extensions"]
max_rows = 1000

[db]
port = 54322
major_version = 15

[studio]
enabled = true
port = 54323

[auth]
enabled = true
site_url = "http://localhost:5173"
additional_redirect_urls = []
jwt_expiry = 3600
enable_signup = true

[auth.email]
enable_signup = true
enable_confirmations = false

# HS256 secret used for local dev. MUST match SUPABASE_JWT_SECRET in tests.
# This is the Supabase CLI default — do not use in production.
# Actual override done at runtime by `supabase start`.

[storage]
enabled = false

[realtime]
enabled = false

[edge_runtime]
enabled = false

[analytics]
enabled = false
```

- [ ] **Step 4: Write `packages/api/.env.example`**

```bash
# Copy to packages/api/.env and fill in local values.

# asyncpg DSN — default = Supabase CLI local postgres
DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres

# Supabase project URL — default = Supabase CLI local gateway
SUPABASE_URL=http://localhost:54321

# HS256 JWT secret — MUST match `supabase status` output locally,
# and the production value in Render for deploy.
# Supabase CLI default is shown for convenience.
SUPABASE_JWT_SECRET=super-secret-jwt-token-with-at-least-32-characters-long

# CORS — comma-separated list of allowed web origins
ALLOWED_ORIGINS=http://localhost:5173

# Application log level
LOG_LEVEL=INFO

# Environment — affects logging format and some defaults
ENV=dev
```

- [ ] **Step 5: Commit**

```bash
git add supabase/config.toml packages/api/.env.example .gitignore
git commit -m "chore(api): scaffold api/ dir tree + supabase config"
```

---

## Task 1: API Package Skeleton (pyproject, editable install)

**Files:**
- Create: `packages/api/pyproject.toml`
- Create: `packages/api/README.md`
- Create: `packages/api/src/api/__init__.py`
- Create: `packages/api/src/api/_version.py`
- Create: `packages/api/tests/__init__.py`
- Create: `packages/api/tests/conftest.py`
- Create: `packages/api/tests/unit/__init__.py`
- Create: `packages/api/tests/integration/__init__.py`

- [ ] **Step 1: Write `packages/api/src/api/_version.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 2: Write `packages/api/src/api/__init__.py`**

```python
from api._version import __version__

__all__ = ["__version__"]
```

- [ ] **Step 3: Write `packages/api/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "api"
description = "Property valuations API service."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "Proprietary" }
authors = [{ name = "Anchor Point Risk", email = "henry@anchorpointrisk.co.za" }]
dynamic = ["version"]
dependencies = [
    "fastapi>=0.110,<1",
    "uvicorn[standard]>=0.29,<1",
    "asyncpg>=0.29,<1",
    "pydantic>=2.6,<3",
    "pydantic-settings>=2,<3",
    "pyjwt[crypto]>=2.8,<3",
    "httpx>=0.27,<1",
    "python-json-logger>=2.0,<3",
    "valuation-engine>=0.1,<0.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5",
    "ruff>=0.5",
    "mypy>=1.10",
    "types-pyjwt",
]

[tool.uv.sources]
valuation-engine = { path = "../valuation_engine", editable = true }

[tool.hatch.version]
path = "src/api/_version.py"

[tool.hatch.build.targets.wheel]
packages = ["src/api"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM", "RET"]

[tool.mypy]
python_version = "3.11"
strict = true
plugins = ["pydantic.mypy"]
files = ["src/api"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
asyncio_mode = "auto"
markers = [
    "integration: requires a running Supabase CLI stack (slow)",
]
```

- [ ] **Step 4: Write `packages/api/README.md`**

````markdown
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
````

- [ ] **Step 5: Write empty `tests/__init__.py` and `tests/unit/__init__.py` and `tests/integration/__init__.py`**

All three files are empty (`""`).

- [ ] **Step 6: Write `packages/api/tests/conftest.py`**

```python
"""Shared pytest fixtures for the API test suite."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]


@pytest.fixture(scope="session")
def package_root() -> Path:
    return PACKAGE_ROOT


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guarantee deterministic env vars for unit tests.

    Integration tests override these in their own conftest.
    """
    monkeypatch.setenv("ENV", "ci")
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("SUPABASE_URL", "http://unused")
    monkeypatch.setenv(
        "SUPABASE_JWT_SECRET",
        "test-secret-minimum-32-chars-long-for-hs256-signing",
    )
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
```

- [ ] **Step 7: Install editable and verify**

```bash
cd packages/api
uv sync
uv run python -c "import api; print(api.__version__)"
```

Expected: `0.1.0`.

- [ ] **Step 8: Verify ruff + mypy pass on the empty package**

```bash
uv run ruff check src
uv run mypy src
```

Expected: both clean.

- [ ] **Step 9: Commit**

```bash
git add packages/api/pyproject.toml packages/api/README.md packages/api/src packages/api/tests
git commit -m "feat(api): scaffold api package (v0.1.0)"
```

---

## Task 2: Settings (`config.py`)

**Files:**
- Create: `packages/api/src/api/config.py`
- Create: `packages/api/tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/api/tests/unit/test_config.py
from __future__ import annotations

import pytest

from api.config import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "a" * 40)
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://a.test,http://b.test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENV", "prod")

    s = Settings()

    assert s.DATABASE_URL == "postgresql://u:p@h/d"
    assert s.SUPABASE_URL == "http://localhost:54321"
    assert s.SUPABASE_JWT_SECRET == "a" * 40
    assert s.allowed_origins_list == ["http://a.test", "http://b.test"]
    assert s.LOG_LEVEL == "DEBUG"
    assert s.ENV == "prod"


def test_settings_allowed_origins_empty_string_yields_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    s = Settings()
    assert s.allowed_origins_list == []


def test_settings_short_jwt_secret_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "short")
    with pytest.raises(ValueError):
        Settings()
```

- [ ] **Step 2: Run — should fail with ImportError**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: `ModuleNotFoundError: api.config`.

- [ ] **Step 3: Write `packages/api/src/api/config.py`**

```python
"""Application settings loaded from environment variables."""
from __future__ import annotations

from functools import cached_property
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_JWT_SECRET: str = Field(min_length=32)
    ALLOWED_ORIGINS: str = ""
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    ENV: Literal["dev", "ci", "prod"] = "dev"

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def _origins_no_internal_whitespace(cls, v: str) -> str:
        return v.strip()

    @cached_property
    def allowed_origins_list(self) -> list[str]:
        if not self.ALLOWED_ORIGINS:
            return []
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


def get_settings() -> Settings:
    """Factory. Called inside lifespan / dependencies; overridable in tests."""
    return Settings()
```

- [ ] **Step 4: Run tests — should pass**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/api/config.py packages/api/tests/unit/test_config.py
git commit -m "feat(api): add settings loader with env validation"
```

---

## Task 3: Structured Logging (`logging.py`)

**Files:**
- Create: `packages/api/src/api/logging.py`
- Create: `packages/api/tests/unit/test_logging.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/api/tests/unit/test_logging.py
from __future__ import annotations

import json
import logging

from api.logging import configure_logging


def test_configure_logging_emits_json(caplog, capsys) -> None:
    configure_logging(level="INFO", env="prod")
    log = logging.getLogger("api.test")
    log.info("hello", extra={"request_id": "abc"})

    captured = capsys.readouterr().out.strip().splitlines()
    assert captured, "expected JSON log line on stdout"
    payload = json.loads(captured[-1])
    assert payload["message"] == "hello"
    assert payload["request_id"] == "abc"
    assert payload["level"] == "INFO"


def test_configure_logging_dev_uses_plain_text(capsys) -> None:
    configure_logging(level="INFO", env="dev")
    log = logging.getLogger("api.test")
    log.info("plain")
    out = capsys.readouterr().out
    # Plain dev formatter is not strict JSON
    assert "plain" in out
```

- [ ] **Step 2: Run — should fail with ImportError**

```bash
uv run pytest tests/unit/test_logging.py -v
```

- [ ] **Step 3: Write `packages/api/src/api/logging.py`**

```python
"""Structured JSON logging for the API service."""
from __future__ import annotations

import logging
import sys
from typing import Literal

from pythonjsonlogger import jsonlogger


def configure_logging(*, level: str = "INFO", env: Literal["dev", "ci", "prod"] = "prod") -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    if env == "dev":
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
        )
    else:
        handler.setFormatter(
            jsonlogger.JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
            )
        )
    root.addHandler(handler)
    root.setLevel(level)
```

- [ ] **Step 4: Run tests — should pass**

```bash
uv run pytest tests/unit/test_logging.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/api/logging.py packages/api/tests/unit/test_logging.py
git commit -m "feat(api): add structured JSON logging"
```

---

## Task 4: Error Envelope (`errors.py`)

**Files:**
- Create: `packages/api/src/api/errors.py`
- Create: `packages/api/tests/unit/test_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/api/tests/unit/test_errors.py
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, ValidationError

from api.errors import (
    APIError,
    install_exception_handlers,
)


class _Body(BaseModel):
    name: str = Field(min_length=1)


def _app() -> FastAPI:
    app = FastAPI()
    install_exception_handlers(app)

    @app.post("/echo")
    def echo(body: _Body) -> dict[str, str]:
        return {"name": body.name}

    @app.get("/boom")
    def boom() -> None:
        raise APIError(status_code=409, code="has_live_children",
                       message="blocked", details={"blocking_count": 3})

    @app.get("/unexpected")
    def unexpected() -> None:
        raise RuntimeError("kaboom")

    @app.get("/not_found")
    def not_found() -> None:
        raise HTTPException(status_code=404)

    return app


def test_pydantic_validation_error_returns_422_envelope() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.post("/echo", json={"name": ""})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "invalid_input"
    assert isinstance(body["error"]["details"]["errors"], list)


def test_api_error_propagates_code_and_details() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 409
    assert r.json() == {
        "error": {
            "code": "has_live_children",
            "message": "blocked",
            "details": {"blocking_count": 3},
        }
    }


def test_unhandled_exception_returns_500_internal_error() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.get("/unexpected")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"


def test_http_exception_404_maps_to_not_found() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.get("/not_found")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
```

- [ ] **Step 2: Run — should fail with ImportError**

```bash
uv run pytest tests/unit/test_errors.py -v
```

- [ ] **Step 3: Write `packages/api/src/api/errors.py`**

```python
"""Unified error envelope. All API errors emit:
    {"error": {"code": str, "message": str, "details": dict | None}}
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class APIError(Exception):
    """Structured, user-facing API error."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


_STATUS_CODE_MAP: dict[int, tuple[str, str]] = {
    400: ("bad_request", "Bad request."),
    401: ("unauthorized", "Unauthorized."),
    403: ("forbidden", "Forbidden."),
    404: ("not_found", "Not found."),
    409: ("conflict", "Conflict."),
    410: ("gone", "Gone."),
    422: ("invalid_input", "Invalid input."),
}


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope("invalid_input", "Invalid input.", {"errors": exc.errors()}),
        )

    @app.exception_handler(ValidationError)
    async def _pydantic_validation(_request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope("invalid_input", "Invalid input.", {"errors": exc.errors()}),
        )

    @app.exception_handler(ValueError)
    async def _value_error(_request: Request, exc: ValueError) -> JSONResponse:
        # Engine ValueErrors surface as 422.
        return JSONResponse(
            status_code=422,
            content=_envelope("engine_validation_error", str(exc), {}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, default_msg = _STATUS_CODE_MAP.get(exc.status_code, ("error", "Error."))
        message = exc.detail if isinstance(exc.detail, str) else default_msg
        details: dict[str, Any] = {}
        if isinstance(exc.detail, dict):
            err = exc.detail.get("error")
            if isinstance(err, dict):
                code = str(err.get("code", code))
                message = str(err.get("message", message))
                raw_details = err.get("details") or {}
                if isinstance(raw_details, dict):
                    details = raw_details
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, message, details),
        )

    @app.exception_handler(HTTPException)
    async def _fastapi_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        return await _http_exception(request, exc)  # type: ignore[misc]

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_envelope("internal_error", "Internal server error.", {}),
        )
```

- [ ] **Step 4: Run tests — should pass**

```bash
uv run pytest tests/unit/test_errors.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/api/errors.py packages/api/tests/unit/test_errors.py
git commit -m "feat(api): add unified error envelope + exception handlers"
```

---

## Task 5: JWT Verification (`auth.py` part 1)

**Files:**
- Create: `packages/api/src/api/auth.py`
- Create: `packages/api/tests/unit/test_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/api/tests/unit/test_auth.py
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from api.auth import JWTClaims, verify_jwt
from api.errors import APIError

SECRET = "test-secret-minimum-32-chars-long-for-hs256-signing"


def _mint(**claims_override: object) -> str:
    now = datetime.now(tz=timezone.utc)
    claims: dict[str, object] = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "email": "alice@example.com",
        "aud": "authenticated",
        "role": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
    }
    claims.update(claims_override)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_verify_jwt_happy_path() -> None:
    token = _mint()
    c = verify_jwt(token, secret=SECRET)
    assert c.sub == "11111111-1111-1111-1111-111111111111"
    assert c.email == "alice@example.com"


def test_verify_jwt_expired_token_rejected() -> None:
    token = _mint(exp=int(time.time()) - 60)
    with pytest.raises(APIError) as ei:
        verify_jwt(token, secret=SECRET)
    assert ei.value.status_code == 401
    assert ei.value.code == "unauthorized"


def test_verify_jwt_wrong_signature_rejected() -> None:
    token = _mint()
    with pytest.raises(APIError):
        verify_jwt(token, secret="wrong-secret-" + "x" * 40)


def test_verify_jwt_wrong_audience_rejected() -> None:
    token = _mint(aud="anon")
    with pytest.raises(APIError):
        verify_jwt(token, secret=SECRET)


def test_verify_jwt_missing_sub_rejected() -> None:
    token = _mint()
    # Re-sign without sub
    token2 = jwt.encode(
        {"aud": "authenticated", "exp": int(time.time()) + 60, "email": "e@x.com"},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(APIError):
        verify_jwt(token2, secret=SECRET)


def test_jwt_claims_is_dataclass() -> None:
    c = JWTClaims(sub="s", email="e@x.com", aud="authenticated", raw={})
    assert c.email == "e@x.com"
```

- [ ] **Step 2: Run — should fail with ImportError**

```bash
uv run pytest tests/unit/test_auth.py -v
```

- [ ] **Step 3: Write initial `packages/api/src/api/auth.py`**

```python
"""JWT verification + auth dependencies.

Dependencies that talk to the DB (current_user, require_valuer) are added in
Task 11 once the `app_user` queries exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt

from api.errors import APIError


@dataclass(frozen=True, slots=True)
class JWTClaims:
    sub: str
    email: str | None
    aud: str
    raw: dict[str, Any]


def verify_jwt(token: str, *, secret: str) -> JWTClaims:
    """Decode and validate a Supabase-issued HS256 JWT.

    Raises APIError(401) on any failure.
    """
    try:
        payload = jwt.decode(
            token,
            key=secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["sub", "exp"]},
        )
    except jwt.InvalidTokenError as exc:
        raise APIError(
            status_code=401,
            code="unauthorized",
            message=f"Invalid token: {exc!s}",
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise APIError(status_code=401, code="unauthorized", message="Missing sub.")
    return JWTClaims(
        sub=str(sub),
        email=payload.get("email"),
        aud=str(payload.get("aud", "")),
        raw=payload,
    )
```

- [ ] **Step 4: Run tests — should pass**

```bash
uv run pytest tests/unit/test_auth.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/api/auth.py packages/api/tests/unit/test_auth.py
git commit -m "feat(api): verify Supabase HS256 JWTs"
```

---

## Task 6: DB Pool Lifecycle (`db.py`)

**Files:**
- Create: `packages/api/src/api/db.py`

> **Note:** `db.py` is intentionally thin. Its integration behavior is exercised by every integration test in later tasks. No dedicated unit test here — mocking asyncpg would be noise.

- [ ] **Step 1: Write `packages/api/src/api/db.py`**

```python
"""asyncpg pool lifecycle + per-request connection dependency."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import asyncpg
from fastapi import Request

if TYPE_CHECKING:
    from fastapi import FastAPI


async def _create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=10,
        command_timeout=30,
    )


@asynccontextmanager
async def lifespan_pool(app: "FastAPI", database_url: str) -> AsyncIterator[None]:
    pool = await _create_pool(database_url)
    app.state.pool = pool
    try:
        yield
    finally:
        await pool.close()


async def get_db(request: Request) -> AsyncIterator[asyncpg.Connection]:
    """FastAPI dependency: check out a connection for this request."""
    pool: asyncpg.Pool = request.app.state.pool
    async with pool.acquire() as conn:
        yield conn
```

- [ ] **Step 2: Ruff + mypy pass**

```bash
uv run ruff check src
uv run mypy src
```

- [ ] **Step 3: Commit**

```bash
git add packages/api/src/api/db.py
git commit -m "feat(api): add asyncpg pool lifecycle + get_db dependency"
```

---

## Task 7: Shared Pydantic Schemas (`schemas/common.py`, `schemas/user.py`)

**Files:**
- Create: `packages/api/src/api/schemas/__init__.py`
- Create: `packages/api/src/api/schemas/common.py`
- Create: `packages/api/src/api/schemas/user.py`
- Create: `packages/api/tests/unit/test_schemas.py`

- [ ] **Step 1: Write `schemas/__init__.py`**

```python
"""Pydantic request/response schemas.

Responses mirror DB rows. Requests are narrower and forbid unknown fields.
"""
```

- [ ] **Step 2: Write `schemas/common.py`**

```python
"""Shared base classes and helpers for API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class APIBase(BaseModel):
    """Base for all API request/response schemas.

    - extra='forbid' on requests catches typos early.
    - populate_by_name allows DB row -> schema construction by field name.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        arbitrary_types_allowed=False,
    )


class Timestamped(APIBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None = None


def nonempty_update(data: dict[str, Any]) -> dict[str, Any]:
    """Strip keys whose value is None. Used to build partial UPDATEs."""
    return {k: v for k, v in data.items() if v is not None}
```

- [ ] **Step 3: Write `schemas/user.py`**

```python
"""AppUser request/response shapes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from api.schemas.common import APIBase

Role = Literal["valuer", "viewer"]


class AppUser(APIBase):
    id: UUID
    email: str | None
    display_name: str | None
    role: Role
    created_at: datetime
    last_seen_at: datetime | None
```

- [ ] **Step 4: Write the failing test**

```python
# packages/api/tests/unit/test_schemas.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from api.schemas.common import nonempty_update
from api.schemas.user import AppUser


def test_nonempty_update_strips_none() -> None:
    assert nonempty_update({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}


def test_app_user_minimum_fields() -> None:
    u = AppUser(
        id=uuid4(),
        email="alice@example.com",
        display_name=None,
        role="viewer",
        created_at=datetime.now(tz=timezone.utc),
        last_seen_at=None,
    )
    assert u.role == "viewer"


def test_app_user_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AppUser(
            id=uuid4(),
            email="a@b.com",
            display_name=None,
            role="viewer",
            created_at=datetime.now(tz=timezone.utc),
            last_seen_at=None,
            extra_unknown_field=True,  # type: ignore[call-arg]
        )


def test_app_user_invalid_role_rejected() -> None:
    with pytest.raises(ValidationError):
        AppUser(
            id=uuid4(),
            email="a@b.com",
            display_name=None,
            role="admin",  # type: ignore[arg-type]
            created_at=datetime.now(tz=timezone.utc),
            last_seen_at=None,
        )
```

- [ ] **Step 5: Run tests — should pass**

```bash
uv run pytest tests/unit/test_schemas.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/api/src/api/schemas packages/api/tests/unit/test_schemas.py
git commit -m "feat(api): add shared schemas + AppUser"
```

---

## Task 8: Entity & Property Schemas

**Files:**
- Create: `packages/api/src/api/schemas/entity.py`
- Create: `packages/api/src/api/schemas/property.py`
- Modify: `packages/api/tests/unit/test_schemas.py`

- [ ] **Step 1: Write `schemas/entity.py`**

```python
"""Entity request/response shapes."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from api.schemas.common import APIBase


class EntityCreate(APIBase):
    name: str = Field(min_length=1, max_length=200)
    registration_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class EntityUpdate(APIBase):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    registration_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "EntityUpdate":
        if all(v is None for v in (self.name, self.registration_number, self.notes)):
            raise ValueError("PATCH body must contain at least one field")
        return self


class Entity(APIBase):
    id: UUID
    name: str
    registration_number: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None
```

- [ ] **Step 2: Write `schemas/property.py`**

```python
"""Property request/response shapes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from api.schemas.common import APIBase

PropertyType = Literal["office", "retail", "industrial", "mixed", "residential", "other"]


class PropertyCreate(APIBase):
    entity_id: UUID
    name: str = Field(min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    property_type: PropertyType = "other"
    notes: str | None = None


class PropertyUpdate(APIBase):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, max_length=500)
    property_type: PropertyType | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "PropertyUpdate":
        values = (self.name, self.address, self.property_type, self.notes)
        if all(v is None for v in values):
            raise ValueError("PATCH body must contain at least one field")
        return self


class Property(APIBase):
    id: UUID
    entity_id: UUID
    name: str
    address: str | None
    property_type: PropertyType
    notes: str | None
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None
```

- [ ] **Step 3: Append failing tests to `tests/unit/test_schemas.py`**

```python
# Append below existing tests

from api.schemas.entity import EntityCreate, EntityUpdate
from api.schemas.property import PropertyCreate, PropertyUpdate


def test_entity_create_happy() -> None:
    e = EntityCreate(name="Acme Pty", registration_number="2020/123456/07")
    assert e.name == "Acme Pty"


def test_entity_update_empty_rejected() -> None:
    with pytest.raises(ValidationError):
        EntityUpdate()


def test_entity_update_name_only_accepted() -> None:
    e = EntityUpdate(name="Acme (renamed)")
    assert e.name == "Acme (renamed)"


def test_property_create_defaults_to_other_type() -> None:
    p = PropertyCreate(entity_id=UUID(int=1), name="Building A")
    assert p.property_type == "other"


def test_property_update_empty_rejected() -> None:
    with pytest.raises(ValidationError):
        PropertyUpdate()
```

- [ ] **Step 4: Run tests — should pass**

```bash
uv run pytest tests/unit/test_schemas.py -v
```

Expected: all 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/api/schemas/entity.py packages/api/src/api/schemas/property.py packages/api/tests/unit/test_schemas.py
git commit -m "feat(api): add Entity/Property schemas with partial-update semantics"
```

---

## Task 9: Snapshot, Portfolio, Audit Schemas

**Files:**
- Create: `packages/api/src/api/schemas/snapshot.py`
- Create: `packages/api/src/api/schemas/portfolio.py`
- Create: `packages/api/src/api/schemas/audit.py`
- Modify: `packages/api/tests/unit/test_schemas.py`

- [ ] **Step 1: Write `schemas/snapshot.py`**

```python
"""ValuationSnapshot response shape.

Inputs are validated by the engine's own ValuationInput; the API does not
redefine it. The Snapshot response includes the frozen inputs_json and
result_json as dicts (not re-validated on read).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from api.schemas.common import APIBase

SnapshotStatus = Literal["active", "superseded"]
SnapshotSource = Literal["manual", "excel_import"]


class Snapshot(APIBase):
    id: UUID
    property_id: UUID
    valuation_date: date
    created_by: UUID
    created_at: datetime
    status: SnapshotStatus
    inputs_json: dict[str, Any]
    result_json: dict[str, Any]
    market_value: Decimal
    cap_rate: Decimal
    engine_version: str
    source: SnapshotSource
    source_file: str | None
```

- [ ] **Step 2: Write `schemas/portfolio.py`**

```python
"""Portfolio summary and timeseries response shapes."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from api.schemas.common import APIBase
from api.schemas.property import PropertyType


class ValueByType(APIBase):
    type: PropertyType
    value: Decimal
    count: int


class ValueByEntity(APIBase):
    entity_id: UUID
    name: str
    value: Decimal
    count: int


class TopProperty(APIBase):
    property_id: UUID
    name: str
    value: Decimal


class PortfolioSummary(APIBase):
    total_market_value: Decimal
    property_count: int
    entity_count: int
    last_snapshot_date: date | None
    value_by_type: list[ValueByType]
    value_by_entity: list[ValueByEntity]
    top_properties: list[TopProperty]


class TimeseriesPoint(APIBase):
    bucket_date: date
    total_market_value: Decimal
    property_count: int


class PortfolioTimeseries(APIBase):
    bucket: str
    points: list[TimeseriesPoint]
```

- [ ] **Step 3: Write `schemas/audit.py`**

```python
"""Audit-log response shapes."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from api.schemas.common import APIBase

AuditAction = Literal["create", "update", "soft_delete"]
AuditTargetTable = Literal["entity", "property", "valuation_snapshot", "app_user"]


class AuditEntry(APIBase):
    id: UUID
    actor_id: UUID
    actor_email: str | None
    action: AuditAction
    target_table: AuditTargetTable
    target_id: UUID
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    created_at: datetime


class AuditPage(APIBase):
    items: list[AuditEntry]
    total: int
    limit: int
    offset: int
```

- [ ] **Step 4: Append round-trip test to `test_schemas.py`**

```python
# Append at bottom

from datetime import date
from decimal import Decimal

from api.schemas.audit import AuditEntry, AuditPage
from api.schemas.portfolio import (
    PortfolioSummary,
    TimeseriesPoint,
    TopProperty,
    ValueByEntity,
    ValueByType,
)
from api.schemas.snapshot import Snapshot


def test_snapshot_round_trip_json() -> None:
    s = Snapshot(
        id=UUID(int=1),
        property_id=UUID(int=2),
        valuation_date=date(2026, 1, 1),
        created_by=UUID(int=3),
        created_at=datetime.now(tz=timezone.utc),
        status="active",
        inputs_json={},
        result_json={},
        market_value=Decimal("1000000"),
        cap_rate=Decimal("0.11"),
        engine_version="0.1.0",
        source="manual",
        source_file=None,
    )
    again = Snapshot.model_validate_json(s.model_dump_json())
    assert again == s


def test_portfolio_summary_construction() -> None:
    summary = PortfolioSummary(
        total_market_value=Decimal("5000000"),
        property_count=3,
        entity_count=2,
        last_snapshot_date=date(2026, 4, 1),
        value_by_type=[ValueByType(type="office", value=Decimal("3000000"), count=2)],
        value_by_entity=[
            ValueByEntity(entity_id=UUID(int=1), name="E", value=Decimal("5000000"), count=3)
        ],
        top_properties=[TopProperty(property_id=UUID(int=2), name="P", value=Decimal("2000000"))],
    )
    assert summary.property_count == 3


def test_audit_page_construction() -> None:
    p = AuditPage(
        items=[
            AuditEntry(
                id=UUID(int=1),
                actor_id=UUID(int=2),
                actor_email="a@b.com",
                action="create",
                target_table="entity",
                target_id=UUID(int=3),
                before_json=None,
                after_json={"name": "Acme"},
                created_at=datetime.now(tz=timezone.utc),
            )
        ],
        total=1,
        limit=50,
        offset=0,
    )
    assert p.total == 1


def test_timeseries_point_dates() -> None:
    tp = TimeseriesPoint(
        bucket_date=date(2025, 1, 1),
        total_market_value=Decimal("1000"),
        property_count=1,
    )
    assert tp.bucket_date.year == 2025
```

- [ ] **Step 5: Run tests — should pass**

```bash
uv run pytest tests/unit/test_schemas.py -v
```

Expected: all 13 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/api/src/api/schemas packages/api/tests/unit/test_schemas.py
git commit -m "feat(api): add snapshot, portfolio, audit schemas"
```

---

## Task 10: SQL Migration — `app_user` Table

**Files:**
- Create: `supabase/migrations/20260424000001_app_user.sql`

- [ ] **Step 1: Write the migration**

```sql
-- 20260424000001_app_user.sql
-- app_user mirrors auth.users with a role. id equals auth.uid().
create extension if not exists "pgcrypto";

create table public.app_user (
    id uuid primary key,
    email text,
    display_name text,
    role text not null default 'viewer' check (role in ('valuer', 'viewer')),
    created_at timestamptz not null default now(),
    last_seen_at timestamptz
);

create index app_user_email_idx on public.app_user (email);

alter table public.app_user enable row level security;

comment on table public.app_user is
  'User mirror table with in-app role. Rows created by the API on first authed request.';
```

- [ ] **Step 2: Apply locally**

```bash
# From repo root, with Docker running:
supabase db reset
```

Expected: the reset prints the migration filename and succeeds. `psql` into `localhost:54322` and verify `\d app_user`.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260424000001_app_user.sql
git commit -m "feat(db): add app_user table migration"
```

---

## Task 11: SQL Migrations — entity, property, valuation_snapshot, audit_log

**Files:**
- Create: `supabase/migrations/20260424000002_entity.sql`
- Create: `supabase/migrations/20260424000003_property.sql`
- Create: `supabase/migrations/20260424000004_valuation_snapshot.sql`
- Create: `supabase/migrations/20260424000005_audit_log.sql`

- [ ] **Step 1: Write `20260424000002_entity.sql`**

```sql
create table public.entity (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    registration_number text,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz,
    deleted_at timestamptz
);

create index entity_name_idx on public.entity (name);
create index entity_live_idx on public.entity (deleted_at) where deleted_at is null;

alter table public.entity enable row level security;
```

- [ ] **Step 2: Write `20260424000003_property.sql`**

```sql
create type public.property_type as enum (
    'office', 'retail', 'industrial', 'mixed', 'residential', 'other'
);

create table public.property (
    id uuid primary key default gen_random_uuid(),
    entity_id uuid not null references public.entity(id),
    name text not null,
    address text,
    property_type public.property_type not null default 'other',
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz,
    deleted_at timestamptz
);

create index property_entity_idx on public.property (entity_id);
create index property_live_idx on public.property (deleted_at) where deleted_at is null;
create index property_type_idx on public.property (property_type);

alter table public.property enable row level security;
```

- [ ] **Step 3: Write `20260424000004_valuation_snapshot.sql`**

```sql
create type public.snapshot_status as enum ('active', 'superseded');
create type public.snapshot_source as enum ('manual', 'excel_import');

create table public.valuation_snapshot (
    id uuid primary key default gen_random_uuid(),
    property_id uuid not null references public.property(id),
    valuation_date date not null,
    created_by uuid not null references public.app_user(id),
    created_at timestamptz not null default now(),
    status public.snapshot_status not null default 'active',
    inputs_json jsonb not null,
    result_json jsonb not null,
    market_value numeric(20,4) not null,
    cap_rate numeric(10,6) not null,
    engine_version text not null,
    source public.snapshot_source not null default 'manual',
    source_file text
);

create index snapshot_property_idx
    on public.valuation_snapshot (property_id, valuation_date desc);
create index snapshot_active_idx
    on public.valuation_snapshot (property_id)
    where status = 'active';
create index snapshot_created_at_idx
    on public.valuation_snapshot (created_at desc);

alter table public.valuation_snapshot enable row level security;
```

- [ ] **Step 4: Write `20260424000005_audit_log.sql`**

```sql
create type public.audit_action as enum ('create', 'update', 'soft_delete');
create type public.audit_target_table as enum (
    'entity', 'property', 'valuation_snapshot', 'app_user'
);

create table public.audit_log (
    id uuid primary key default gen_random_uuid(),
    actor_id uuid not null references public.app_user(id),
    actor_email text,
    action public.audit_action not null,
    target_table public.audit_target_table not null,
    target_id uuid not null,
    before_json jsonb,
    after_json jsonb,
    created_at timestamptz not null default now()
);

create index audit_created_at_idx on public.audit_log (created_at desc);
create index audit_target_idx on public.audit_log (target_table, target_id);
create index audit_actor_idx on public.audit_log (actor_id);

alter table public.audit_log enable row level security;
```

- [ ] **Step 5: Apply locally**

```bash
supabase db reset
```

Expected: all 5 migrations run clean.

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/20260424000002_entity.sql supabase/migrations/20260424000003_property.sql supabase/migrations/20260424000004_valuation_snapshot.sql supabase/migrations/20260424000005_audit_log.sql
git commit -m "feat(db): add entity, property, snapshot, audit migrations"
```

---

## Task 12: RLS Policies Migration

**Files:**
- Create: `supabase/migrations/20260424000006_rls_policies.sql`

- [ ] **Step 1: Write the migration**

```sql
-- 20260424000006_rls_policies.sql
-- RLS policies. The API connects as service-role which bypasses these,
-- so they primarily exist for forward-compat if any client ever connects
-- with a user JWT directly.

-- Helper: is_valuer() reads role from app_user for auth.uid().
create or replace function public.is_valuer() returns boolean
language sql stable as $$
    select exists (
        select 1 from public.app_user
        where id = auth.uid() and role = 'valuer'
    );
$$;

-- app_user: user can read their own row only
create policy "app_user_self_select" on public.app_user
    for select to authenticated
    using (id = auth.uid());

-- entity
create policy "entity_select_all_auth" on public.entity
    for select to authenticated using (true);

create policy "entity_insert_valuer" on public.entity
    for insert to authenticated with check (public.is_valuer());

create policy "entity_update_valuer" on public.entity
    for update to authenticated using (public.is_valuer());

-- property
create policy "property_select_all_auth" on public.property
    for select to authenticated using (true);

create policy "property_insert_valuer" on public.property
    for insert to authenticated with check (public.is_valuer());

create policy "property_update_valuer" on public.property
    for update to authenticated using (public.is_valuer());

-- valuation_snapshot: select for all auth; insert for valuer; never update/delete
create policy "snapshot_select_all_auth" on public.valuation_snapshot
    for select to authenticated using (true);

create policy "snapshot_insert_valuer" on public.valuation_snapshot
    for insert to authenticated with check (public.is_valuer());

-- audit_log: select for authenticated; writes only via service_role
create policy "audit_select_all_auth" on public.audit_log
    for select to authenticated using (true);
```

- [ ] **Step 2: Apply locally**

```bash
supabase db reset
```

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260424000006_rls_policies.sql
git commit -m "feat(db): add RLS policies for two-role access"
```

---

## Task 13: `queries/app_user.py`

**Files:**
- Create: `packages/api/src/api/queries/__init__.py`
- Create: `packages/api/src/api/queries/app_user.py`

- [ ] **Step 1: Write empty `queries/__init__.py`**

```python
"""asyncpg query layer. One file per table."""
```

- [ ] **Step 2: Write `queries/app_user.py`**

```python
"""Query functions for app_user."""
from __future__ import annotations

from typing import cast
from uuid import UUID

import asyncpg

_COLS = "id, email, display_name, role, created_at, last_seen_at"


async def upsert_from_claims(
    conn: asyncpg.Connection,
    *,
    auth_uid: UUID,
    email: str | None,
) -> asyncpg.Record:
    """Create the user row on first sight; always bump last_seen_at.

    Default role is 'viewer' on first insert. Returns the post-update row.
    """
    row = await conn.fetchrow(
        f"""
        insert into public.app_user (id, email, role, last_seen_at)
        values ($1, $2, 'viewer', now())
        on conflict (id) do update
            set last_seen_at = excluded.last_seen_at,
                email = coalesce(excluded.email, public.app_user.email)
        returning {_COLS}
        """,
        auth_uid,
        email,
    )
    return cast("asyncpg.Record", row)


async def list_users(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    rows = await conn.fetch(
        f"select {_COLS} from public.app_user order by created_at asc"
    )
    return list(rows)


async def get_user(conn: asyncpg.Connection, user_id: UUID) -> asyncpg.Record | None:
    row = await conn.fetchrow(
        f"select {_COLS} from public.app_user where id = $1",
        user_id,
    )
    return row
```

- [ ] **Step 3: Commit**

```bash
git add packages/api/src/api/queries/__init__.py packages/api/src/api/queries/app_user.py
git commit -m "feat(api): add app_user queries"
```

---

## Task 14: `queries/entity.py`

**Files:**
- Create: `packages/api/src/api/queries/entity.py`

- [ ] **Step 1: Write the module**

```python
"""Query functions for entity."""
from __future__ import annotations

from typing import Any, cast
from uuid import UUID

import asyncpg

_COLS = "id, name, registration_number, notes, created_at, updated_at, deleted_at"

_UPDATABLE = ("name", "registration_number", "notes")


async def list_entities(
    conn: asyncpg.Connection, *, include_deleted: bool = False
) -> list[asyncpg.Record]:
    where = "" if include_deleted else "where deleted_at is null"
    rows = await conn.fetch(
        f"select {_COLS} from public.entity {where} order by name asc"
    )
    return list(rows)


async def get_entity(
    conn: asyncpg.Connection, entity_id: UUID, *, include_deleted: bool = False
) -> asyncpg.Record | None:
    extra = "" if include_deleted else "and deleted_at is null"
    row = await conn.fetchrow(
        f"select {_COLS} from public.entity where id = $1 {extra}",
        entity_id,
    )
    return row


async def insert_entity(
    conn: asyncpg.Connection,
    *,
    name: str,
    registration_number: str | None,
    notes: str | None,
) -> asyncpg.Record:
    row = await conn.fetchrow(
        f"""
        insert into public.entity (name, registration_number, notes)
        values ($1, $2, $3)
        returning {_COLS}
        """,
        name, registration_number, notes,
    )
    return cast("asyncpg.Record", row)


async def update_entity(
    conn: asyncpg.Connection, entity_id: UUID, patch: dict[str, Any]
) -> asyncpg.Record | None:
    patch = {k: v for k, v in patch.items() if k in _UPDATABLE}
    if not patch:
        return await get_entity(conn, entity_id)

    set_clauses = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(patch))
    values = list(patch.values())
    row = await conn.fetchrow(
        f"""
        update public.entity
           set {set_clauses}, updated_at = now()
         where id = $1 and deleted_at is null
         returning {_COLS}
        """,
        entity_id, *values,
    )
    return row


async def soft_delete_entity(
    conn: asyncpg.Connection, entity_id: UUID
) -> asyncpg.Record | None:
    row = await conn.fetchrow(
        f"""
        update public.entity set deleted_at = now()
         where id = $1 and deleted_at is null
         returning {_COLS}
        """,
        entity_id,
    )
    return row


async def count_live_properties(conn: asyncpg.Connection, entity_id: UUID) -> int:
    row = await conn.fetchrow(
        "select count(*)::int as c from public.property "
        "where entity_id = $1 and deleted_at is null",
        entity_id,
    )
    assert row is not None
    return int(row["c"])
```

- [ ] **Step 2: Commit**

```bash
git add packages/api/src/api/queries/entity.py
git commit -m "feat(api): add entity queries"
```

---

## Task 15: `queries/property.py`

**Files:**
- Create: `packages/api/src/api/queries/property.py`

- [ ] **Step 1: Write the module**

```python
"""Query functions for property."""
from __future__ import annotations

from typing import Any, cast
from uuid import UUID

import asyncpg

_COLS = (
    "id, entity_id, name, address, property_type, notes, "
    "created_at, updated_at, deleted_at"
)

_UPDATABLE = ("name", "address", "property_type", "notes")


async def list_properties(
    conn: asyncpg.Connection,
    *,
    entity_id: UUID | None = None,
    property_type: str | None = None,
    include_deleted: bool = False,
) -> list[asyncpg.Record]:
    clauses: list[str] = []
    params: list[Any] = []
    if not include_deleted:
        clauses.append("deleted_at is null")
    if entity_id is not None:
        params.append(entity_id)
        clauses.append(f"entity_id = ${len(params)}")
    if property_type is not None:
        params.append(property_type)
        clauses.append(f"property_type = ${len(params)}")

    where = f"where {' and '.join(clauses)}" if clauses else ""
    rows = await conn.fetch(
        f"select {_COLS} from public.property {where} order by name asc",
        *params,
    )
    return list(rows)


async def get_property(
    conn: asyncpg.Connection, property_id: UUID, *, include_deleted: bool = False
) -> asyncpg.Record | None:
    extra = "" if include_deleted else "and deleted_at is null"
    row = await conn.fetchrow(
        f"select {_COLS} from public.property where id = $1 {extra}",
        property_id,
    )
    return row


async def insert_property(
    conn: asyncpg.Connection,
    *,
    entity_id: UUID,
    name: str,
    address: str | None,
    property_type: str,
    notes: str | None,
) -> asyncpg.Record:
    row = await conn.fetchrow(
        f"""
        insert into public.property
            (entity_id, name, address, property_type, notes)
        values ($1, $2, $3, $4::public.property_type, $5)
        returning {_COLS}
        """,
        entity_id, name, address, property_type, notes,
    )
    return cast("asyncpg.Record", row)


async def update_property(
    conn: asyncpg.Connection, property_id: UUID, patch: dict[str, Any]
) -> asyncpg.Record | None:
    patch = {k: v for k, v in patch.items() if k in _UPDATABLE}
    if not patch:
        return await get_property(conn, property_id)

    set_parts: list[str] = []
    values: list[Any] = []
    for k, v in patch.items():
        values.append(v)
        if k == "property_type":
            set_parts.append(f"{k} = ${len(values) + 1}::public.property_type")
        else:
            set_parts.append(f"{k} = ${len(values) + 1}")

    row = await conn.fetchrow(
        f"""
        update public.property
           set {", ".join(set_parts)}, updated_at = now()
         where id = $1 and deleted_at is null
         returning {_COLS}
        """,
        property_id, *values,
    )
    return row


async def soft_delete_property(
    conn: asyncpg.Connection, property_id: UUID
) -> asyncpg.Record | None:
    row = await conn.fetchrow(
        f"""
        update public.property set deleted_at = now()
         where id = $1 and deleted_at is null
         returning {_COLS}
        """,
        property_id,
    )
    return row


async def count_active_snapshots(conn: asyncpg.Connection, property_id: UUID) -> int:
    row = await conn.fetchrow(
        "select count(*)::int as c from public.valuation_snapshot "
        "where property_id = $1 and status = 'active'",
        property_id,
    )
    assert row is not None
    return int(row["c"])
```

- [ ] **Step 2: Commit**

```bash
git add packages/api/src/api/queries/property.py
git commit -m "feat(api): add property queries"
```

---

## Task 16: `queries/snapshot.py`

**Files:**
- Create: `packages/api/src/api/queries/snapshot.py`

- [ ] **Step 1: Write the module**

```python
"""Query functions for valuation_snapshot."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import asyncpg

_COLS = (
    "id, property_id, valuation_date, created_by, created_at, status, "
    "inputs_json, result_json, market_value, cap_rate, engine_version, "
    "source, source_file"
)


async def list_for_property(
    conn: asyncpg.Connection, property_id: UUID
) -> list[asyncpg.Record]:
    rows = await conn.fetch(
        f"""
        select {_COLS} from public.valuation_snapshot
         where property_id = $1
         order by valuation_date desc, created_at desc
        """,
        property_id,
    )
    return list(rows)


async def get_snapshot(
    conn: asyncpg.Connection, snapshot_id: UUID
) -> asyncpg.Record | None:
    row = await conn.fetchrow(
        f"select {_COLS} from public.valuation_snapshot where id = $1",
        snapshot_id,
    )
    return row


async def supersede_active(
    tx: asyncpg.Connection, property_id: UUID
) -> int:
    """Flip all currently-active snapshots for a property to superseded."""
    result = await tx.execute(
        """
        update public.valuation_snapshot
           set status = 'superseded'
         where property_id = $1 and status = 'active'
        """,
        property_id,
    )
    # `UPDATE N` → last token is row count
    return int(result.split()[-1])


async def insert_snapshot(
    tx: asyncpg.Connection,
    *,
    property_id: UUID,
    valuation_date: date,
    created_by: UUID,
    inputs_json: dict[str, Any],
    result_json: dict[str, Any],
    market_value: Decimal,
    cap_rate: Decimal,
    engine_version: str,
    source: str,
    source_file: str | None,
) -> asyncpg.Record:
    row = await tx.fetchrow(
        f"""
        insert into public.valuation_snapshot
            (property_id, valuation_date, created_by, status,
             inputs_json, result_json, market_value, cap_rate,
             engine_version, source, source_file)
        values ($1, $2, $3, 'active', $4::jsonb, $5::jsonb, $6, $7,
                $8, $9::public.snapshot_source, $10)
        returning {_COLS}
        """,
        property_id,
        valuation_date,
        created_by,
        json.dumps(inputs_json, default=_json_default),
        json.dumps(result_json, default=_json_default),
        market_value,
        cap_rate,
        engine_version,
        source,
        source_file,
    )
    return cast("asyncpg.Record", row)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Not JSON-serializable: {type(value).__name__}")
```

- [ ] **Step 2: Commit**

```bash
git add packages/api/src/api/queries/snapshot.py
git commit -m "feat(api): add valuation_snapshot queries (supersede + insert)"
```

---

## Task 17: `queries/audit.py` + `audit.py` Helper

**Files:**
- Create: `packages/api/src/api/queries/audit.py`
- Create: `packages/api/src/api/audit.py`
- Create: `packages/api/tests/unit/test_audit.py`

- [ ] **Step 1: Write `queries/audit.py`**

```python
"""Query functions for audit_log."""
from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

_COLS = (
    "id, actor_id, actor_email, action, target_table, target_id, "
    "before_json, after_json, created_at"
)


async def list_audit(
    conn: asyncpg.Connection,
    *,
    limit: int = 50,
    offset: int = 0,
    target_table: str | None = None,
    actor_id: UUID | None = None,
) -> tuple[list[asyncpg.Record], int]:
    clauses: list[str] = []
    params: list[Any] = []
    if target_table is not None:
        params.append(target_table)
        clauses.append(f"target_table = ${len(params)}::public.audit_target_table")
    if actor_id is not None:
        params.append(actor_id)
        clauses.append(f"actor_id = ${len(params)}")

    where = f"where {' and '.join(clauses)}" if clauses else ""

    total_row = await conn.fetchrow(
        f"select count(*)::int as c from public.audit_log {where}",
        *params,
    )
    assert total_row is not None
    total = int(total_row["c"])

    params_with_paging = [*params, limit, offset]
    rows = await conn.fetch(
        f"""
        select {_COLS} from public.audit_log {where}
         order by created_at desc
         limit ${len(params) + 1} offset ${len(params) + 2}
        """,
        *params_with_paging,
    )
    return list(rows), total
```

- [ ] **Step 2: Write `audit.py` helper**

```python
"""Audit-log helper. Called inside the same transaction as every mutation."""
from __future__ import annotations

import json
from typing import Any, Literal
from uuid import UUID

import asyncpg

from api.queries.snapshot import _json_default as _json_default  # reuse


async def audit(
    tx: asyncpg.Connection,
    *,
    actor_id: UUID,
    actor_email: str | None,
    action: Literal["create", "update", "soft_delete"],
    target_table: Literal["entity", "property", "valuation_snapshot", "app_user"],
    target_id: UUID,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    await tx.execute(
        """
        insert into public.audit_log
            (actor_id, actor_email, action, target_table, target_id,
             before_json, after_json)
        values ($1, $2, $3::public.audit_action,
                $4::public.audit_target_table, $5, $6::jsonb, $7::jsonb)
        """,
        actor_id,
        actor_email,
        action,
        target_table,
        target_id,
        json.dumps(before, default=_json_default) if before is not None else None,
        json.dumps(after, default=_json_default) if after is not None else None,
    )


def record_to_json(record: asyncpg.Record) -> dict[str, Any]:
    """Convert a Record to a plain dict suitable for audit before/after."""
    return dict(record)
```

- [ ] **Step 3: Write a unit test for the JSON serializer**

```python
# packages/api/tests/unit/test_audit.py
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from api.queries.snapshot import _json_default


def test_decimal_stringified() -> None:
    assert _json_default(Decimal("1.23")) == "1.23"


def test_date_isoformatted() -> None:
    assert _json_default(date(2026, 1, 2)) == "2026-01-02"


def test_datetime_isoformatted() -> None:
    out = _json_default(datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
    assert out.startswith("2026-01-02T03:04:05")


def test_uuid_isoformatted() -> None:
    u = uuid4()
    # UUID has .isoformat? No — hasattr isoformat is False for UUID.
    # Our default raises TypeError on non-supported; ensure str(uuid) path via json.dumps.
    # We accept a TypeError here — json.dumps UUIDs via `default=str` in callers.
    import pytest

    with pytest.raises(TypeError):
        _json_default(u)
```

- [ ] **Step 4: Run tests — should pass**

```bash
uv run pytest tests/unit/test_audit.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/api/queries/audit.py packages/api/src/api/audit.py packages/api/tests/unit/test_audit.py
git commit -m "feat(api): add audit queries and audit() helper"
```

---

## Task 18: `queries/portfolio.py`

**Files:**
- Create: `packages/api/src/api/queries/portfolio.py`

- [ ] **Step 1: Write the module**

```python
"""Portfolio analytical queries. Latest-snapshot-per-property is the key CTE."""
from __future__ import annotations

import asyncpg

_LATEST_CTE = """
with latest as (
    select distinct on (s.property_id)
        s.property_id, s.market_value, s.valuation_date
    from public.valuation_snapshot s
    join public.property p on p.id = s.property_id and p.deleted_at is null
    join public.entity e on e.id = p.entity_id and e.deleted_at is null
    where s.status = 'active'
    order by s.property_id, s.valuation_date desc, s.created_at desc
)
"""


async def summary(
    conn: asyncpg.Connection, *, top_limit: int = 10
) -> dict[str, object]:
    totals = await conn.fetchrow(
        _LATEST_CTE
        + """
        select
            coalesce(sum(latest.market_value), 0) as total_market_value,
            count(*)::int as property_count,
            (select count(*)::int from public.entity where deleted_at is null) as entity_count,
            max(latest.valuation_date) as last_snapshot_date
        from latest
        """
    )

    by_type = await conn.fetch(
        _LATEST_CTE
        + """
        select p.property_type as type,
               coalesce(sum(latest.market_value), 0) as value,
               count(*)::int as count
        from latest
        join public.property p on p.id = latest.property_id
        group by p.property_type
        order by value desc
        """
    )

    by_entity = await conn.fetch(
        _LATEST_CTE
        + """
        select e.id as entity_id,
               e.name as name,
               coalesce(sum(latest.market_value), 0) as value,
               count(*)::int as count
        from latest
        join public.property p on p.id = latest.property_id
        join public.entity e on e.id = p.entity_id
        group by e.id, e.name
        order by value desc
        """
    )

    top_props = await conn.fetch(
        _LATEST_CTE
        + """
        select p.id as property_id, p.name as name, latest.market_value as value
        from latest
        join public.property p on p.id = latest.property_id
        order by latest.market_value desc
        limit $1
        """,
        top_limit,
    )

    assert totals is not None
    return {
        "total_market_value": totals["total_market_value"],
        "property_count": totals["property_count"],
        "entity_count": totals["entity_count"],
        "last_snapshot_date": totals["last_snapshot_date"],
        "value_by_type": [dict(r) for r in by_type],
        "value_by_entity": [dict(r) for r in by_entity],
        "top_properties": [dict(r) for r in top_props],
    }


async def timeseries_year(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    rows = await conn.fetch(
        """
        with active as (
            select distinct on (s.property_id, date_trunc('year', s.valuation_date))
                s.property_id,
                date_trunc('year', s.valuation_date)::date as bucket_date,
                s.market_value
            from public.valuation_snapshot s
            join public.property p on p.id = s.property_id and p.deleted_at is null
            order by s.property_id, date_trunc('year', s.valuation_date),
                     s.valuation_date desc, s.created_at desc
        )
        select bucket_date,
               coalesce(sum(market_value), 0) as total_market_value,
               count(*)::int as property_count
        from active
        group by bucket_date
        order by bucket_date asc
        """
    )
    return list(rows)
```

- [ ] **Step 2: Commit**

```bash
git add packages/api/src/api/queries/portfolio.py
git commit -m "feat(api): add portfolio summary + timeseries queries"
```

---

## Task 19: Auth Dependencies (`current_user`, `require_valuer`)

**Files:**
- Modify: `packages/api/src/api/auth.py`

- [ ] **Step 1: Append to `auth.py`**

```python
# Append to src/api/auth.py

from typing import Annotated

import asyncpg
from fastapi import Depends, Request

from api.config import Settings, get_settings
from api.db import get_db
from api.queries import app_user as q_app_user
from api.schemas.user import AppUser


def _extract_bearer(request: Request) -> str:
    authz = request.headers.get("Authorization") or request.headers.get("authorization")
    if not authz or not authz.lower().startswith("bearer "):
        raise APIError(
            status_code=401, code="missing_token",
            message="Missing or malformed Authorization header.",
        )
    return authz.split(" ", 1)[1].strip()


async def current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> AppUser:
    token = _extract_bearer(request)
    claims = verify_jwt(token, secret=settings.SUPABASE_JWT_SECRET)
    from uuid import UUID
    row = await q_app_user.upsert_from_claims(
        conn,
        auth_uid=UUID(claims.sub),
        email=claims.email,
    )
    user = AppUser.model_validate(dict(row))
    request.state.user = user
    return user


async def require_valuer(
    user: Annotated[AppUser, Depends(current_user)],
) -> AppUser:
    if user.role != "valuer":
        raise APIError(
            status_code=403, code="forbidden",
            message="Valuer role required.",
        )
    return user
```

- [ ] **Step 2: Ruff + mypy pass**

```bash
uv run ruff check src
uv run mypy src
```

- [ ] **Step 3: Commit**

```bash
git add packages/api/src/api/auth.py
git commit -m "feat(api): add current_user + require_valuer dependencies"
```

---

## Task 20: FastAPI App Factory (`main.py`)

**Files:**
- Create: `packages/api/src/api/main.py`
- Create: `packages/api/src/api/routers/__init__.py`
- Create: `packages/api/src/api/routers/health.py`

- [ ] **Step 1: Write `routers/__init__.py`**

```python
"""HTTP routers. Composed by main.py."""
```

- [ ] **Step 2: Write `routers/health.py`**

```python
"""Liveness endpoint. No auth, no DB."""
from __future__ import annotations

from fastapi import APIRouter

from api._version import __version__ as api_version

try:
    from valuation_engine import __version__ as engine_version
except ImportError:  # pragma: no cover
    engine_version = "unknown"


router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "api_version": api_version,
        "engine_version": engine_version,
    }
```

- [ ] **Step 3: Write `main.py`**

```python
"""FastAPI application factory."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api._version import __version__
from api.config import Settings, get_settings
from api.db import lifespan_pool
from api.errors import install_exception_handlers
from api.logging import configure_logging
from api.routers import health as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.LOG_LEVEL, env=settings.ENV)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with lifespan_pool(app, settings.DATABASE_URL):
            yield

    app = FastAPI(
        title="property-valuations-model API",
        version=__version__,
        lifespan=lifespan,
    )

    if settings.allowed_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    install_exception_handlers(app)
    app.dependency_overrides[get_settings] = lambda: settings

    app.include_router(health_router.router)
    return app


app = create_app()
```

- [ ] **Step 4: Smoke-run in a terminal (optional, Docker-less if `DATABASE_URL` points nowhere — connection only opens on first DB-touching request)**

```bash
uv run uvicorn api.main:app --port 8001 &
curl -sS http://localhost:8001/healthz
# Expected JSON {"status":"ok", ...}
kill %1
```

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/api/main.py packages/api/src/api/routers
git commit -m "feat(api): add FastAPI app factory + /healthz router"
```

---

## Task 21: Integration Test Harness

**Files:**
- Create: `packages/api/tests/integration/conftest.py`
- Create: `packages/api/tests/integration/test_health.py`

- [ ] **Step 1: Write `tests/integration/conftest.py`**

```python
"""Integration test fixtures.

Require a live Supabase CLI stack:
    supabase start

Env vars (set in CI via the workflow; locally via .env.test or shell):
    DATABASE_URL, SUPABASE_URL, SUPABASE_JWT_SECRET
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import httpx
import jwt
import pytest
import pytest_asyncio

from api.config import Settings, get_settings
from api.main import create_app

pytestmark = pytest.mark.integration


def _int_settings() -> Settings:
    return Settings(
        DATABASE_URL=os.environ["DATABASE_URL"],
        SUPABASE_URL=os.environ["SUPABASE_URL"],
        SUPABASE_JWT_SECRET=os.environ["SUPABASE_JWT_SECRET"],
        ALLOWED_ORIGINS="",
        LOG_LEVEL="WARNING",
        ENV="ci",
    )


@pytest.fixture(scope="session")
def settings() -> Settings:
    return _int_settings()


@pytest_asyncio.fixture()
async def pool(settings: Settings) -> AsyncIterator[asyncpg.Pool]:
    pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL, min_size=1, max_size=4)
    try:
        yield pool
    finally:
        await pool.close()


@pytest_asyncio.fixture(autouse=True)
async def _truncate(pool: asyncpg.Pool) -> AsyncIterator[None]:
    async with pool.acquire() as conn:
        await conn.execute(
            "truncate public.audit_log, public.valuation_snapshot, "
            "public.property, public.entity, public.app_user cascade"
        )
    yield


@pytest_asyncio.fixture()
async def app(settings: Settings) -> AsyncIterator[Any]:
    application = create_app(settings=settings)
    # Trigger lifespan
    async with application.router.lifespan_context(application):
        yield application


@pytest_asyncio.fixture()
async def client(app: Any) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _mint_token(settings: Settings, *, sub: UUID, email: str) -> str:
    now = datetime.now(tz=timezone.utc)
    return jwt.encode(
        {
            "sub": str(sub),
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
        },
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )


@pytest_asyncio.fixture()
async def make_user(pool: asyncpg.Pool, settings: Settings):
    """Factory: `(email, role='valuer')` → (user_id, Authorization header)."""
    async def _make(email: str = "alice@example.com", role: str = "valuer"):
        uid = uuid4()
        async with pool.acquire() as conn:
            await conn.execute(
                "insert into public.app_user (id, email, role, last_seen_at) "
                "values ($1, $2, $3, now())",
                uid, email, role,
            )
        token = _mint_token(settings, sub=uid, email=email)
        return uid, {"Authorization": f"Bearer {token}"}
    return _make


@pytest_asyncio.fixture()
async def valuer(make_user):
    return await make_user("valuer@example.com", "valuer")


@pytest_asyncio.fixture()
async def viewer(make_user):
    return await make_user("viewer@example.com", "viewer")
```

- [ ] **Step 2: Write `tests/integration/test_health.py`**

```python
from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_healthz(client: httpx.AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["api_version"]
    assert body["engine_version"]
```

- [ ] **Step 3: Run with stack up (local)**

```bash
# From repo root
supabase start

# In packages/api
export DATABASE_URL="postgresql://postgres:postgres@localhost:54322/postgres"
export SUPABASE_URL="http://localhost:54321"
export SUPABASE_JWT_SECRET=$(supabase status -o env | grep JWT_SECRET | cut -d= -f2-)
uv run pytest -m integration tests/integration/test_health.py -v
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add packages/api/tests/integration
git commit -m "test(api): add integration harness + /healthz coverage"
```

---

## Task 22: `/me` Router + Test

**Files:**
- Create: `packages/api/src/api/routers/me.py`
- Modify: `packages/api/src/api/main.py`
- Create: `packages/api/tests/integration/test_me.py`

- [ ] **Step 1: Write `routers/me.py`**

```python
"""GET /me — current user, auto-provisioned on first call."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from api.auth import current_user
from api.schemas.user import AppUser

router = APIRouter(tags=["me"])


@router.get("/me", response_model=AppUser)
async def me(user: Annotated[AppUser, Depends(current_user)]) -> AppUser:
    return user
```

- [ ] **Step 2: Register the router in `main.py`**

Replace the router-include block near the end of `create_app`:

```python
from api.routers import health as health_router
from api.routers import me as me_router

# ... inside create_app, after install_exception_handlers:
    app.include_router(health_router.router)
    app.include_router(me_router.router)
```

- [ ] **Step 3: Write the integration test**

```python
# packages/api/tests/integration/test_me.py
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_me_requires_bearer_token(client) -> None:
    r = await client.get("/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "missing_token"


async def test_me_returns_user_for_existing_app_user(client, valuer) -> None:
    _, headers = valuer
    r = await client.get("/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "valuer"


async def test_me_auto_provisions_new_user_as_viewer(client, settings, pool) -> None:
    # Mint a token for a sub with no app_user row yet.
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    import jwt as jwtlib

    sub = uuid4()
    now = datetime.now(tz=timezone.utc)
    token = jwtlib.encode(
        {
            "sub": str(sub),
            "email": "new@example.com",
            "aud": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
        },
        settings.SUPABASE_JWT_SECRET,
        algorithm="HS256",
    )
    r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["role"] == "viewer"

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select role from public.app_user where id = $1", sub
        )
        assert row is not None
        assert row["role"] == "viewer"
```

- [ ] **Step 4: Run**

```bash
uv run pytest -m integration tests/integration/test_me.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/api/routers/me.py packages/api/src/api/main.py packages/api/tests/integration/test_me.py
git commit -m "feat(api): add /me endpoint with auto-provisioning"
```

---

## Task 23: `/entities` Router (CRUD + soft-delete + audit)

**Files:**
- Create: `packages/api/src/api/routers/entities.py`
- Modify: `packages/api/src/api/main.py`
- Create: `packages/api/tests/integration/test_entities.py`

- [ ] **Step 1: Write `routers/entities.py`**

```python
"""CRUD + soft-delete endpoints for entity."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from api.audit import audit, record_to_json
from api.auth import current_user, require_valuer
from api.db import get_db
from api.errors import APIError
from api.queries import entity as q_entity
from api.schemas.entity import Entity, EntityCreate, EntityUpdate
from api.schemas.user import AppUser

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("", response_model=list[Entity])
async def list_entities(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    include_deleted: bool = Query(default=False),
) -> list[Entity]:
    rows = await q_entity.list_entities(conn, include_deleted=include_deleted)
    return [Entity.model_validate(dict(r)) for r in rows]


@router.get("/{entity_id}", response_model=Entity)
async def get_entity(
    entity_id: UUID,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    include_deleted: bool = Query(default=False),
) -> Entity:
    row = await q_entity.get_entity(conn, entity_id, include_deleted=include_deleted)
    if row is None:
        raise APIError(status_code=404, code="not_found", message="Entity not found.")
    return Entity.model_validate(dict(row))


@router.post("", response_model=Entity, status_code=201)
async def create_entity(
    body: EntityCreate,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Entity:
    async with conn.transaction():
        row = await q_entity.insert_entity(
            conn,
            name=body.name,
            registration_number=body.registration_number,
            notes=body.notes,
        )
        await audit(
            conn,
            actor_id=user.id,
            actor_email=user.email,
            action="create",
            target_table="entity",
            target_id=row["id"],
            before=None,
            after=record_to_json(row),
        )
    return Entity.model_validate(dict(row))


@router.patch("/{entity_id}", response_model=Entity)
async def update_entity(
    entity_id: UUID,
    body: EntityUpdate,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Entity:
    before = await q_entity.get_entity(conn, entity_id)
    if before is None:
        raise APIError(status_code=404, code="not_found", message="Entity not found.")
    patch = body.model_dump(exclude_unset=True)
    async with conn.transaction():
        after_row = await q_entity.update_entity(conn, entity_id, patch)
        assert after_row is not None
        await audit(
            conn,
            actor_id=user.id,
            actor_email=user.email,
            action="update",
            target_table="entity",
            target_id=entity_id,
            before=record_to_json(before),
            after=record_to_json(after_row),
        )
    return Entity.model_validate(dict(after_row))


@router.delete("/{entity_id}", response_model=Entity)
async def delete_entity(
    entity_id: UUID,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Entity:
    before = await q_entity.get_entity(conn, entity_id)
    if before is None:
        raise APIError(status_code=404, code="not_found", message="Entity not found.")
    live_children = await q_entity.count_live_properties(conn, entity_id)
    if live_children > 0:
        raise APIError(
            status_code=409, code="has_live_children",
            message="Entity has live properties and cannot be deleted.",
            details={"blocking_count": live_children},
        )
    async with conn.transaction():
        after_row = await q_entity.soft_delete_entity(conn, entity_id)
        assert after_row is not None
        await audit(
            conn,
            actor_id=user.id,
            actor_email=user.email,
            action="soft_delete",
            target_table="entity",
            target_id=entity_id,
            before=record_to_json(before),
            after=record_to_json(after_row),
        )
    return Entity.model_validate(dict(after_row))
```

- [ ] **Step 2: Register in `main.py`**

```python
from api.routers import entities as entities_router

# ... inside create_app, before `return app`:
    app.include_router(entities_router.router)
```

- [ ] **Step 3: Write integration tests**

```python
# packages/api/tests/integration/test_entities.py
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_create_and_list_entity(client, valuer) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "Acme"})
    assert r.status_code == 201
    assert r.json()["name"] == "Acme"

    r = await client.get("/entities", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_viewer_cannot_create_entity(client, viewer) -> None:
    _, headers = viewer
    r = await client.post("/entities", headers=headers, json={"name": "Acme"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


async def test_patch_entity_name_only(client, valuer) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "A"})
    eid = r.json()["id"]
    r = await client.patch(f"/entities/{eid}", headers=headers, json={"name": "B"})
    assert r.status_code == 200
    assert r.json()["name"] == "B"


async def test_patch_empty_body_422(client, valuer) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "A"})
    eid = r.json()["id"]
    r = await client.patch(f"/entities/{eid}", headers=headers, json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_input"


async def test_delete_entity_soft(client, valuer) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "A"})
    eid = r.json()["id"]
    r = await client.delete(f"/entities/{eid}", headers=headers)
    assert r.status_code == 200
    assert r.json()["deleted_at"] is not None

    # Default list hides soft-deleted
    r = await client.get("/entities", headers=headers)
    assert r.json() == []

    # include_deleted shows it
    r = await client.get("/entities?include_deleted=true", headers=headers)
    assert len(r.json()) == 1


async def test_delete_entity_with_live_property_409(client, valuer, pool) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "A"})
    eid = r.json()["id"]
    async with pool.acquire() as conn:
        await conn.execute(
            "insert into public.property (entity_id, name) values ($1, $2)",
            eid, "P",
        )
    r = await client.delete(f"/entities/{eid}", headers=headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "has_live_children"
    assert r.json()["error"]["details"]["blocking_count"] == 1


async def test_entity_audit_trail_written(client, valuer, pool) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "A"})
    eid = r.json()["id"]
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select action from public.audit_log where target_id = $1 order by created_at asc",
            eid,
        )
    assert [dict(r)["action"] for r in rows] == ["create"]
```

- [ ] **Step 4: Run**

```bash
uv run pytest -m integration tests/integration/test_entities.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/api/routers/entities.py packages/api/src/api/main.py packages/api/tests/integration/test_entities.py
git commit -m "feat(api): add /entities CRUD + soft delete + audit"
```

---

## Task 24: `/properties` Router

**Files:**
- Create: `packages/api/src/api/routers/properties.py`
- Modify: `packages/api/src/api/main.py`
- Create: `packages/api/tests/integration/test_properties.py`

- [ ] **Step 1: Write `routers/properties.py`**

```python
"""CRUD + soft-delete endpoints for property."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from api.audit import audit, record_to_json
from api.auth import current_user, require_valuer
from api.db import get_db
from api.errors import APIError
from api.queries import entity as q_entity
from api.queries import property as q_property
from api.schemas.property import Property, PropertyCreate, PropertyType, PropertyUpdate
from api.schemas.user import AppUser

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=list[Property])
async def list_properties(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    entity_id: UUID | None = Query(default=None),
    property_type: PropertyType | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> list[Property]:
    rows = await q_property.list_properties(
        conn,
        entity_id=entity_id,
        property_type=property_type,
        include_deleted=include_deleted,
    )
    return [Property.model_validate(dict(r)) for r in rows]


@router.get("/{property_id}", response_model=Property)
async def get_property(
    property_id: UUID,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    include_deleted: bool = Query(default=False),
) -> Property:
    row = await q_property.get_property(conn, property_id, include_deleted=include_deleted)
    if row is None:
        raise APIError(status_code=404, code="not_found", message="Property not found.")
    return Property.model_validate(dict(row))


@router.post("", response_model=Property, status_code=201)
async def create_property(
    body: PropertyCreate,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Property:
    parent = await q_entity.get_entity(conn, body.entity_id)
    if parent is None:
        raise APIError(status_code=422, code="invalid_input",
                       message="entity_id does not reference a live entity.")
    async with conn.transaction():
        row = await q_property.insert_property(
            conn,
            entity_id=body.entity_id,
            name=body.name,
            address=body.address,
            property_type=body.property_type,
            notes=body.notes,
        )
        await audit(
            conn,
            actor_id=user.id, actor_email=user.email,
            action="create", target_table="property",
            target_id=row["id"],
            before=None, after=record_to_json(row),
        )
    return Property.model_validate(dict(row))


@router.patch("/{property_id}", response_model=Property)
async def update_property(
    property_id: UUID,
    body: PropertyUpdate,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Property:
    before = await q_property.get_property(conn, property_id)
    if before is None:
        raise APIError(status_code=404, code="not_found", message="Property not found.")
    patch = body.model_dump(exclude_unset=True)
    async with conn.transaction():
        after_row = await q_property.update_property(conn, property_id, patch)
        assert after_row is not None
        await audit(
            conn,
            actor_id=user.id, actor_email=user.email,
            action="update", target_table="property",
            target_id=property_id,
            before=record_to_json(before), after=record_to_json(after_row),
        )
    return Property.model_validate(dict(after_row))


@router.delete("/{property_id}", response_model=Property)
async def delete_property(
    property_id: UUID,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Property:
    before = await q_property.get_property(conn, property_id)
    if before is None:
        raise APIError(status_code=404, code="not_found", message="Property not found.")
    live = await q_property.count_active_snapshots(conn, property_id)
    if live > 0:
        raise APIError(
            status_code=409, code="has_live_children",
            message="Property has active valuation snapshots.",
            details={"blocking_count": live},
        )
    async with conn.transaction():
        after_row = await q_property.soft_delete_property(conn, property_id)
        assert after_row is not None
        await audit(
            conn,
            actor_id=user.id, actor_email=user.email,
            action="soft_delete", target_table="property",
            target_id=property_id,
            before=record_to_json(before), after=record_to_json(after_row),
        )
    return Property.model_validate(dict(after_row))
```

- [ ] **Step 2: Register in `main.py`**

```python
from api.routers import properties as properties_router
# ...
    app.include_router(properties_router.router)
```

- [ ] **Step 3: Write integration tests**

```python
# packages/api/tests/integration/test_properties.py
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_create_property(client, valuer) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "E"})
    eid = r.json()["id"]
    r = await client.post(
        "/properties",
        headers=headers,
        json={"entity_id": eid, "name": "Tower A", "property_type": "office"},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "Tower A"
    assert r.json()["property_type"] == "office"


async def test_filter_by_entity_id(client, valuer) -> None:
    _, headers = valuer
    r = await client.post("/entities", headers=headers, json={"name": "E1"})
    e1 = r.json()["id"]
    r = await client.post("/entities", headers=headers, json={"name": "E2"})
    e2 = r.json()["id"]
    for eid, name in ((e1, "P1"), (e1, "P2"), (e2, "P3")):
        await client.post(
            "/properties", headers=headers, json={"entity_id": eid, "name": name},
        )
    r = await client.get(f"/properties?entity_id={e1}", headers=headers)
    assert r.status_code == 200
    assert sorted(p["name"] for p in r.json()) == ["P1", "P2"]


async def test_create_property_unknown_entity_422(client, valuer) -> None:
    _, headers = valuer
    r = await client.post(
        "/properties", headers=headers,
        json={"entity_id": "00000000-0000-0000-0000-000000000000", "name": "X"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_input"


async def test_viewer_cannot_create_property(client, viewer) -> None:
    _, headers = viewer
    r = await client.post(
        "/properties", headers=headers,
        json={"entity_id": "00000000-0000-0000-0000-000000000000", "name": "X"},
    )
    assert r.status_code == 403
```

- [ ] **Step 4: Run**

```bash
uv run pytest -m integration tests/integration/test_properties.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/api/routers/properties.py packages/api/src/api/main.py packages/api/tests/integration/test_properties.py
git commit -m "feat(api): add /properties CRUD + filters + soft delete"
```

---

## Task 25: `/calculate` Router (preview, valuer-only)

**Files:**
- Create: `packages/api/src/api/routers/calculate.py`
- Modify: `packages/api/src/api/main.py`
- Create: `packages/api/tests/unit/test_calculate_router.py`

- [ ] **Step 1: Write `routers/calculate.py`**

```python
"""POST /calculate — preview valuation from ValuationInput; no DB write.

Valuer-only per spec §7.1. Engine ValueError surfaces as 422.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from api.auth import require_valuer
from api.schemas.user import AppUser

try:
    from valuation_engine import calculate
    from valuation_engine.models import ValuationInput
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("valuation_engine must be installed") from exc


router = APIRouter(tags=["calculate"])


@router.post("/calculate")
async def preview_calculate(
    body: ValuationInput,
    _user: Annotated[AppUser, Depends(require_valuer)],
) -> dict[str, Any]:
    result = calculate(body)
    return result.model_dump(mode="json")
```

- [ ] **Step 2: Register in `main.py`**

```python
from api.routers import calculate as calculate_router
# ...
    app.include_router(calculate_router.router)
```

- [ ] **Step 3: Write the failing unit test**

```python
# packages/api/tests/unit/test_calculate_router.py
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from api.auth import current_user, require_valuer
from api.errors import install_exception_handlers
from api.schemas.user import AppUser


def _stub_user(role: str = "valuer") -> AppUser:
    from datetime import datetime, timezone
    from uuid import UUID
    return AppUser(
        id=UUID(int=1), email="v@x.com", display_name=None, role=role,
        created_at=datetime.now(tz=timezone.utc), last_seen_at=None,
    )


def _app_for_calc(role: str = "valuer"):
    from fastapi import FastAPI

    from api.routers import calculate as calculate_router

    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(calculate_router.router)
    app.dependency_overrides[current_user] = lambda: _stub_user(role)
    app.dependency_overrides[require_valuer] = (
        lambda: _stub_user("valuer") if role == "valuer"
        else (_ for _ in ()).throw(
            __import__("api.errors", fromlist=["APIError"]).APIError(
                status_code=403, code="forbidden", message="fb"
            )
        )
    )
    return app


def _payload() -> dict:
    return {
        "valuation_date": date(2026, 1, 1).isoformat(),
        "tenants": [{
            "description": "Office",
            "rentable_area_m2": "100",
            "rent_per_m2_pm": "85",
            "annual_escalation_pct": "0",
        }],
        "monthly_operating_expenses": "0",
        "vacancy_allowance_pct": "0",
        "cap_rate": "0.10",
    }


def test_calculate_happy_path_returns_result() -> None:
    with TestClient(_app_for_calc(role="valuer")) as client:
        r = client.post("/calculate", json=_payload())
    assert r.status_code == 200
    assert "market_value" in r.json()
    assert "engine_version" in r.json()


def test_calculate_invalid_input_422() -> None:
    payload = _payload()
    payload["cap_rate"] = "0"
    with TestClient(_app_for_calc(role="valuer"), raise_server_exceptions=False) as client:
        r = client.post("/calculate", json=payload)
    assert r.status_code == 422
```

- [ ] **Step 4: Run**

```bash
uv run pytest tests/unit/test_calculate_router.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/api/routers/calculate.py packages/api/src/api/main.py packages/api/tests/unit/test_calculate_router.py
git commit -m "feat(api): add /calculate preview endpoint"
```

---

## Task 26: `/snapshots` Router (list, get, create)

**Files:**
- Create: `packages/api/src/api/routers/snapshots.py`
- Modify: `packages/api/src/api/main.py`
- Create: `packages/api/tests/integration/test_snapshots.py`

- [ ] **Step 1: Write `routers/snapshots.py`**

```python
"""Snapshot endpoints: list per property, get one, create (runs engine + persists)."""
from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from api.audit import audit, record_to_json
from api.auth import current_user, require_valuer
from api.db import get_db
from api.errors import APIError
from api.queries import property as q_property
from api.queries import snapshot as q_snapshot
from api.queries.snapshot import _json_default
from api.schemas.snapshot import Snapshot
from api.schemas.user import AppUser

try:
    from valuation_engine import __version__ as engine_version
    from valuation_engine import calculate
    from valuation_engine.models import ValuationInput
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("valuation_engine must be installed") from exc


snapshots_router = APIRouter(tags=["snapshots"])
properties_snapshots_router = APIRouter(prefix="/properties", tags=["snapshots"])


@properties_snapshots_router.get(
    "/{property_id}/snapshots", response_model=list[Snapshot]
)
async def list_property_snapshots(
    property_id: UUID,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> list[Snapshot]:
    prop = await q_property.get_property(conn, property_id, include_deleted=True)
    if prop is None:
        raise APIError(status_code=404, code="not_found", message="Property not found.")
    rows = await q_snapshot.list_for_property(conn, property_id)
    return [_row_to_schema(r) for r in rows]


@snapshots_router.get("/snapshots/{snapshot_id}", response_model=Snapshot)
async def get_snapshot(
    snapshot_id: UUID,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Snapshot:
    row = await q_snapshot.get_snapshot(conn, snapshot_id)
    if row is None:
        raise APIError(status_code=404, code="not_found", message="Snapshot not found.")
    return _row_to_schema(row)


@properties_snapshots_router.post(
    "/{property_id}/snapshots", response_model=Snapshot, status_code=201
)
async def create_snapshot(
    property_id: UUID,
    body: ValuationInput,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Snapshot:
    prop = await q_property.get_property(conn, property_id)
    if prop is None:
        raise APIError(status_code=404, code="not_found", message="Property not found.")

    result = calculate(body)
    inputs_json = body.model_dump(mode="json")
    result_json = result.model_dump(mode="json")

    async with conn.transaction():
        await q_snapshot.supersede_active(conn, property_id)
        row = await q_snapshot.insert_snapshot(
            conn,
            property_id=property_id,
            valuation_date=body.valuation_date,
            created_by=user.id,
            inputs_json=inputs_json,
            result_json=result_json,
            market_value=result.market_value,
            cap_rate=body.cap_rate,
            engine_version=engine_version,
            source="manual",
            source_file=None,
        )
        await audit(
            conn,
            actor_id=user.id,
            actor_email=user.email,
            action="create",
            target_table="valuation_snapshot",
            target_id=row["id"],
            before=None,
            after=record_to_json(row),
        )
    return _row_to_schema(row)


def _row_to_schema(row: asyncpg.Record) -> Snapshot:
    d = dict(row)
    # jsonb columns come back as dicts already, but be defensive with str fallback.
    for k in ("inputs_json", "result_json"):
        val = d[k]
        if isinstance(val, str):
            d[k] = json.loads(val)
    return Snapshot.model_validate(d)
```

- [ ] **Step 2: Register in `main.py`**

```python
from api.routers import snapshots as snapshots_router
# ...
    app.include_router(snapshots_router.snapshots_router)
    app.include_router(snapshots_router.properties_snapshots_router)
```

- [ ] **Step 3: Write integration tests**

```python
# packages/api/tests/integration/test_snapshots.py
from __future__ import annotations

from datetime import date

import pytest

pytestmark = pytest.mark.integration


async def _make_property(client, headers) -> str:
    r = await client.post("/entities", headers=headers, json={"name": "E"})
    eid = r.json()["id"]
    r = await client.post(
        "/properties", headers=headers,
        json={"entity_id": eid, "name": "P", "property_type": "office"},
    )
    return r.json()["id"]


def _inputs() -> dict:
    return {
        "valuation_date": date(2026, 1, 1).isoformat(),
        "tenants": [{
            "description": "Office",
            "rentable_area_m2": "100",
            "rent_per_m2_pm": "85",
            "annual_escalation_pct": "0",
        }],
        "monthly_operating_expenses": "0",
        "vacancy_allowance_pct": "0",
        "cap_rate": "0.10",
    }


async def test_create_snapshot_and_get(client, valuer) -> None:
    _, headers = valuer
    pid = await _make_property(client, headers)
    r = await client.post(
        f"/properties/{pid}/snapshots", headers=headers, json=_inputs()
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "active"
    sid = body["id"]

    r = await client.get(f"/snapshots/{sid}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == sid


async def test_second_snapshot_supersedes_first(client, valuer) -> None:
    _, headers = valuer
    pid = await _make_property(client, headers)
    r1 = await client.post(f"/properties/{pid}/snapshots", headers=headers, json=_inputs())
    s1 = r1.json()["id"]
    r2 = await client.post(f"/properties/{pid}/snapshots", headers=headers, json=_inputs())
    s2 = r2.json()["id"]
    assert s1 != s2

    r = await client.get(f"/snapshots/{s1}", headers=headers)
    assert r.json()["status"] == "superseded"
    r = await client.get(f"/snapshots/{s2}", headers=headers)
    assert r.json()["status"] == "active"


async def test_list_snapshots_for_property(client, valuer) -> None:
    _, headers = valuer
    pid = await _make_property(client, headers)
    await client.post(f"/properties/{pid}/snapshots", headers=headers, json=_inputs())
    r = await client.get(f"/properties/{pid}/snapshots", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_viewer_cannot_create_snapshot(client, viewer) -> None:
    _, headers = viewer
    r = await client.post(
        "/properties/00000000-0000-0000-0000-000000000000/snapshots",
        headers=headers, json=_inputs(),
    )
    assert r.status_code == 403


async def test_snapshot_records_engine_version(client, valuer) -> None:
    from valuation_engine import __version__ as ev
    _, headers = valuer
    pid = await _make_property(client, headers)
    r = await client.post(f"/properties/{pid}/snapshots", headers=headers, json=_inputs())
    assert r.json()["engine_version"] == ev


async def test_snapshot_property_not_found_404(client, valuer) -> None:
    _, headers = valuer
    r = await client.post(
        "/properties/00000000-0000-0000-0000-000000000000/snapshots",
        headers=headers, json=_inputs(),
    )
    assert r.status_code == 404


async def test_snapshot_engine_error_422(client, valuer) -> None:
    _, headers = valuer
    pid = await _make_property(client, headers)
    bad = _inputs()
    bad["cap_rate"] = "0"  # engine rejects
    r = await client.post(f"/properties/{pid}/snapshots", headers=headers, json=bad)
    assert r.status_code == 422
```

- [ ] **Step 4: Run**

```bash
uv run pytest -m integration tests/integration/test_snapshots.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/api/routers/snapshots.py packages/api/src/api/main.py packages/api/tests/integration/test_snapshots.py
git commit -m "feat(api): add snapshot list/get/create with supersede + audit"
```

---

## Task 27: `/portfolio/summary` + `/portfolio/timeseries`

**Files:**
- Create: `packages/api/src/api/routers/portfolio.py`
- Modify: `packages/api/src/api/main.py`
- Create: `packages/api/tests/integration/test_portfolio.py`

- [ ] **Step 1: Write `routers/portfolio.py`**

```python
"""Portfolio endpoints."""
from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from api.auth import current_user
from api.db import get_db
from api.queries import portfolio as q_portfolio
from api.schemas.portfolio import (
    PortfolioSummary,
    PortfolioTimeseries,
    TimeseriesPoint,
    TopProperty,
    ValueByEntity,
    ValueByType,
)
from api.schemas.user import AppUser

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummary)
async def get_summary(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    limit: int = Query(default=10, ge=1, le=100),
) -> PortfolioSummary:
    raw = await q_portfolio.summary(conn, top_limit=limit)
    return PortfolioSummary(
        total_market_value=raw["total_market_value"],
        property_count=raw["property_count"],
        entity_count=raw["entity_count"],
        last_snapshot_date=raw["last_snapshot_date"],
        value_by_type=[ValueByType(**r) for r in raw["value_by_type"]],
        value_by_entity=[ValueByEntity(**r) for r in raw["value_by_entity"]],
        top_properties=[TopProperty(**r) for r in raw["top_properties"]],
    )


@router.get("/timeseries", response_model=PortfolioTimeseries)
async def get_timeseries(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    bucket: Literal["year"] = Query(default="year"),
) -> PortfolioTimeseries:
    rows = await q_portfolio.timeseries_year(conn)
    points = [TimeseriesPoint(**dict(r)) for r in rows]
    return PortfolioTimeseries(bucket=bucket, points=points)
```

- [ ] **Step 2: Register in `main.py`**

```python
from api.routers import portfolio as portfolio_router
# ...
    app.include_router(portfolio_router.router)
```

- [ ] **Step 3: Write integration tests**

```python
# packages/api/tests/integration/test_portfolio.py
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

pytestmark = pytest.mark.integration


async def _seed(client, headers) -> list[str]:
    """Two entities, four properties, snapshots at varying values."""
    ids: list[str] = []
    e1 = (await client.post("/entities", headers=headers, json={"name": "E1"})).json()["id"]
    e2 = (await client.post("/entities", headers=headers, json={"name": "E2"})).json()["id"]
    for eid, name, ptype, rent, cap, dt in (
        (e1, "P1", "office", "85", "0.10", "2025-06-01"),
        (e1, "P2", "retail", "120", "0.09", "2025-06-01"),
        (e2, "P3", "industrial", "50", "0.12", "2025-06-01"),
        (e2, "P4", "office", "100", "0.11", "2026-01-01"),
    ):
        p = (await client.post(
            "/properties", headers=headers,
            json={"entity_id": eid, "name": name, "property_type": ptype},
        )).json()["id"]
        ids.append(p)
        await client.post(
            f"/properties/{p}/snapshots", headers=headers,
            json={
                "valuation_date": dt,
                "tenants": [{
                    "description": "T",
                    "rentable_area_m2": "100",
                    "rent_per_m2_pm": rent,
                    "annual_escalation_pct": "0",
                }],
                "monthly_operating_expenses": "500",
                "vacancy_allowance_pct": "0.05",
                "cap_rate": cap,
            },
        )
    return ids


async def test_portfolio_summary_structure(client, valuer) -> None:
    _, headers = valuer
    await _seed(client, headers)
    r = await client.get("/portfolio/summary", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["property_count"] == 4
    assert body["entity_count"] == 2
    assert Decimal(body["total_market_value"]) > 0
    types = {row["type"] for row in body["value_by_type"]}
    assert {"office", "retail", "industrial"} <= types
    assert 0 < len(body["top_properties"]) <= 10


async def test_portfolio_top_limit(client, valuer) -> None:
    _, headers = valuer
    await _seed(client, headers)
    r = await client.get("/portfolio/summary?limit=2", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["top_properties"]) == 2


async def test_portfolio_timeseries_year(client, valuer) -> None:
    _, headers = valuer
    await _seed(client, headers)
    r = await client.get("/portfolio/timeseries", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["bucket"] == "year"
    years = {p["bucket_date"][:4] for p in body["points"]}
    assert {"2025", "2026"} <= years


async def test_portfolio_empty_returns_zero_totals(client, valuer) -> None:
    _, headers = valuer
    r = await client.get("/portfolio/summary", headers=headers)
    assert r.status_code == 200
    assert r.json()["property_count"] == 0
    assert Decimal(r.json()["total_market_value"]) == Decimal("0")
```

- [ ] **Step 4: Run**

```bash
uv run pytest -m integration tests/integration/test_portfolio.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/api/src/api/routers/portfolio.py packages/api/src/api/main.py packages/api/tests/integration/test_portfolio.py
git commit -m "feat(api): add /portfolio/summary + /portfolio/timeseries"
```

---

## Task 28: `/users` + `/audit` Routers

**Files:**
- Create: `packages/api/src/api/routers/users.py`
- Create: `packages/api/src/api/routers/audit.py`
- Modify: `packages/api/src/api/main.py`
- Create: `packages/api/tests/integration/test_users.py`
- Create: `packages/api/tests/integration/test_audit.py`

- [ ] **Step 1: Write `routers/users.py`**

```python
"""GET /users — list app_user rows."""
from __future__ import annotations

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends

from api.auth import current_user
from api.db import get_db
from api.queries import app_user as q_app_user
from api.schemas.user import AppUser

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[AppUser])
async def list_users(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> list[AppUser]:
    rows = await q_app_user.list_users(conn)
    return [AppUser.model_validate(dict(r)) for r in rows]
```

- [ ] **Step 2: Write `routers/audit.py`**

```python
"""GET /audit — paginated audit log."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from api.auth import current_user
from api.db import get_db
from api.queries import audit as q_audit
from api.schemas.audit import AuditEntry, AuditPage, AuditTargetTable
from api.schemas.user import AppUser

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditPage)
async def list_audit(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    target_table: AuditTargetTable | None = Query(default=None),
    actor_id: UUID | None = Query(default=None),
) -> AuditPage:
    rows, total = await q_audit.list_audit(
        conn, limit=limit, offset=offset,
        target_table=target_table, actor_id=actor_id,
    )
    return AuditPage(
        items=[AuditEntry.model_validate(dict(r)) for r in rows],
        total=total, limit=limit, offset=offset,
    )
```

- [ ] **Step 3: Register both in `main.py`**

```python
from api.routers import audit as audit_router
from api.routers import users as users_router
# ...
    app.include_router(users_router.router)
    app.include_router(audit_router.router)
```

- [ ] **Step 4: Write integration tests**

```python
# packages/api/tests/integration/test_users.py
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_users_list_contains_self(client, valuer) -> None:
    _, headers = valuer
    r = await client.get("/users", headers=headers)
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()}
    assert "valuer@example.com" in emails
```

```python
# packages/api/tests/integration/test_audit.py
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_audit_contains_entity_create(client, valuer) -> None:
    _, headers = valuer
    await client.post("/entities", headers=headers, json={"name": "A"})
    r = await client.get("/audit", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert any(
        e["target_table"] == "entity" and e["action"] == "create"
        for e in body["items"]
    )


async def test_audit_filter_by_target_table(client, valuer) -> None:
    _, headers = valuer
    e = (await client.post("/entities", headers=headers, json={"name": "A"})).json()
    await client.post(
        "/properties", headers=headers,
        json={"entity_id": e["id"], "name": "P"},
    )
    r = await client.get("/audit?target_table=property", headers=headers)
    assert r.status_code == 200
    assert all(item["target_table"] == "property" for item in r.json()["items"])


async def test_audit_pagination(client, valuer) -> None:
    _, headers = valuer
    for i in range(5):
        await client.post("/entities", headers=headers, json={"name": f"E{i}"})
    r = await client.get("/audit?limit=2&offset=0", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
```

- [ ] **Step 5: Run**

```bash
uv run pytest -m integration tests/integration/test_users.py tests/integration/test_audit.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/api/src/api/routers/users.py packages/api/src/api/routers/audit.py packages/api/src/api/main.py packages/api/tests/integration/test_users.py packages/api/tests/integration/test_audit.py
git commit -m "feat(api): add /users + /audit endpoints"
```

---

## Task 29: Dockerfile + render.yaml + smoke.sh

**Files:**
- Create: `packages/api/Dockerfile`
- Create: `packages/api/render.yaml`
- Create: `packages/api/scripts/smoke.sh`

- [ ] **Step 1: Write `packages/api/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.4.*

WORKDIR /app

# Copy engine first so the editable/path install works; release builds still
# resolve via the tagged git ref from [project.dependencies] when
# `uv sync --no-sources` is used in CI.
COPY packages/valuation_engine /app/packages/valuation_engine
COPY packages/api /app/packages/api

WORKDIR /app/packages/api
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 1001 appuser
USER appuser

ENV PORT=8000
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Write `packages/api/render.yaml`**

```yaml
services:
  - type: web
    name: property-valuations-api
    env: docker
    plan: starter
    region: frankfurt
    dockerfilePath: ./packages/api/Dockerfile
    dockerContext: .
    healthCheckPath: /healthz
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_JWT_SECRET
        sync: false
      - key: ALLOWED_ORIGINS
        sync: false
      - key: LOG_LEVEL
        value: INFO
      - key: ENV
        value: prod
```

- [ ] **Step 3: Write `packages/api/scripts/smoke.sh`**

```bash
#!/usr/bin/env bash
# Post-deploy smoke test.
# Usage: scripts/smoke.sh https://api.example.com <VALID_JWT>
set -euo pipefail

BASE="${1:?BASE_URL required}"
TOKEN="${2:?JWT required}"
AUTH="Authorization: Bearer ${TOKEN}"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "ok: $*"; }

code=$(curl -s -o /tmp/health.json -w '%{http_code}' "${BASE}/healthz")
[ "${code}" = "200" ] || fail "/healthz returned ${code}"
grep -q '"status":"ok"' /tmp/health.json || fail "/healthz body missing status"
ok "/healthz"

code=$(curl -s -o /tmp/me.json -w '%{http_code}' -H "${AUTH}" "${BASE}/me")
[ "${code}" = "200" ] || fail "/me returned ${code}"
grep -q '"role"' /tmp/me.json || fail "/me body missing role"
ok "/me"

code=$(curl -s -o /tmp/ents.json -w '%{http_code}' -H "${AUTH}" "${BASE}/entities")
[ "${code}" = "200" ] || fail "/entities returned ${code}"
ok "/entities"

echo "all smoke checks passed"
```

- [ ] **Step 4: Make the script executable and test locally (optional)**

```bash
chmod +x packages/api/scripts/smoke.sh
```

- [ ] **Step 5: Commit**

```bash
git add packages/api/Dockerfile packages/api/render.yaml packages/api/scripts/smoke.sh
git commit -m "chore(api): add Dockerfile, render.yaml, smoke.sh"
```

---

## Task 30: GitHub Actions — `api.yml`

**Files:**
- Create: `.github/workflows/api.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: api
on:
  push:
    paths:
      - 'packages/api/**'
      - 'packages/valuation_engine/**'
      - 'supabase/**'
      - '.github/workflows/api.yml'
  pull_request:
    paths:
      - 'packages/api/**'
      - 'packages/valuation_engine/**'
      - 'supabase/**'
      - '.github/workflows/api.yml'

jobs:
  lint-type:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: packages/api
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Sync deps
        run: uv sync --all-extras
      - name: Ruff
        run: uv run ruff check src tests
      - name: Mypy
        run: uv run mypy src

  unit:
    needs: lint-type
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: packages/api
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Sync deps
        run: uv sync --all-extras
      - name: Unit tests
        run: uv run pytest -m "not integration" -v

  integration:
    needs: unit
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: packages/api
    env:
      DATABASE_URL: postgresql://postgres:postgres@localhost:54322/postgres
      SUPABASE_URL: http://localhost:54321
      SUPABASE_JWT_SECRET: super-secret-jwt-token-with-at-least-32-characters-long
    steps:
      - uses: actions/checkout@v4
      - uses: supabase/setup-cli@v1
        with:
          version: latest
      - name: Supabase start
        working-directory: .
        run: supabase start
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Sync deps
        run: uv sync --all-extras
      - name: Integration tests
        run: uv run pytest -m integration -v
      - name: Supabase stop
        if: always()
        working-directory: .
        run: supabase stop
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/api.yml
git commit -m "ci(api): lint, type-check, unit + integration via Supabase CLI"
```

---

## Task 31: Full test sweep + ruff + mypy

**Files:**
- None (verification task).

- [ ] **Step 1: Ruff full pass**

```bash
cd packages/api
uv run ruff check src tests
```

Expected: clean.

- [ ] **Step 2: Mypy strict pass**

```bash
uv run mypy src
```

Expected: `Success: no issues found`.

- [ ] **Step 3: Unit tests full pass**

```bash
uv run pytest -m "not integration" -v
```

Expected: all green.

- [ ] **Step 4: Integration tests full pass (stack up)**

```bash
# From repo root
supabase start

cd packages/api
export DATABASE_URL="postgresql://postgres:postgres@localhost:54322/postgres"
export SUPABASE_URL="http://localhost:54321"
export SUPABASE_JWT_SECRET=$(cd .. && cd .. && supabase status -o env | grep JWT_SECRET | cut -d= -f2-)
uv run pytest -m integration -v
```

Expected: all green.

- [ ] **Step 5: If anything fails, fix in a focused commit rather than amending prior commits.**

---

## Self-Review

Spec-coverage check against `docs/superpowers/specs/2026-04-24-api-core-design.md`:

| Spec section | Covered by |
|---|---|
| §4 File structure | Task 0, 1, 20 |
| §5.1 asyncpg pool + get_db | Task 6 |
| §5.2 per-table query layout | Tasks 13–18 |
| §5.3 migrations (6 files) | Tasks 10–12 |
| §5.4 RLS | Task 12 |
| §6.1 verify_jwt | Task 5 |
| §6.2 current_user upsert | Task 19 |
| §6.3 require_valuer | Task 19 |
| §7.1 endpoint inventory | Tasks 22–28 |
| §7.2 request/response shapes | Tasks 7–9 |
| §7.3 snapshot supersede flow | Task 26 |
| §7.4 error envelope | Task 4 |
| §8 audit helper + coverage | Tasks 17, 23, 24, 26 |
| §9 settings | Task 2 |
| §10 logging + /healthz | Tasks 3, 20 |
| §11 test layering | Tasks 7–9 (unit) + Task 21 (integration harness) |
| §12 GitHub Actions | Task 30 |
| §13 Dockerfile/render/smoke | Task 29 |
| §14 engine dependency | Task 1 pyproject |

All spec sections have implementing tasks. No placeholders. Type names consistent (`AppUser`, `APIError`, `ValuationInput`, `Snapshot`, `PropertyType`, `AuditTargetTable`) across tasks.

---
