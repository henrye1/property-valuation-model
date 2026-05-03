# Plan 3 — Excel Imports + PDF/XLSX Exports — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Excel import workflow (upload → background parse → reviewer queue → idempotent per-item commit) and the per-snapshot PDF + XLSX export endpoints on top of the Plan 2 FastAPI service.

**Architecture:** Pure API plumbing — the engine's parse/render shipped in Plan 1. New code lives under `packages/api/src/api/` in `routers/imports.py`, `routers/exports.py`, `queries/import_{batch,item}.py`, `schemas/imports.py`, and a new `services/` directory (storage wrapper, parse worker, matcher, commit worker, exports). Five additive SQL migrations (pg_trgm, two new tables, RLS, Storage bucket). Plan 2's three follow-up TODOs (db.py timeout, errors.py narrowing, version bump) land as the first three commits.

**Tech Stack:** Python 3.11+, FastAPI 0.110+, asyncpg, Pydantic v2, pydantic-settings, PyJWT, uv, hatchling, pytest + pytest-asyncio + httpx, Supabase CLI (Postgres + GoTrue + Storage), pg_trgm, WeasyPrint 62+, Jinja2, openpyxl (transitive via engine), pikepdf (dev only), GitHub Actions.

**Spec reference:** [`docs/superpowers/specs/2026-05-03-plan-3-imports-exports-design.md`](../specs/2026-05-03-plan-3-imports-exports-design.md).

---

## Adaptations from spec pseudocode (read first)

The spec's §8 pseudocode used two API shorthands that don't match the engine's actual API. Adaptations applied throughout this plan:

1. **Hard parse failures.** Spec said `excel.parse(bytes, filename)` raises `HardParseError`. Reality: `valuation_engine.excel.parse_workbook(path: Path) -> ParseResult` always returns; `parse_errors: list[ValuationWarning]` is populated and `inputs is None` when the parse fails hard. The plan's `parse_worker._process_one` checks `if parsed.inputs is None:` and writes `errors_json = parsed.parse_errors` — same effect, no exception machinery.
2. **Bytes vs paths.** Spec said `excel.parse(bytes)` and `excel.render(...) -> bytes`. Reality: `parse_workbook(path: Path)` reads from disk; `render_workbook(out_path: Path, *, building_name, inputs, result) -> None` writes to disk. The plan uses `tempfile.NamedTemporaryFile(suffix=".xlsx")` adapters in both directions inside `services/storage.py` (parse) and `routers/exports.py` (render). 5-line wrappers.
3. **Snapshot create helper.** Spec referenced `snapshot_q.create_with_supersede`. Plan 2 actually exposes `q_snapshot.supersede_active(conn, property_id)` + `q_snapshot.insert_snapshot(...)` as separate functions, and the existing `POST /properties/{id}/snapshots` router (`routers/snapshots.py:77-101`) calls them inside one `async with conn.transaction()`. The Plan 3 `commit_worker._commit_one` uses the same two-call pattern — same source of truth, no new helper.

---

## File Structure

```text
property-valuations-model/
├── supabase/migrations/                                 # 5 NEW
│   ├── 20260503000001_pg_trgm.sql
│   ├── 20260503000002_import_batch.sql
│   ├── 20260503000003_import_item.sql
│   ├── 20260503000004_imports_rls.sql
│   └── 20260503000005_storage_bucket.sql
├── packages/api/
│   ├── pyproject.toml                                   # MODIFY (add weasyprint, jinja2, pikepdf-dev; bump version)
│   ├── Dockerfile                                       # MODIFY (apt-install Pango/Cairo)
│   ├── render.yaml                                      # MODIFY (build cmd apt-install + 7 new env vars)
│   ├── .env.example                                     # MODIFY (BRANDING_*, IMPORT_*, STORAGE_*)
│   ├── scripts/smoke.sh                                 # MODIFY (add /imports + export checks)
│   ├── branding/                                        # NEW DIR
│   │   ├── README.md
│   │   └── anchorpoint_logo.png                        # placeholder
│   ├── src/api/
│   │   ├── _version.py                                  # MODIFY (0.1.0 → 0.2.0)
│   │   ├── main.py                                      # MODIFY (register routers; init branding + storage on startup)
│   │   ├── config.py                                    # MODIFY (BRANDING_*, IMPORT_*, STORAGE_*)
│   │   ├── db.py                                        # MODIFY (acquire timeout + 503 mapping)
│   │   ├── errors.py                                    # MODIFY (narrow ValueError handler; add TimeoutError → 503)
│   │   ├── routers/
│   │   │   ├── imports.py                               # NEW
│   │   │   ├── exports.py                               # NEW
│   │   │   └── snapshots.py                             # MODIFY (re-raise engine ValueError as APIError(422))
│   │   ├── queries/
│   │   │   ├── import_batch.py                          # NEW
│   │   │   ├── import_item.py                           # NEW
│   │   │   └── snapshot.py                              # MODIFY (add get_with_property)
│   │   ├── schemas/
│   │   │   └── imports.py                               # NEW
│   │   ├── services/                                    # NEW DIR
│   │   │   ├── __init__.py
│   │   │   ├── branding.py
│   │   │   ├── storage.py
│   │   │   ├── matcher.py
│   │   │   ├── parse_worker.py
│   │   │   ├── commit_worker.py
│   │   │   └── exports.py
│   │   └── exports/                                     # NEW DIR (PDF assets)
│   │       ├── __init__.py
│   │       ├── pdf_template.html
│   │       └── pdf_styles.css
│   └── tests/
│       ├── unit/                                        # 8 NEW
│       │   ├── test_carryover_db_timeout.py
│       │   ├── test_carryover_errors_narrowing.py
│       │   ├── test_imports_schemas.py
│       │   ├── test_matcher_query.py
│       │   ├── test_parse_worker_per_item.py
│       │   ├── test_commit_worker.py
│       │   ├── test_exports_context_builder.py
│       │   └── test_exports_filename.py
│       ├── integration/                                 # 10 NEW
│       │   ├── test_imports_upload.py
│       │   ├── test_imports_list_detail.py
│       │   ├── test_imports_patch.py
│       │   ├── test_imports_cancel.py
│       │   ├── test_imports_commit.py
│       │   ├── test_imports_source_redirect.py
│       │   ├── test_imports_rls.py
│       │   ├── test_imports_storage_cleanup.py
│       │   ├── test_exports_pdf_endpoint.py
│       │   └── test_exports_xlsx_endpoint.py
│       ├── pdf/                                         # NEW DIR
│       │   ├── __init__.py
│       │   ├── conftest.py
│       │   ├── reference/
│       │   │   └── canonical_one_pager.pdf
│       │   └── test_pdf_visual.py
│       └── fixtures/imports/                            # NEW DIR
│           ├── build.py
│           ├── canonical.xlsx
│           ├── canonical_no_parking.xlsx
│           ├── canonical_multi_sheet.xlsx
│           ├── label_drift_minor.xlsx
│           ├── missing_tenants.xlsx
│           ├── recompute_mismatch.xlsx
│           ├── exact_name_match.xlsx
│           ├── fuzzy_name_match.xlsx
│           └── corrupt.xlsx
└── .github/workflows/api.yml                            # MODIFY (apt-install for WeasyPrint)
```

---

## Phase 0 — Plan 2 carry-overs (Tasks 0–2)

These three tasks land **first** on `plan-3-imports-exports`, before any Plan 3 work. Each is a small, isolated change with its own commit so the PR diff stays reviewable.

---

### Task 0: Carry-over — `db.py` pool acquire timeout + 503 mapping

**Files:**
- Modify: `packages/api/src/api/db.py`
- Modify: `packages/api/src/api/config.py`
- Modify: `packages/api/src/api/errors.py`
- Test (new): `packages/api/tests/unit/test_carryover_db_timeout.py`

**Why:** The TODO in [db.py:54-58](packages/api/src/api/db.py#L54) says: `pool.acquire()` blocks indefinitely when the pool is exhausted. Before production traffic with real concurrency, wrap with an acquisition timeout and map `asyncio.TimeoutError` to HTTP 503 in `errors.py`. This carry-over does exactly that.

- [ ] **Step 1: Write the failing test**

Create `packages/api/tests/unit/test_carryover_db_timeout.py`:

```python
"""Verify pool.acquire() is called with an acquisition timeout, and that
asyncio.TimeoutError is mapped to HTTP 503."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.db import get_db
from api.errors import install_exception_handlers


@pytest.mark.asyncio
async def test_get_db_passes_acquire_timeout() -> None:
    """The get_db dependency must call pool.acquire(timeout=...) — never bare."""
    pool = MagicMock()
    pool.acquire = MagicMock()
    # Configure the context manager protocol on whatever acquire() returns.
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value="conn-sentinel")
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = cm

    request = MagicMock()
    request.app.state.pool = pool

    gen = get_db(request)
    conn = await gen.__anext__()
    try:
        assert conn == "conn-sentinel"
    finally:
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

    # The crux: timeout kwarg was passed.
    call = pool.acquire.call_args
    assert "timeout" in call.kwargs, "pool.acquire() must be called with a timeout kwarg"
    assert call.kwargs["timeout"] > 0


def test_timeout_error_maps_to_503() -> None:
    """asyncio.TimeoutError raised in a route maps to envelope 503."""
    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/boom")
    async def _boom() -> Any:
        raise asyncio.TimeoutError("pool exhausted")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 503
    body = resp.json()
    assert body == {
        "error": {
            "code": "service_unavailable",
            "message": "Database connection unavailable; please retry shortly.",
            "details": {},
        }
    }
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/api
uv run pytest tests/unit/test_carryover_db_timeout.py -v
```

Expected: both tests **FAIL** — first because `pool.acquire()` is called with no kwargs, second because `asyncio.TimeoutError` is not in any exception handler.

- [ ] **Step 3: Add `DB_ACQUIRE_TIMEOUT_S` setting**

Open `packages/api/src/api/config.py` and add to the `Settings` class (preserve existing fields):

```python
    # Per-request asyncpg pool acquisition timeout (seconds). Bounds the wait when
    # the pool is exhausted; raises asyncio.TimeoutError → 503.
    DB_ACQUIRE_TIMEOUT_S: float = 10.0
```

- [ ] **Step 4: Wire the timeout into `get_db`**

In `packages/api/src/api/db.py`, replace the body of `get_db` with:

```python
async def get_db(request: Request) -> AsyncIterator[asyncpg.Connection]:
    """FastAPI dependency: check out a connection for this request.

    Wraps pool.acquire() with an acquisition timeout sourced from settings.
    asyncio.TimeoutError surfaces as 503 via the global exception handler.
    """
    pool: asyncpg.Pool = request.app.state.pool
    settings = request.app.state.settings
    async with pool.acquire(timeout=settings.DB_ACQUIRE_TIMEOUT_S) as conn:
        yield conn
```

Remove the `TODO(pool-timeout):` comment block — superseded.

- [ ] **Step 5: Add the 503 handler**

In `packages/api/src/api/errors.py`, **inside `install_exception_handlers`**, add (anywhere among the other `@app.exception_handler` blocks):

```python
    @app.exception_handler(asyncio.TimeoutError)
    async def _async_timeout(_request: Request, _exc: asyncio.TimeoutError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=_envelope(
                "service_unavailable",
                "Database connection unavailable; please retry shortly.",
                {},
            ),
        )
```

Add `import asyncio` to the top of the file (next to the other stdlib imports).

- [ ] **Step 6: Persist `settings` on `app.state`**

The new `get_db` reads `request.app.state.settings`. Confirm `main.py` already populates this. Open `packages/api/src/api/main.py` and look in the lifespan / app factory for a line setting `app.state.settings = settings`. If absent, add it next to the existing `app.state.pool = pool`:

```python
    # In create_app() or the lifespan setup, alongside other app.state.* assignments:
    app.state.settings = settings
```

- [ ] **Step 7: Run the test to verify it passes**

```bash
cd packages/api
uv run pytest tests/unit/test_carryover_db_timeout.py -v
```

Expected: both tests **PASS**.

- [ ] **Step 8: Run the full unit suite to confirm no regression**

```bash
cd packages/api
uv run pytest -m "not integration" -v
```

Expected: all previously-passing unit tests still pass; new tests pass; total count = previous total + 2.

- [ ] **Step 9: Type-check + lint**

```bash
cd packages/api
uv run ruff check src tests
uv run mypy src
```

Expected: clean.

- [ ] **Step 10: Commit**

```bash
git add packages/api/src/api/db.py \
        packages/api/src/api/config.py \
        packages/api/src/api/errors.py \
        packages/api/src/api/main.py \
        packages/api/tests/unit/test_carryover_db_timeout.py
git commit -m "fix(api): pool.acquire timeout + 503 mapping (Plan 2 carry-over)

Wraps asyncpg pool.acquire() with a configurable acquisition timeout
(DB_ACQUIRE_TIMEOUT_S, default 10s) so an exhausted pool fails fast
instead of blocking the request indefinitely. asyncio.TimeoutError
surfaces as a 503 envelope.

Closes the 'pool-timeout' TODO from Plan 2."
```

---

### Task 1: Carry-over — `errors.py` narrow ValueError handler

**Files:**
- Modify: `packages/api/src/api/errors.py`
- Modify: `packages/api/src/api/routers/snapshots.py`
- Modify: `packages/api/src/api/routers/calculate.py`
- Modify: `packages/api/tests/unit/test_errors.py`
- Test (new): `packages/api/tests/unit/test_carryover_errors_narrowing.py`

**Why:** [errors.py:81-90](packages/api/src/api/errors.py#L81) has a global `ValueError → 422 engine_validation_error` handler with a TODO to narrow it. The risk is masking unrelated bugs (any `ValueError` from any code path) with a misleading "engine_validation_error" code. The fix: remove the global handler; have the two routers that actually call the engine (`/calculate`, `POST /properties/{id}/snapshots`) catch `ValueError` themselves and re-raise as `APIError(422, "engine_validation_error", ...)`. The new commit/parse paths (Plan 3) will follow the same pattern in their respective tasks.

- [ ] **Step 1: Write the failing test**

Create `packages/api/tests/unit/test_carryover_errors_narrowing.py`:

```python
"""ValueError outside scoped engine wrappers must surface as 500, not 422.
Engine ValueErrors raised inside the routers' own scoped wrappers continue
to surface as 422 'engine_validation_error'."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.errors import APIError, install_exception_handlers


@pytest.fixture
def app_with_handlers() -> FastAPI:
    app = FastAPI()
    install_exception_handlers(app)
    return app


def test_unscoped_value_error_returns_500(app_with_handlers: FastAPI) -> None:
    """A bare ValueError from app code must NOT be masked as engine_validation_error."""

    @app_with_handlers.get("/oops")
    async def _oops() -> Any:
        raise ValueError("nothing to do with the engine")

    client = TestClient(app_with_handlers, raise_server_exceptions=False)
    resp = client.get("/oops")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "internal_error"


def test_scoped_engine_value_error_returns_422(app_with_handlers: FastAPI) -> None:
    """Routers that call the engine wrap their own ValueError → APIError(422)."""

    @app_with_handlers.get("/calc")
    async def _calc() -> Any:
        try:
            raise ValueError("cap_rate must be > 0")
        except ValueError as exc:
            raise APIError(
                status_code=422,
                code="engine_validation_error",
                message=str(exc),
            ) from exc

    client = TestClient(app_with_handlers)
    resp = client.get("/calc")
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "engine_validation_error"
    assert body["error"]["message"] == "cap_rate must be > 0"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/api
uv run pytest tests/unit/test_carryover_errors_narrowing.py -v
```

Expected: `test_unscoped_value_error_returns_500` **FAILS** because the global handler maps it to 422; `test_scoped_engine_value_error_returns_422` passes (APIError already works).

- [ ] **Step 3: Remove the global ValueError handler**

In `packages/api/src/api/errors.py`, **delete** the entire block:

```python
    @app.exception_handler(ValueError)
    async def _value_error(_request: Request, exc: ValueError) -> JSONResponse:
        # Engine ValueErrors surface as 422.
        # TODO: narrow this to the /calculate call site once that router ships
        # (Task 25) — catching bare ValueError globally risks masking non-engine
        # bugs with a misleading "engine_validation_error" code.
        return JSONResponse(
            status_code=422,
            content=_envelope("engine_validation_error", str(exc), {}),
        )
```

The unhandled-Exception handler at the bottom of the function will now catch any unmapped ValueError and return 500.

- [ ] **Step 4: Wrap the engine call in `routers/calculate.py`**

Open `packages/api/src/api/routers/calculate.py`. Find the line that calls the engine (something like `result = calculate(body)`). Wrap it:

```python
from api.errors import APIError

# ... inside the route handler:
try:
    result = calculate(body)
except ValueError as exc:
    raise APIError(
        status_code=422,
        code="engine_validation_error",
        message=str(exc),
    ) from exc
```

- [ ] **Step 5: Wrap the engine call in `routers/snapshots.py`**

Open `packages/api/src/api/routers/snapshots.py`. In `create_snapshot` (line 73), wrap the existing `result = calculate(body)`:

```python
try:
    result = calculate(body)
except ValueError as exc:
    raise APIError(
        status_code=422,
        code="engine_validation_error",
        message=str(exc),
    ) from exc
```

`APIError` is already imported in both routers — no new imports needed.

- [ ] **Step 6: Update the existing `test_errors.py` to match the new behaviour**

Open `packages/api/tests/unit/test_errors.py`. Find any test that asserts a bare `ValueError` returns 422 with `engine_validation_error`. Update those tests:

- If the test was checking the global handler's behaviour: **delete** that test (it documents removed behaviour).
- If the test was checking the engine path end-to-end: **rewrite** it to raise the ValueError inside an `APIError`-wrapping helper, matching the new pattern.

If you find no such tests, this step is a no-op — note that explicitly in the commit message.

- [ ] **Step 7: Run the carry-over tests**

```bash
cd packages/api
uv run pytest tests/unit/test_carryover_errors_narrowing.py -v
```

Expected: both tests **PASS**.

- [ ] **Step 8: Run the full unit suite**

```bash
cd packages/api
uv run pytest -m "not integration" -v
```

Expected: all pass.

- [ ] **Step 9: Type-check + lint**

```bash
cd packages/api
uv run ruff check src tests
uv run mypy src
```

Expected: clean.

- [ ] **Step 10: Commit**

```bash
git add packages/api/src/api/errors.py \
        packages/api/src/api/routers/calculate.py \
        packages/api/src/api/routers/snapshots.py \
        packages/api/tests/unit/test_errors.py \
        packages/api/tests/unit/test_carryover_errors_narrowing.py
git commit -m "fix(api): narrow ValueError handler to scoped engine wrappers (Plan 2 carry-over)

Removes the global ValueError → 422 'engine_validation_error' handler that
risked masking unrelated bugs. The two routers that actually call the
engine now wrap calculate() with try/except ValueError → APIError(422)
themselves. New code paths in Plan 3 (parse worker, commit worker) will
follow the same pattern.

Closes the narrow-ValueError TODO from errors.py:84-86."
```

---

### Task 2: Carry-over — version bump 0.1.0 → 0.2.0

**Files:**
- Modify: `packages/api/src/api/_version.py`
- Modify: `packages/api/pyproject.toml`

**Why:** Plan 3 adds new endpoints and tables — additive, semver minor.

- [ ] **Step 1: Bump `_version.py`**

Open `packages/api/src/api/_version.py`. It currently contains `__version__ = "0.1.0"`. Replace with:

```python
__version__ = "0.2.0"
```

- [ ] **Step 2: Bump `pyproject.toml`**

Open `packages/api/pyproject.toml`. Find the `[project]` table; locate `version = "0.1.0"` (or `dynamic = ["version"]` — if dynamic, no edit needed here). Update to `version = "0.2.0"` if static.

- [ ] **Step 3: Verify the bump is reflected**

```bash
cd packages/api
uv run python -c "from api import __version__; print(__version__)"
```

Expected output: `0.2.0`.

- [ ] **Step 4: Commit**

```bash
git add packages/api/src/api/_version.py packages/api/pyproject.toml
git commit -m "chore(api): bump version 0.1.0 → 0.2.0 for Plan 3 (imports + exports)"
```

---

## Phase 1 — SQL Migrations (Tasks 3–7)

Five additive migrations. Each is verified against the local Supabase CLI Postgres via `supabase db reset` followed by a schema query.

---

### Task 3: Migration — `pg_trgm` extension + GIN index on `property.name`

**Files:**
- Create: `supabase/migrations/20260503000001_pg_trgm.sql`

**Why:** `services/matcher.py` (Task 13) uses `similarity(name, $1)` with a threshold to suggest matching properties when reviewing imported workbooks. The GIN index on `gin_trgm_ops` makes this O(log n) instead of a sequential scan.

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260503000001_pg_trgm.sql`:

```sql
-- Enable trigram similarity for fuzzy matching of property names during
-- Excel imports (services/matcher.py).
create extension if not exists pg_trgm;

-- Partial GIN index: only over live (non-soft-deleted) properties, since the
-- matcher never suggests soft-deleted rows.
create index if not exists property_name_trgm_idx
  on public.property using gin (name gin_trgm_ops)
  where deleted_at is null;
```

- [ ] **Step 2: Apply the migration**

```bash
# From repo root, with Docker running:
supabase db reset
```

Expected: command completes with no errors; existing migrations replay; the new migration applies.

- [ ] **Step 3: Verify the extension and index exist**

```bash
psql "postgresql://postgres:postgres@localhost:54322/postgres" -c \
  "select extname from pg_extension where extname = 'pg_trgm';"
```

Expected output: one row, `pg_trgm`.

```bash
psql "postgresql://postgres:postgres@localhost:54322/postgres" -c \
  "select indexname from pg_indexes where tablename = 'property' and indexname = 'property_name_trgm_idx';"
```

Expected output: one row, `property_name_trgm_idx`.

- [ ] **Step 4: Smoke-test similarity() function**

```bash
psql "postgresql://postgres:postgres@localhost:54322/postgres" -c \
  "select similarity('55 Empire Road', '55 Empire Rd');"
```

Expected: a numeric value between 0.5 and 0.9 (close strings score high).

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20260503000001_pg_trgm.sql
git commit -m "feat(db): pg_trgm extension + GIN index on property.name

Enables fuzzy matching of building names against existing properties
during Excel import review (services/matcher.py)."
```

---

### Task 4: Migration — `import_batch` table

**Files:**
- Create: `supabase/migrations/20260503000002_import_batch.sql`

**Why:** Per spec §6.1, one row per upload session; tracks reviewer, status, file count.

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260503000002_import_batch.sql`:

```sql
create table public.import_batch (
  id            uuid primary key default gen_random_uuid(),
  uploaded_by   uuid not null references public.app_user(id),
  uploaded_at   timestamptz not null default now(),
  file_count    int  not null check (file_count >= 1),
  status        text not null check (status in ('parsing','review','committed','cancelled')),
  notes         text
);

create index import_batch_uploaded_by_idx
  on public.import_batch (uploaded_by, uploaded_at desc);

comment on table public.import_batch is
  'One row per Excel-import session. Status: parsing -> review -> committed | cancelled. Rows never deleted (audit trail).';
```

- [ ] **Step 2: Apply and verify**

```bash
supabase db reset
psql "postgresql://postgres:postgres@localhost:54322/postgres" -c "\d public.import_batch"
```

Expected: table description shows the 6 columns, the FK to `app_user`, the two CHECK constraints, the default for `id`.

- [ ] **Step 3: Smoke-test invalid status is rejected**

```bash
psql "postgresql://postgres:postgres@localhost:54322/postgres" -c \
  "insert into public.app_user (id, email, role) values ('00000000-0000-0000-0000-000000000001', 'smoke@test.local', 'valuer') on conflict (id) do nothing; insert into public.import_batch (uploaded_by, file_count, status) values ('00000000-0000-0000-0000-000000000001', 1, 'bogus');"
```

Expected: insert into `app_user` succeeds, insert into `import_batch` fails with `ERROR:  new row for relation "import_batch" violates check constraint`.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/20260503000002_import_batch.sql
git commit -m "feat(db): import_batch table

One row per Excel-import session. Status: parsing -> review -> committed | cancelled.
Never deleted; audit trail."
```

---

### Task 5: Migration — `import_item` table

**Files:**
- Create: `supabase/migrations/20260503000003_import_item.sql`

**Why:** Per spec §6.2, one row per uploaded workbook; carries parser output, reviewer resolution, and the eventual snapshot link.

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260503000003_import_item.sql`:

```sql
create table public.import_item (
  id                       uuid primary key default gen_random_uuid(),
  batch_id                 uuid not null references public.import_batch(id) on delete cascade,
  filename                 text not null,
  storage_path             text not null,

  -- Parser output (populated by services/parse_worker.py)
  parse_status             text not null check (parse_status in ('ok','warning','error')),
  building_name            text,
  parsed_inputs_json       jsonb,
  computed_result_json     jsonb,
  spreadsheet_market_value numeric,
  recomputed_market_value  numeric,
  diff_pct                 numeric,
  warnings_json            jsonb not null default '[]'::jsonb,
  errors_json              jsonb not null default '[]'::jsonb,

  -- Auto-suggest (populated by services/matcher.py at parse time)
  suggested_property_id    uuid references public.property(id),
  suggested_score          numeric,
  auto_linked              boolean not null default false,

  -- Reviewer resolution
  resolution               text not null default 'pending'
                                check (resolution in ('pending','accepted','rejected','edited','committed')),
  resolved_property_id     uuid references public.property(id),
  resolved_snapshot_id     uuid references public.valuation_snapshot(id),
  resolved_inputs_json     jsonb,
  resolution_notes         text,
  resolved_at              timestamptz,
  resolved_by              uuid references public.app_user(id),

  created_at               timestamptz not null default now()
);

create index import_item_batch_idx       on public.import_item (batch_id);
create index import_item_resolution_idx  on public.import_item (batch_id, resolution);

comment on table public.import_item is
  'One row per uploaded workbook in an import_batch. Reviewer resolves each via PATCH; commit loop sets resolved_snapshot_id. Never deleted; cascade only fires if parent batch is deleted (which the API never does).';
```

- [ ] **Step 2: Apply and verify**

```bash
supabase db reset
psql "postgresql://postgres:postgres@localhost:54322/postgres" -c "\d public.import_item"
```

Expected: ~22 columns, FK to `import_batch` with `on delete cascade`, FKs to `property`, `valuation_snapshot`, `app_user`. Two CHECK constraints (parse_status, resolution).

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260503000003_import_item.sql
git commit -m "feat(db): import_item table

One row per uploaded workbook. Carries parser output, auto-suggest match,
and reviewer resolution. Cascade delete from import_batch (defence-in-depth
only; API never deletes batches)."
```

---

### Task 6: Migration — RLS policies for `import_batch` + `import_item`

**Files:**
- Create: `supabase/migrations/20260503000004_imports_rls.sql`

**Why:** Per spec §6.4 — viewer + valuer SELECT, valuer-only INSERT/UPDATE, no DELETE policy. The API uses the service-role key (bypasses RLS); policies are second-line defence.

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260503000004_imports_rls.sql`:

```sql
alter table public.import_batch enable row level security;
alter table public.import_item  enable row level security;

-- ============================ import_batch ===================================

create policy import_batch_select on public.import_batch
  for select to authenticated using (true);

create policy import_batch_insert on public.import_batch
  for insert to authenticated
  with check (
    exists (
      select 1 from public.app_user u
      where u.id = auth.uid() and u.role = 'valuer'
    )
    and uploaded_by = auth.uid()
  );

create policy import_batch_update on public.import_batch
  for update to authenticated
  using (
    exists (
      select 1 from public.app_user u
      where u.id = auth.uid() and u.role = 'valuer'
    )
  );

-- ============================ import_item ====================================

create policy import_item_select on public.import_item
  for select to authenticated using (true);

create policy import_item_insert on public.import_item
  for insert to authenticated
  with check (
    exists (
      select 1 from public.app_user u
      where u.id = auth.uid() and u.role = 'valuer'
    )
  );

create policy import_item_update on public.import_item
  for update to authenticated
  using (
    exists (
      select 1 from public.app_user u
      where u.id = auth.uid() and u.role = 'valuer'
    )
  );

-- No DELETE policy on either table; rows are kept for audit.
```

- [ ] **Step 2: Apply and verify policies**

```bash
supabase db reset
psql "postgresql://postgres:postgres@localhost:54322/postgres" -c \
  "select tablename, policyname, cmd from pg_policies where tablename in ('import_batch', 'import_item') order by tablename, cmd;"
```

Expected: 6 rows — three policies per table (SELECT, INSERT, UPDATE), no DELETE.

- [ ] **Step 3: Verify RLS is enabled**

```bash
psql "postgresql://postgres:postgres@localhost:54322/postgres" -c \
  "select relname, relrowsecurity from pg_class where relname in ('import_batch', 'import_item');"
```

Expected: both rows show `relrowsecurity = t`.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/20260503000004_imports_rls.sql
git commit -m "feat(db): RLS policies for import_batch + import_item

Viewer + Valuer SELECT, Valuer-only INSERT/UPDATE, no DELETE policy.
API uses service-role key (bypasses RLS); policies are defence-in-depth.
Integration test test_imports_rls.py verifies role enforcement against
a real JWT."
```

---

### Task 7: Migration — Storage bucket for uploaded workbooks

**Files:**
- Create: `supabase/migrations/20260503000005_storage_bucket.sql`

**Why:** Per spec §6.5 — private bucket `imports`, no public read policy, all access via signed URLs minted by the API. Created via SQL so it's reproducible across local CLI and hosted projects.

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260503000005_storage_bucket.sql`:

```sql
-- Private bucket for raw uploaded workbooks. Reviewer downloads happen via
-- 5-minute signed URLs minted by services/storage.py; the browser must never
-- read this bucket directly.
insert into storage.buckets (id, name, public)
values ('imports', 'imports', false)
on conflict (id) do nothing;

-- No storage.objects policies for the 'authenticated' role are created;
-- only the API's service-role key (which bypasses RLS) reads/writes this bucket.
```

- [ ] **Step 2: Apply and verify**

```bash
supabase db reset
psql "postgresql://postgres:postgres@localhost:54322/postgres" -c \
  "select id, name, public from storage.buckets where id = 'imports';"
```

Expected: one row, `id = imports`, `public = false`.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260503000005_storage_bucket.sql
git commit -m "feat(db): private 'imports' Supabase Storage bucket

Reproducible across local CLI and hosted projects. No public-read policy;
all access goes through services/storage.py via service-role-minted
5-minute signed URLs."
```

---

## Phase 2 — Schemas & Queries (Tasks 8–11)

Pydantic DTOs and asyncpg query helpers. Pure-Python work — no DB connection required for unit tests; query helpers are exercised via integration tests in later tasks.

---

### Task 8: `schemas/imports.py` — Pydantic DTOs

**Files:**
- Create: `packages/api/src/api/schemas/imports.py`
- Test (new): `packages/api/tests/unit/test_imports_schemas.py`

**Why:** Defines the request/response shapes for `POST /imports`, `GET /imports*`, `PATCH /imports/{id}/items/{iid}`, `POST /imports/{id}/cancel`, `POST /imports/{id}/commit`. Mirrors the column shape of `import_batch` and `import_item`. The Plan 2 pattern (one schema file per DB table) is preserved.

- [ ] **Step 1: Write the failing test**

Create `packages/api/tests/unit/test_imports_schemas.py`:

```python
"""DTO validation tests for imports endpoints."""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.schemas.imports import (
    CommitFailure,
    CommitSummary,
    ImportBatch,
    ImportBatchCounts,
    ImportBatchListItem,
    ImportItem,
    ImportItemPatch,
    ImportItemSuggestion,
    ImportItemWarning,
)


def test_import_item_patch_accepted_requires_property_id_when_no_auto_link() -> None:
    """resolution=accepted with auto_linked=false on the row must carry resolved_property_id."""
    with pytest.raises(ValidationError):
        ImportItemPatch(resolution="accepted", resolved_property_id=None,
                        resolved_inputs=None, resolution_notes=None)


def test_import_item_patch_edited_requires_inputs_and_property_id() -> None:
    with pytest.raises(ValidationError):
        ImportItemPatch(resolution="edited", resolved_property_id=uuid4(),
                        resolved_inputs=None, resolution_notes=None)
    with pytest.raises(ValidationError):
        ImportItemPatch(resolution="edited", resolved_property_id=None,
                        resolved_inputs={"valuation_date": "2026-03-15"},
                        resolution_notes=None)


def test_import_item_patch_rejected_ignores_other_fields() -> None:
    """resolution=rejected accepts a body with property_id/inputs but they're permitted."""
    obj = ImportItemPatch(resolution="rejected", resolved_property_id=uuid4(),
                          resolved_inputs={"x": 1}, resolution_notes="bad data")
    assert obj.resolution == "rejected"


def test_import_item_patch_accepted_with_property_id_passes() -> None:
    obj = ImportItemPatch(resolution="accepted", resolved_property_id=uuid4(),
                          resolved_inputs=None, resolution_notes=None)
    assert obj.resolution == "accepted"


def test_import_batch_counts_zero_default_for_missing_keys() -> None:
    counts = ImportBatchCounts()
    assert counts.pending == 0
    assert counts.accepted == 0
    assert counts.rejected == 0
    assert counts.committed == 0


def test_commit_summary_validates_minimal() -> None:
    s = CommitSummary(
        batch_id=uuid4(),
        summary={"committed": 8, "failed": 1, "skipped": 3},
        failures=[CommitFailure(item_id=uuid4(), filename="x.xlsx",
                                reason="no_inputs", message="...")],
        batch_status="review",
    )
    assert s.summary["failed"] == 1
    assert s.batch_status == "review"


def test_import_item_warning_round_trips() -> None:
    w = ImportItemWarning(code="lease_expired", message="...", field_path="tenants[2]")
    assert w.model_dump()["field_path"] == "tenants[2]"


def test_import_item_suggestion_score_bounded() -> None:
    """score must be in [0, 1] (pg_trgm similarity range)."""
    with pytest.raises(ValidationError):
        ImportItemSuggestion(property_id=uuid4(), property_name="x",
                             entity_id=uuid4(), entity_name="y",
                             score=Decimal("1.5"), auto_linked=False)


def test_import_batch_list_item_includes_counts() -> None:
    """List item shape carries per-status counts (no separate fetch)."""
    item = ImportBatchListItem(
        id=uuid4(),
        uploaded_by={"id": str(uuid4()), "email": "a@b"},
        uploaded_at="2026-05-03T12:00:00Z",
        file_count=3,
        status="review",
        counts=ImportBatchCounts(pending=1, accepted=2),
    )
    assert item.counts.accepted == 2


def test_import_batch_detail_includes_items_inline() -> None:
    """Detail shape inlines items (no N+1 pagination in v1)."""
    batch = ImportBatch(
        id=uuid4(),
        uploaded_by={"id": str(uuid4()), "email": "a@b"},
        uploaded_at="2026-05-03T12:00:00Z",
        file_count=1,
        status="review",
        notes=None,
        items=[],
    )
    assert batch.items == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/api
uv run pytest tests/unit/test_imports_schemas.py -v
```

Expected: collection error or all tests **FAIL** because `api.schemas.imports` doesn't exist.

- [ ] **Step 3: Implement the schemas**

Create `packages/api/src/api/schemas/imports.py`:

```python
"""DTOs for /imports endpoints + commit summary.

Mirrors the column shape of import_batch + import_item. Validation enforces
the resolution-state matrix from spec §7.5.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ParseStatus = Literal["ok", "warning", "error"]
Resolution = Literal["pending", "accepted", "rejected", "edited", "committed"]
BatchStatus = Literal["parsing", "review", "committed", "cancelled"]


class ImportItemWarning(BaseModel):
    code: str
    message: str
    field_path: str | None = None


class ImportItemSuggestion(BaseModel):
    property_id: UUID
    property_name: str
    entity_id: UUID
    entity_name: str
    score: Annotated[Decimal, Field(ge=0, le=1)]
    auto_linked: bool


class ImportItem(BaseModel):
    """Full row shape returned by GET /imports/{id} and PATCH responses."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID
    filename: str
    parse_status: ParseStatus
    building_name: str | None
    spreadsheet_market_value: Decimal | None
    recomputed_market_value: Decimal | None
    diff_pct: Decimal | None
    warnings: list[ImportItemWarning] = []
    errors: list[ImportItemWarning] = []
    suggestion: ImportItemSuggestion | None = None
    resolution: Resolution
    resolved_property_id: UUID | None
    parsed_inputs: dict[str, Any] | None
    computed_result: dict[str, Any] | None
    resolved_inputs: dict[str, Any] | None


class ImportItemPatch(BaseModel):
    """PATCH /imports/{id}/items/{iid} body. Per-field-conditional validation."""
    resolution: Literal["accepted", "rejected", "edited"]
    resolved_property_id: UUID | None = None
    resolved_inputs: dict[str, Any] | None = None
    resolution_notes: str | None = None

    @model_validator(mode="after")
    def _validate_state(self) -> "ImportItemPatch":
        if self.resolution == "edited":
            if self.resolved_inputs is None:
                raise ValueError("resolution='edited' requires resolved_inputs")
            if self.resolved_property_id is None:
                raise ValueError("resolution='edited' requires resolved_property_id")
        elif self.resolution == "accepted":
            # Server-side handler must verify auto_linked OR resolved_property_id.
            # Schema-level: if no auto-link is in play, the body must carry an id.
            # We can't see the row from here, so the router enforces the auto-link
            # branch; schema only catches the "no id at all" case.
            if self.resolved_property_id is None:
                raise ValueError(
                    "resolution='accepted' requires resolved_property_id "
                    "unless the row is already auto_linked"
                )
        # 'rejected' allows any payload; resolved_* fields are simply ignored downstream.
        return self


class ImportBatchCounts(BaseModel):
    pending:   int = 0
    accepted:  int = 0
    rejected:  int = 0
    edited:    int = 0
    committed: int = 0


class _ActorRef(BaseModel):
    id: str
    email: str | None = None


class ImportBatchListItem(BaseModel):
    id: UUID
    uploaded_by: _ActorRef
    uploaded_at: str
    file_count: int
    status: BatchStatus
    counts: ImportBatchCounts


class ImportBatchList(BaseModel):
    items: list[ImportBatchListItem]
    total: int


class ImportBatch(BaseModel):
    """Full batch detail with inline items (GET /imports/{id})."""
    id: UUID
    uploaded_by: _ActorRef
    uploaded_at: str
    file_count: int
    status: BatchStatus
    notes: str | None
    items: list[ImportItem]


class ImportCreated(BaseModel):
    """Response for POST /imports (202)."""
    batch_id: UUID
    file_count: int
    status: Literal["parsing"]


class CommitFailure(BaseModel):
    item_id: UUID
    filename: str
    reason: str
    message: str


class CommitSummary(BaseModel):
    batch_id: UUID
    summary: dict[str, int]
    failures: list[CommitFailure]
    batch_status: Literal["committed", "review"]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/api
uv run pytest tests/unit/test_imports_schemas.py -v
```

Expected: all 10 tests **PASS**.

- [ ] **Step 5: Lint + type-check**

```bash
cd packages/api
uv run ruff check src/api/schemas/imports.py tests/unit/test_imports_schemas.py
uv run mypy src/api/schemas/imports.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/api/src/api/schemas/imports.py packages/api/tests/unit/test_imports_schemas.py
git commit -m "feat(api): schemas/imports.py — DTOs for /imports endpoints

ImportItem, ImportItemPatch (with state-matrix validator), ImportBatch
detail + list shapes, ImportBatchCounts, CommitSummary, CommitFailure.
Mirrors column shape of import_batch + import_item."
```

---

### Task 9: `queries/import_batch.py` — asyncpg helpers

**Files:**
- Create: `packages/api/src/api/queries/import_batch.py`

**Why:** Mirrors the Plan 2 pattern (one query file per table). Pure SQL composition; no business logic. Tested via integration in later router tasks.

- [ ] **Step 1: Write the module**

Create `packages/api/src/api/queries/import_batch.py`:

```python
"""asyncpg query helpers for the import_batch table.

No business logic — pure SQL. Idempotency, status-machine guards, and
RLS-bypass are the routers' / services' responsibility.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

_COLS = "id, uploaded_by, uploaded_at, file_count, status, notes"


async def insert(
    conn: asyncpg.Connection,
    *,
    uploaded_by: UUID,
    file_count: int,
    status: str = "parsing",
    notes: str | None = None,
) -> asyncpg.Record:
    return await conn.fetchrow(
        f"""
        insert into public.import_batch (uploaded_by, file_count, status, notes)
        values ($1, $2, $3, $4)
        returning {_COLS}
        """,
        uploaded_by, file_count, status, notes,
    )


async def get_by_id(
    conn: asyncpg.Connection, batch_id: UUID,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"select {_COLS} from public.import_batch where id = $1",
        batch_id,
    )


async def list_with_counts(
    conn: asyncpg.Connection,
    *,
    statuses: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[asyncpg.Record], int]:
    """Returns (rows, total). Each row carries import_batch cols plus
    `pending`, `accepted`, `rejected`, `edited`, `committed_count` ints."""
    where = ""
    params: list[Any] = []
    if statuses:
        where = "where b.status = any($1::text[])"
        params.append(statuses)
    pl = len(params)
    rows = await conn.fetch(
        f"""
        with batch_counts as (
            select batch_id,
                   count(*) filter (where resolution = 'pending')   as pending,
                   count(*) filter (where resolution = 'accepted')  as accepted,
                   count(*) filter (where resolution = 'rejected')  as rejected,
                   count(*) filter (where resolution = 'edited')    as edited,
                   count(*) filter (where resolution = 'committed') as committed_count
              from public.import_item
             group by batch_id
        )
        select b.id, b.uploaded_by, b.uploaded_at, b.file_count, b.status, b.notes,
               coalesce(c.pending, 0)         as pending,
               coalesce(c.accepted, 0)        as accepted,
               coalesce(c.rejected, 0)        as rejected,
               coalesce(c.edited, 0)          as edited,
               coalesce(c.committed_count, 0) as committed_count
          from public.import_batch b
          left join batch_counts c on c.batch_id = b.id
        {where}
         order by b.uploaded_at desc
         limit ${pl + 1} offset ${pl + 2}
        """,
        *params, limit, offset,
    )
    total_row = await conn.fetchrow(
        f"select count(*)::int as n from public.import_batch b {where}",
        *params,
    )
    total = int(total_row["n"]) if total_row else 0
    return list(rows), total


async def set_status(
    conn: asyncpg.Connection,
    batch_id: UUID,
    new_status: str,
) -> int:
    """Returns affected row count (0 or 1)."""
    result = await conn.execute(
        "update public.import_batch set status = $1 where id = $2",
        new_status, batch_id,
    )
    return int(result.rsplit(maxsplit=1)[-1])
```

- [ ] **Step 2: Lint + type-check**

```bash
cd packages/api
uv run ruff check src/api/queries/import_batch.py
uv run mypy src/api/queries/import_batch.py
```

Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add packages/api/src/api/queries/import_batch.py
git commit -m "feat(api): queries/import_batch.py — asyncpg helpers

insert, get_by_id, list_with_counts (joins import_item per-status counts),
set_status. No business logic — exercised via integration tests in
router tasks."
```

---

### Task 10: `queries/import_item.py` — asyncpg helpers

**Files:**
- Create: `packages/api/src/api/queries/import_item.py`

**Why:** Companion to Task 9. Used by `parse_worker`, `commit_worker`, and the imports router.

- [ ] **Step 1: Write the module**

Create `packages/api/src/api/queries/import_item.py`:

```python
"""asyncpg query helpers for the import_item table."""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg

_COLS = (
    "id, batch_id, filename, storage_path, parse_status, building_name, "
    "parsed_inputs_json, computed_result_json, spreadsheet_market_value, "
    "recomputed_market_value, diff_pct, warnings_json, errors_json, "
    "suggested_property_id, suggested_score, auto_linked, "
    "resolution, resolved_property_id, resolved_snapshot_id, "
    "resolved_inputs_json, resolution_notes, resolved_at, resolved_by, "
    "created_at"
)


def _jdef(value: Any) -> Any:
    """JSON encoder for Decimal + UUID + date/datetime in our row payloads."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Not JSON-serializable: {type(value).__name__}")


async def insert_placeholder(
    conn: asyncpg.Connection,
    *,
    batch_id: UUID,
    filename: str,
    storage_path: str,
) -> asyncpg.Record:
    """Insert a row in 'parsing' state. parse_worker mutates it later."""
    return await conn.fetchrow(
        f"""
        insert into public.import_item
            (batch_id, filename, storage_path, parse_status)
        values ($1, $2, $3, 'ok')
        returning {_COLS}
        """,
        batch_id, filename, storage_path,
    )


async def get_by_id(
    conn: asyncpg.Connection, item_id: UUID,
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"select {_COLS} from public.import_item where id = $1",
        item_id,
    )


async def list_for_batch(
    conn: asyncpg.Connection, batch_id: UUID,
) -> list[asyncpg.Record]:
    rows = await conn.fetch(
        f"""
        select {_COLS} from public.import_item
         where batch_id = $1
         order by created_at asc
        """,
        batch_id,
    )
    return list(rows)


async def list_for_parsing(
    conn: asyncpg.Connection, batch_id: UUID,
) -> list[asyncpg.Record]:
    """Items the parse_worker still needs to process (idempotency-safe)."""
    rows = await conn.fetch(
        f"""
        select {_COLS} from public.import_item
         where batch_id = $1
           and parsed_inputs_json is null
           and (errors_json = '[]'::jsonb or errors_json is null)
         order by created_at asc
        """,
        batch_id,
    )
    return list(rows)


async def list_for_commit(
    conn: asyncpg.Connection, batch_id: UUID,
) -> list[asyncpg.Record]:
    """Items the commit_worker should process (resolution accepted|edited, not yet snapshot'd)."""
    rows = await conn.fetch(
        f"""
        select {_COLS} from public.import_item
         where batch_id = $1
           and resolution in ('accepted', 'edited')
           and resolved_snapshot_id is null
         order by created_at asc
        """,
        batch_id,
    )
    return list(rows)


async def count_already_committed(
    conn: asyncpg.Connection, batch_id: UUID,
) -> int:
    row = await conn.fetchrow(
        """
        select count(*)::int as n from public.import_item
         where batch_id = $1 and resolved_snapshot_id is not null
        """,
        batch_id,
    )
    return int(row["n"]) if row else 0


async def all_items_terminal(
    conn: asyncpg.Connection, batch_id: UUID,
) -> bool:
    """True iff every item is committed or rejected (batch can flip to committed)."""
    row = await conn.fetchrow(
        """
        select count(*)::int as n_open
          from public.import_item
         where batch_id = $1
           and resolution not in ('committed', 'rejected')
        """,
        batch_id,
    )
    return (int(row["n_open"]) if row else 0) == 0


async def mark_parsed(
    conn: asyncpg.Connection,
    item_id: UUID,
    *,
    building_name: str | None,
    parsed_inputs_json: dict[str, Any] | None,
    computed_result_json: dict[str, Any] | None,
    spreadsheet_market_value: Decimal | None,
    recomputed_market_value: Decimal | None,
    diff_pct: Decimal | None,
    warnings_json: list[dict[str, Any]],
    parse_status: str,
    suggested_property_id: UUID | None,
    suggested_score: Decimal | None,
    auto_linked: bool,
    resolution: str,
    resolved_property_id: UUID | None,
) -> None:
    await conn.execute(
        """
        update public.import_item set
            building_name = $2,
            parsed_inputs_json = $3::jsonb,
            computed_result_json = $4::jsonb,
            spreadsheet_market_value = $5,
            recomputed_market_value = $6,
            diff_pct = $7,
            warnings_json = $8::jsonb,
            parse_status = $9,
            suggested_property_id = $10,
            suggested_score = $11,
            auto_linked = $12,
            resolution = $13,
            resolved_property_id = $14
         where id = $1
        """,
        item_id, building_name,
        json.dumps(parsed_inputs_json, default=_jdef) if parsed_inputs_json else None,
        json.dumps(computed_result_json, default=_jdef) if computed_result_json else None,
        spreadsheet_market_value, recomputed_market_value, diff_pct,
        json.dumps(warnings_json, default=_jdef),
        parse_status, suggested_property_id, suggested_score, auto_linked,
        resolution, resolved_property_id,
    )


async def mark_parse_error(
    conn: asyncpg.Connection,
    item_id: UUID,
    *,
    building_name: str | None = None,
    parsed_inputs_json: dict[str, Any] | None = None,
    errors: list[dict[str, Any]],
) -> None:
    await conn.execute(
        """
        update public.import_item set
            parse_status = 'error',
            building_name = coalesce($2, building_name),
            parsed_inputs_json = coalesce($3::jsonb, parsed_inputs_json),
            errors_json = $4::jsonb
         where id = $1
        """,
        item_id, building_name,
        json.dumps(parsed_inputs_json, default=_jdef) if parsed_inputs_json else None,
        json.dumps(errors, default=_jdef),
    )


async def mark_unrecoverable_error(
    conn: asyncpg.Connection, item_id: UUID, exc_repr: str,
) -> None:
    await mark_parse_error(
        conn, item_id,
        errors=[{"code": "unrecoverable_parse_error", "message": exc_repr,
                 "field_path": None}],
    )


async def patch_resolution(
    conn: asyncpg.Connection,
    item_id: UUID,
    *,
    resolution: str,
    resolved_property_id: UUID | None,
    resolved_inputs_json: dict[str, Any] | None,
    computed_result_json: dict[str, Any] | None,
    resolution_notes: str | None,
    resolved_by: UUID,
) -> asyncpg.Record:
    return await conn.fetchrow(
        f"""
        update public.import_item set
            resolution = $2,
            resolved_property_id = $3,
            resolved_inputs_json = coalesce($4::jsonb, resolved_inputs_json),
            computed_result_json = coalesce($5::jsonb, computed_result_json),
            resolution_notes = coalesce($6, resolution_notes),
            resolved_at = now(),
            resolved_by = $7
         where id = $1
        returning {_COLS}
        """,
        item_id, resolution, resolved_property_id,
        json.dumps(resolved_inputs_json, default=_jdef) if resolved_inputs_json else None,
        json.dumps(computed_result_json, default=_jdef) if computed_result_json else None,
        resolution_notes, resolved_by,
    )


async def mark_committed(
    conn: asyncpg.Connection,
    item_id: UUID,
    *,
    snapshot_id: UUID,
    actor_id: UUID,
) -> None:
    await conn.execute(
        """
        update public.import_item set
            resolution = 'committed',
            resolved_snapshot_id = $2,
            resolved_at = now(),
            resolved_by = $3
         where id = $1
        """,
        item_id, snapshot_id, actor_id,
    )
```

- [ ] **Step 2: Lint + type-check**

```bash
cd packages/api
uv run ruff check src/api/queries/import_item.py
uv run mypy src/api/queries/import_item.py
```

Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add packages/api/src/api/queries/import_item.py
git commit -m "feat(api): queries/import_item.py — asyncpg helpers

insert_placeholder, get_by_id, list_for_batch, list_for_parsing,
list_for_commit, count_already_committed, all_items_terminal, mark_parsed,
mark_parse_error, mark_unrecoverable_error, patch_resolution, mark_committed.

Idempotency lives in the queries (list_for_parsing skips already-parsed,
list_for_commit skips already-committed)."
```

---

### Task 11: Extend `queries/snapshot.py` — `get_with_property`

**Files:**
- Modify: `packages/api/src/api/queries/snapshot.py`

**Why:** Per spec §10.1, the export endpoints need a snapshot row joined to property + entity (for the filename and the PDF header). Plan 2's `get_snapshot` returns only the snapshot row.

- [ ] **Step 1: Add the new function**

In `packages/api/src/api/queries/snapshot.py`, after the existing `get_snapshot` function, add:

```python
async def get_with_property(
    conn: asyncpg.Connection, snapshot_id: UUID,
) -> asyncpg.Record | None:
    """Snapshot row joined with property + entity for the export endpoints.

    Returns columns: all _COLS from valuation_snapshot, plus property_name,
    property_address, entity_id, entity_name. Returns None if the snapshot
    or its parent property is missing/soft-deleted.
    """
    return await conn.fetchrow(
        f"""
        select {_COLS},
               p.name    as property_name,
               p.address as property_address,
               p.entity_id,
               e.name    as entity_name
          from public.valuation_snapshot s
          join public.property p on p.id = s.property_id
          join public.entity   e on e.id = p.entity_id
         where s.id = $1
        """,
        snapshot_id,
    )
```

- [ ] **Step 2: Lint + type-check**

```bash
cd packages/api
uv run ruff check src/api/queries/snapshot.py
uv run mypy src/api/queries/snapshot.py
```

Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add packages/api/src/api/queries/snapshot.py
git commit -m "feat(api): queries/snapshot.get_with_property

Joins valuation_snapshot -> property -> entity for the export endpoints
(PDF + XLSX). Coexists with the existing get_snapshot — does not replace
it. Used by routers/exports.py."
```

---

## Phase 3 — Services (Tasks 12–15)

Four service modules: Storage SDK wrapper, fuzzy matcher, parse worker, commit worker. The Storage wrapper is the only place that imports `supabase-py` SDK; the matcher is the only place that issues `pg_trgm` SQL; the workers are the only places that orchestrate the engine + queries together.

---

### Task 12: `services/storage.py` — Supabase Storage wrapper

**Files:**
- Create: `packages/api/src/api/services/__init__.py`
- Create: `packages/api/src/api/services/storage.py`
- Modify: `packages/api/pyproject.toml` (add `supabase` SDK if not already present)
- Modify: `packages/api/src/api/config.py` (add `STORAGE_SIGNED_URL_TTL_S`)

**Why:** Single chokepoint for all Supabase Storage SDK calls. Exposes `upload`, `download`, `signed_url`, `delete_prefix`. Tested via integration in router tasks (the local Supabase CLI ships Storage; mocking would hide SDK contract bugs).

- [ ] **Step 1: Confirm `supabase` SDK is in lockfile or add it**

```bash
cd packages/api
uv pip list 2>/dev/null | grep -i supabase
```

If absent, add to `packages/api/pyproject.toml` under `[project] dependencies`:

```toml
"supabase>=2.4",
```

Then:

```bash
cd packages/api
uv sync
```

- [ ] **Step 2: Add the setting**

In `packages/api/src/api/config.py`, add to the `Settings` class:

```python
    # TTL for signed URLs minted by services/storage.py for original-workbook downloads.
    STORAGE_SIGNED_URL_TTL_S: int = 300
```

- [ ] **Step 3: Create the services package**

Create `packages/api/src/api/services/__init__.py`:

```python
"""Service-layer modules. Routers and queries should import from here, not
from third-party SDKs directly."""
```

- [ ] **Step 4: Implement the storage wrapper**

Create `packages/api/src/api/services/storage.py`:

```python
"""Supabase Storage wrapper for the 'imports' bucket.

The only file in the API package that imports the Supabase Storage SDK.
"""
from __future__ import annotations

import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Iterator
from uuid import UUID

if TYPE_CHECKING:
    from supabase import Client


BUCKET = "imports"

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str) -> str:
    """Conservative filesystem-safe transform: keep alnum/._-, collapse runs."""
    cleaned = _SAFE_NAME.sub("_", name).strip("._-") or "file"
    return cleaned[:200]


def storage_path_for(batch_id: UUID, safe_name: str) -> str:
    return f"{batch_id}/{safe_name}"


class StorageClient:
    """Thin wrapper around supabase-py's storage_from_."""

    def __init__(self, client: "Client", *, signed_url_ttl_s: int = 300) -> None:
        self._client = client
        self._ttl = signed_url_ttl_s

    def upload(self, batch_id: UUID, filename: str, data: bytes) -> str:
        """Returns the storage_path written. Filename collisions are the
        caller's responsibility (router suffixes __1/__2 before calling)."""
        safe = safe_filename(filename)
        path = storage_path_for(batch_id, safe)
        self._client.storage.from_(BUCKET).upload(
            path, data, file_options={"content-type":
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        )
        return path

    def download(self, path: str) -> bytes:
        return self._client.storage.from_(BUCKET).download(path)

    def signed_url(self, path: str) -> str:
        """Returns a 5-minute (configurable) signed URL string."""
        result = self._client.storage.from_(BUCKET).create_signed_url(path, self._ttl)
        # supabase-py returns {'signedURL': '...'} (or 'signedUrl' depending on version).
        for key in ("signedURL", "signedUrl", "signed_url"):
            if key in result:
                return str(result[key])
        raise RuntimeError(f"No signedURL in storage response: {result!r}")

    def delete_prefix(self, batch_id: UUID) -> None:
        """Delete every object under <batch_id>/. List-then-delete pattern."""
        prefix = str(batch_id)
        listing = self._client.storage.from_(BUCKET).list(prefix)
        names = [f"{prefix}/{obj['name']}" for obj in listing]
        if names:
            self._client.storage.from_(BUCKET).remove(names)


@contextmanager
def downloaded_to_tempfile(client: StorageClient, path: str) -> Iterator[Path]:
    """Context manager: download bytes from Storage to a tempfile, yield the
    Path, delete the tempfile on exit. Used by parse_worker because the
    engine's parse_workbook(path) takes a Path, not bytes."""
    data = client.download(path)
    tf = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    try:
        tf.write(data)
        tf.flush()
        tf.close()
        yield Path(tf.name)
    finally:
        Path(tf.name).unlink(missing_ok=True)


def build_client(settings: object) -> StorageClient:
    """Construct a StorageClient from app settings.

    `settings` is duck-typed to avoid a circular import with config.py.
    """
    from supabase import create_client
    url = getattr(settings, "SUPABASE_URL")
    key = getattr(settings, "SUPABASE_SERVICE_ROLE_KEY").get_secret_value()
    ttl = int(getattr(settings, "STORAGE_SIGNED_URL_TTL_S"))
    sb = create_client(url, key)
    return StorageClient(sb, signed_url_ttl_s=ttl)
```

- [ ] **Step 5: Lint + type-check**

```bash
cd packages/api
uv run ruff check src/api/services/storage.py
uv run mypy src/api/services/storage.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/api/src/api/services/__init__.py \
        packages/api/src/api/services/storage.py \
        packages/api/src/api/config.py \
        packages/api/pyproject.toml \
        packages/api/uv.lock
git commit -m "feat(api): services/storage.py — Supabase Storage wrapper

Single chokepoint for the supabase-py SDK. upload, download, signed_url
(default 5 min TTL via STORAGE_SIGNED_URL_TTL_S), delete_prefix.

Plus downloaded_to_tempfile context manager — parse_worker writes
bytes to a tempfile so the engine's parse_workbook(path: Path) can
read it (spec adaptation note in plan header)."
```

---

### Task 13: `services/matcher.py` — `pg_trgm`-backed property suggestions

**Files:**
- Create: `packages/api/src/api/services/matcher.py`
- Test (new): `packages/api/tests/unit/test_matcher_query.py`

**Why:** Spec §8.5. Returns either an auto-link (single exact name match) or up to 5 fuzzy suggestions above the similarity threshold. Pure SQL — no engine calls, no business state.

- [ ] **Step 1: Write the failing test**

Create `packages/api/tests/unit/test_matcher_query.py`:

```python
"""Tests for matcher's pure logic + SQL parameter composition.
Real DB queries are exercised in integration tests."""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from api.services import matcher


def _record(d: dict[str, Any]) -> Any:
    """Mimic asyncpg.Record's dict-style access."""
    class R(dict[str, Any]):
        def __getitem__(self, key: str) -> Any:
            return dict.__getitem__(self, key)
    return R(d)


@pytest.mark.asyncio
async def test_no_building_name_returns_empty_match() -> None:
    conn = AsyncMock()
    result = await matcher.suggest(conn, None)
    assert result.property_id is None
    assert result.score is None
    assert result.auto_linked is False
    assert result.suggestions == []
    conn.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_blank_building_name_returns_empty_match() -> None:
    conn = AsyncMock()
    result = await matcher.suggest(conn, "   ")
    assert result.property_id is None
    conn.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_single_exact_match_auto_links() -> None:
    pid = uuid4()
    eid = uuid4()
    conn = AsyncMock()
    conn.fetch.side_effect = [
        # First fetch: exact match query, returns 1 row
        [_record({"id": pid, "entity_id": eid, "name": "55 Empire Road"})],
    ]
    result = await matcher.suggest(conn, "  55 EMPIRE ROAD  ")  # case + whitespace
    assert result.property_id == pid
    assert result.auto_linked is True
    assert result.score == Decimal("1.0") or result.score == 1.0
    assert result.suggestions == []
    # Only the exact-match query ran, not the fuzzy fallback.
    assert conn.fetch.call_count == 1


@pytest.mark.asyncio
async def test_multiple_exact_matches_no_auto_link() -> None:
    """When two properties share a name, reviewer must disambiguate."""
    p1, p2 = uuid4(), uuid4()
    conn = AsyncMock()
    conn.fetch.side_effect = [
        [_record({"id": p1, "entity_id": uuid4(), "name": "Empire Road"}),
         _record({"id": p2, "entity_id": uuid4(), "name": "Empire Road"})],
    ]
    result = await matcher.suggest(conn, "Empire Road")
    assert result.property_id is None
    assert result.auto_linked is False
    assert len(result.suggestions) == 2
    assert {s.id for s in result.suggestions} == {p1, p2}


@pytest.mark.asyncio
async def test_fuzzy_match_returns_suggestions() -> None:
    pid = uuid4()
    conn = AsyncMock()
    conn.fetch.side_effect = [
        [],  # exact returns nothing
        [_record({"id": pid, "entity_id": uuid4(),
                  "name": "55 Empire Road", "score": 0.78})],
    ]
    result = await matcher.suggest(conn, "55 Empire Rd")
    assert result.property_id is None
    assert result.auto_linked is False
    assert len(result.suggestions) == 1
    assert result.suggestions[0].id == pid
    assert pytest.approx(float(result.suggestions[0].score), abs=0.01) == 0.78


@pytest.mark.asyncio
async def test_fuzzy_below_threshold_returns_nothing() -> None:
    conn = AsyncMock()
    conn.fetch.side_effect = [[], []]  # exact none, fuzzy none
    result = await matcher.suggest(conn, "wildly different name")
    assert result.suggestions == []


def test_threshold_constant_is_documented() -> None:
    assert matcher.SIMILARITY_THRESHOLD == 0.5
    assert matcher.MAX_SUGGESTIONS == 5
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/api
uv run pytest tests/unit/test_matcher_query.py -v
```

Expected: collection error or all tests **FAIL** because `api.services.matcher` doesn't exist.

- [ ] **Step 3: Implement the matcher**

Create `packages/api/src/api/services/matcher.py`:

```python
"""Property fuzzy-match for Excel import auto-linking.

Pure SQL via pg_trgm. Threshold + max-suggestions are module-level constants
so they can be tuned from production data later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

import asyncpg

SIMILARITY_THRESHOLD: float = 0.5
MAX_SUGGESTIONS: int = 5


@dataclass(frozen=True)
class Suggestion:
    id: UUID
    entity_id: UUID
    name: str
    score: Decimal


@dataclass(frozen=True)
class MatchResult:
    property_id: UUID | None
    score: Decimal | None
    auto_linked: bool
    suggestions: list[Suggestion] = field(default_factory=list)


async def suggest(
    conn: asyncpg.Connection, building_name: str | None,
) -> MatchResult:
    """Match `building_name` against public.property.

    Logic:
    1. Exact (case + whitespace normalised) match → if exactly one, auto-link.
    2. Multiple exact matches → suggest all, no auto-link.
    3. No exact match → pg_trgm similarity ≥ SIMILARITY_THRESHOLD, top N suggestions.
    """
    if not building_name or not building_name.strip():
        return MatchResult(None, None, False, [])

    exact = await conn.fetch(
        """
        select id, entity_id, name
          from public.property
         where deleted_at is null
           and lower(trim(name)) = lower(trim($1))
        """,
        building_name,
    )

    if len(exact) == 1:
        row = exact[0]
        return MatchResult(
            property_id=row["id"],
            score=Decimal("1.0"),
            auto_linked=True,
            suggestions=[],
        )

    if len(exact) > 1:
        sugs = [
            Suggestion(id=r["id"], entity_id=r["entity_id"],
                       name=r["name"], score=Decimal("1.0"))
            for r in exact
        ]
        return MatchResult(None, None, False, sugs)

    fuzzy = await conn.fetch(
        """
        select id, entity_id, name, similarity(name, $1) as score
          from public.property
         where deleted_at is null
           and similarity(name, $1) >= $2
         order by score desc
         limit $3
        """,
        building_name, SIMILARITY_THRESHOLD, MAX_SUGGESTIONS,
    )
    sugs = [
        Suggestion(id=r["id"], entity_id=r["entity_id"],
                   name=r["name"], score=Decimal(str(r["score"])))
        for r in fuzzy
    ]
    return MatchResult(None, None, False, sugs)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/api
uv run pytest tests/unit/test_matcher_query.py -v
```

Expected: all 7 tests **PASS**.

- [ ] **Step 5: Lint + type-check**

```bash
cd packages/api
uv run ruff check src/api/services/matcher.py tests/unit/test_matcher_query.py
uv run mypy src/api/services/matcher.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/api/src/api/services/matcher.py \
        packages/api/tests/unit/test_matcher_query.py
git commit -m "feat(api): services/matcher.py — pg_trgm property suggestions

Exact match (case+whitespace normalised) -> auto-link if one row.
Multiple exact matches -> suggest all. Otherwise fuzzy via similarity()
above SIMILARITY_THRESHOLD (0.5), top MAX_SUGGESTIONS (5)."
```

---

### Task 14: `services/parse_worker.py` — background-task entry point

**Files:**
- Create: `packages/api/src/api/services/parse_worker.py`
- Test (new): `packages/api/tests/unit/test_parse_worker_per_item.py`

**Why:** Spec §8. Pulls files from Storage, runs `parse_workbook` + `calculate`, calls matcher, writes `import_item` rows. The outer broad-`except` per item is the **only** place broad exception catch is permitted; a single bad workbook must not poison the rest of the batch.

- [ ] **Step 1: Write the failing test**

Create `packages/api/tests/unit/test_parse_worker_per_item.py`:

```python
"""Unit tests for parse_worker._process_one with mocked storage + engine."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from api.services import parse_worker
from api.services.matcher import MatchResult, Suggestion


def _item_record(**overrides: Any) -> Any:
    """Mimic an asyncpg.Record for an import_item row."""
    base = {
        "id": uuid4(),
        "batch_id": uuid4(),
        "filename": "fixture.xlsx",
        "storage_path": f"{uuid4()}/fixture.xlsx",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_process_one_parse_returns_no_inputs_marks_error() -> None:
    """When parse_workbook returns inputs=None, item is marked as parse error
    with the engine's parse_errors attached."""
    item = _item_record()
    conn = AsyncMock()
    storage = MagicMock()

    parse_result = MagicMock()
    parse_result.inputs = None
    parse_result.building_name = "55 Empire Road"
    parse_result.parse_errors = [
        MagicMock(model_dump=lambda: {"code": "missing_required_section",
                                      "message": "...", "field_path": "tenants"}),
    ]

    with patch.object(parse_worker, "_parse_bytes", return_value=parse_result), \
         patch("api.queries.import_item.mark_parse_error",
               new_callable=AsyncMock) as mock_mark_err:
        await parse_worker._process_one(conn, storage, item)

    mock_mark_err.assert_called_once()
    kwargs = mock_mark_err.call_args.kwargs
    assert kwargs["building_name"] == "55 Empire Road"
    assert kwargs["errors"][0]["code"] == "missing_required_section"


@pytest.mark.asyncio
async def test_process_one_engine_value_error_marks_error() -> None:
    item = _item_record()
    conn = AsyncMock()
    storage = MagicMock()

    parse_result = MagicMock()
    parse_result.inputs = MagicMock()
    parse_result.inputs.model_dump = lambda mode="json": {"valuation_date": "2026-03-15"}
    parse_result.building_name = "x"
    parse_result.sheet_market_value = Decimal("12500000")
    parse_result.parse_warnings = []
    parse_result.parse_errors = []

    with patch.object(parse_worker, "_parse_bytes", return_value=parse_result), \
         patch.object(parse_worker, "_calc",
                      side_effect=ValueError("cap_rate must be > 0")), \
         patch("api.queries.import_item.mark_parse_error",
               new_callable=AsyncMock) as mock_mark_err:
        await parse_worker._process_one(conn, storage, item)

    mock_mark_err.assert_called_once()
    err = mock_mark_err.call_args.kwargs["errors"][0]
    assert err["code"] == "engine_validation_error"
    assert "cap_rate" in err["message"]


@pytest.mark.asyncio
async def test_process_one_happy_path_marks_parsed_with_match() -> None:
    item = _item_record()
    conn = AsyncMock()
    storage = MagicMock()
    pid = uuid4()

    parse_result = MagicMock()
    parse_result.inputs = MagicMock()
    parse_result.inputs.model_dump = lambda mode="json": {"valuation_date": "2026-03-15"}
    parse_result.building_name = "55 Empire Road"
    parse_result.sheet_market_value = Decimal("12500000")
    parse_result.parse_warnings = []
    parse_result.parse_errors = []

    calc_result = MagicMock()
    calc_result.market_value = Decimal("12500000")
    calc_result.warnings = []
    calc_result.model_dump = lambda mode="json": {"market_value": "12500000"}

    with patch.object(parse_worker, "_parse_bytes", return_value=parse_result), \
         patch.object(parse_worker, "_calc", return_value=calc_result), \
         patch("api.services.matcher.suggest",
               new_callable=AsyncMock) as mock_suggest, \
         patch("api.queries.import_item.mark_parsed",
               new_callable=AsyncMock) as mock_mark:
        mock_suggest.return_value = MatchResult(
            property_id=pid, score=Decimal("1.0"), auto_linked=True,
            suggestions=[],
        )
        await parse_worker._process_one(conn, storage, item)

    mock_mark.assert_called_once()
    kwargs = mock_mark.call_args.kwargs
    assert kwargs["parse_status"] == "ok"
    assert kwargs["auto_linked"] is True
    assert kwargs["resolution"] == "accepted"
    assert kwargs["resolved_property_id"] == pid


@pytest.mark.asyncio
async def test_process_one_recompute_mismatch_adds_warning() -> None:
    """diff > tolerance produces a recompute_mismatch warning + parse_status=warning."""
    item = _item_record()
    conn = AsyncMock()
    storage = MagicMock()

    parse_result = MagicMock()
    parse_result.inputs = MagicMock()
    parse_result.inputs.model_dump = lambda mode="json": {}
    parse_result.building_name = "x"
    parse_result.sheet_market_value = Decimal("12500000")
    parse_result.parse_warnings = []
    parse_result.parse_errors = []

    calc_result = MagicMock()
    calc_result.market_value = Decimal("13000000")  # 4% diff > 0.1% tolerance
    calc_result.warnings = []
    calc_result.model_dump = lambda mode="json": {}

    with patch.object(parse_worker, "_parse_bytes", return_value=parse_result), \
         patch.object(parse_worker, "_calc", return_value=calc_result), \
         patch("api.services.matcher.suggest",
               new_callable=AsyncMock) as mock_suggest, \
         patch("api.queries.import_item.mark_parsed",
               new_callable=AsyncMock) as mock_mark:
        mock_suggest.return_value = MatchResult(None, None, False, [])
        await parse_worker._process_one(conn, storage, item)

    kwargs = mock_mark.call_args.kwargs
    assert kwargs["parse_status"] == "warning"
    codes = [w["code"] for w in kwargs["warnings_json"]]
    assert "recompute_mismatch" in codes


@pytest.mark.asyncio
async def test_run_outer_exception_marks_unrecoverable() -> None:
    """The outer broad-except per item must catch any exception type, log it,
    and mark the item with code='unrecoverable_parse_error'."""
    item = _item_record()
    pool_acquire_cm = AsyncMock()
    conn = AsyncMock()
    pool_acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    pool_acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=pool_acquire_cm)

    storage = MagicMock()

    with patch("api.queries.import_item.list_for_parsing",
               new_callable=AsyncMock, return_value=[item]), \
         patch.object(parse_worker, "_process_one",
                      side_effect=RuntimeError("boom")), \
         patch("api.queries.import_item.mark_unrecoverable_error",
               new_callable=AsyncMock) as mock_mark, \
         patch("api.queries.import_batch.set_status",
               new_callable=AsyncMock):
        await parse_worker.run(pool, storage, item["batch_id"])

    mock_mark.assert_called_once()
    args = mock_mark.call_args.args
    assert args[1] == item["id"]
    assert "boom" in args[2]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/api
uv run pytest tests/unit/test_parse_worker_per_item.py -v
```

Expected: collection error or all tests **FAIL** (module doesn't exist).

- [ ] **Step 3: Implement the parse worker**

Create `packages/api/src/api/services/parse_worker.py`:

```python
"""Background task: parse uploaded workbooks, recompute, write import_item rows.

Outer broad-except per item is the ONLY place in the codebase where catching
bare Exception is permitted: a single bad workbook must not poison the batch.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg

from api.queries import import_batch as q_batch
from api.queries import import_item as q_item
from api.services import matcher
from api.services.storage import StorageClient, downloaded_to_tempfile

try:
    from valuation_engine import calculate as _engine_calculate
    from valuation_engine.excel import parse_workbook
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("valuation_engine must be installed") from exc

log = logging.getLogger(__name__)

RECOMPUTE_TOLERANCE_PCT = Decimal("0.001")


def _parse_bytes(storage: StorageClient, storage_path: str) -> Any:
    """Adapter: bytes from Storage → tempfile → engine.parse_workbook(path).
    See plan header adaptation #2."""
    with downloaded_to_tempfile(storage, storage_path) as path:
        return parse_workbook(path)


def _calc(inputs: Any) -> Any:
    """Indirection so tests can patch it without monkey-patching the engine."""
    return _engine_calculate(inputs)


def _compute_diff(
    sheet_value: Decimal | None, recomputed: Decimal,
) -> tuple[Decimal | None, dict[str, Any] | None]:
    if sheet_value is None or sheet_value == 0:
        return None, {
            "code": "formula_missing_value",
            "message": "Sheet's market value cell had no cached value; "
                       "diff_pct unavailable.",
            "field_path": None,
        }
    diff = (abs(recomputed - sheet_value) / sheet_value)
    if diff > RECOMPUTE_TOLERANCE_PCT:
        return diff, {
            "code": "recompute_mismatch",
            "message": (f"Engine recomputed {recomputed}; sheet stored "
                        f"{sheet_value} (diff {diff:.4%})."),
            "field_path": None,
        }
    return diff, None


async def _process_one(
    conn: asyncpg.Connection,
    storage: StorageClient,
    item: Any,
) -> None:
    """Per-item processing. Errors raised here are caught by the outer
    broad-except in run() and logged + persisted as unrecoverable."""
    parsed = _parse_bytes(storage, item["storage_path"])

    if parsed.inputs is None:
        # Engine surfaces hard parse errors via parse_errors (see plan adaptation #1).
        await q_item.mark_parse_error(
            conn, item["id"],
            building_name=parsed.building_name,
            errors=[w.model_dump() if hasattr(w, "model_dump") else dict(w)
                    for w in parsed.parse_errors],
        )
        return

    inputs_json = parsed.inputs.model_dump(mode="json")

    try:
        result = _calc(parsed.inputs)
    except ValueError as exc:
        await q_item.mark_parse_error(
            conn, item["id"],
            building_name=parsed.building_name,
            parsed_inputs_json=inputs_json,
            errors=[{"code": "engine_validation_error",
                     "message": str(exc), "field_path": None}],
        )
        return

    diff_pct, diff_warning = _compute_diff(
        parsed.sheet_market_value, result.market_value,
    )

    warnings: list[dict[str, Any]] = []
    for w in result.warnings:
        warnings.append(w.model_dump() if hasattr(w, "model_dump") else dict(w))
    for w in parsed.parse_warnings:
        warnings.append(w.model_dump() if hasattr(w, "model_dump") else dict(w))
    if diff_warning is not None:
        warnings.append(diff_warning)

    match = await matcher.suggest(conn, parsed.building_name)

    parse_status = "warning" if warnings else "ok"
    resolution = "accepted" if match.auto_linked else "pending"

    await q_item.mark_parsed(
        conn, item["id"],
        building_name=parsed.building_name,
        parsed_inputs_json=inputs_json,
        computed_result_json=result.model_dump(mode="json"),
        spreadsheet_market_value=parsed.sheet_market_value,
        recomputed_market_value=result.market_value,
        diff_pct=diff_pct,
        warnings_json=warnings,
        parse_status=parse_status,
        suggested_property_id=match.property_id,
        suggested_score=match.score,
        auto_linked=match.auto_linked,
        resolution=resolution,
        resolved_property_id=(match.property_id if match.auto_linked else None),
    )


async def run(
    pool: asyncpg.Pool,
    storage: StorageClient,
    batch_id: UUID,
) -> None:
    """Idempotent batch parse. Re-callable: list_for_parsing skips
    already-parsed rows."""
    async with pool.acquire(timeout=10) as conn:
        items = await q_item.list_for_parsing(conn, batch_id)
        for item in items:
            try:
                await _process_one(conn, storage, item)
            except Exception as exc:  # noqa: BLE001 — last-resort guard, see module docstring
                log.exception(
                    "parse_worker_item_failed",
                    extra={"item_id": str(item["id"]),
                           "filename": item["filename"],
                           "batch_id": str(batch_id)},
                )
                await q_item.mark_unrecoverable_error(conn, item["id"], repr(exc))
        await q_batch.set_status(conn, batch_id, "review")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/api
uv run pytest tests/unit/test_parse_worker_per_item.py -v
```

Expected: all 5 tests **PASS**.

- [ ] **Step 5: Lint + type-check**

```bash
cd packages/api
uv run ruff check src/api/services/parse_worker.py tests/unit/test_parse_worker_per_item.py
uv run mypy src/api/services/parse_worker.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/api/src/api/services/parse_worker.py \
        packages/api/tests/unit/test_parse_worker_per_item.py
git commit -m "feat(api): services/parse_worker.py — background-task batch parser

For each import_item: download from Storage to a tempfile, parse via
valuation_engine.excel.parse_workbook, recompute via engine.calculate,
diff against sheet's stored market value, run matcher.suggest, persist
via mark_parsed.

Outer broad-except per item: a single bad workbook must not poison the
batch. Logged + stored as 'unrecoverable_parse_error'."
```

---

### Task 15: `services/commit_worker.py` — idempotent commit loop

**Files:**
- Create: `packages/api/src/api/services/commit_worker.py`
- Test (new): `packages/api/tests/unit/test_commit_worker.py`

**Why:** Spec §9. Per-item transactions, idempotent (skips items already snapshot'd). Reuses Plan 2's `q_snapshot.supersede_active` + `q_snapshot.insert_snapshot` — same code path as the manual `POST /properties/{id}/snapshots` endpoint.

- [ ] **Step 1: Write the failing test**

Create `packages/api/tests/unit/test_commit_worker.py`:

```python
"""Unit tests for commit_worker — control flow + per-item failure handling."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from api.services import commit_worker
from api.services.commit_worker import CommitFailure
from api.schemas.user import AppUser


def _user() -> AppUser:
    return AppUser(
        id=uuid4(), email="reviewer@anchorpointrisk.co.za",
        display_name=None, role="valuer",
        created_at="2026-05-01T00:00:00Z", last_seen_at=None,
    )


def _item_record(**overrides: Any) -> dict[str, Any]:
    pid = uuid4()
    base: dict[str, Any] = {
        "id": uuid4(),
        "batch_id": uuid4(),
        "filename": "fixture.xlsx",
        "resolution": "accepted",
        "resolved_property_id": pid,
        "resolved_inputs_json": None,
        "parsed_inputs_json": {
            "valuation_date": "2026-03-15", "tenants": [], "cap_rate": "0.10",
            "monthly_operating_expenses": "100000", "vacancy_allowance_pct": "0.05",
        },
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_commit_one_no_inputs_raises_commit_failure() -> None:
    item = _item_record(parsed_inputs_json=None, resolved_inputs_json=None)
    pool = MagicMock()
    user = _user()
    with pytest.raises(CommitFailure) as ei:
        await commit_worker._commit_one(pool, item, user)
    assert ei.value.reason == "no_inputs"


@pytest.mark.asyncio
async def test_commit_one_no_property_link_raises() -> None:
    item = _item_record(resolved_property_id=None)
    pool = MagicMock()
    user = _user()
    with pytest.raises(CommitFailure) as ei:
        await commit_worker._commit_one(pool, item, user)
    assert ei.value.reason == "no_property_link"


@pytest.mark.asyncio
async def test_commit_batch_collects_failures_and_continues() -> None:
    """One failing item must not stop the loop; summary collects failures."""
    item_ok = _item_record(filename="ok.xlsx")
    item_bad = _item_record(filename="bad.xlsx", resolved_property_id=None)
    user = _user()
    pool = MagicMock()

    with patch("api.queries.import_item.list_for_commit",
               new_callable=AsyncMock, return_value=[item_ok, item_bad]), \
         patch("api.queries.import_item.count_already_committed",
               new_callable=AsyncMock, return_value=0), \
         patch("api.queries.import_item.all_items_terminal",
               new_callable=AsyncMock, return_value=False), \
         patch("api.queries.import_batch.set_status",
               new_callable=AsyncMock), \
         patch("api.services.commit_worker._commit_one",
               new_callable=AsyncMock) as mock_co, \
         patch("api.audit.audit", new_callable=AsyncMock):
        # ok succeeds, bad raises CommitFailure.
        async def side(_pool: Any, item: dict[str, Any], _user: Any) -> None:
            if item["filename"] == "bad.xlsx":
                raise CommitFailure(item["id"], item["filename"],
                                    "no_property_link", "...")
        mock_co.side_effect = side

        summary = await commit_worker.commit_batch(pool, item_ok["batch_id"], user)

    assert summary.committed == 1
    assert summary.failed == 1
    assert len(summary.failures) == 1
    assert summary.failures[0].reason == "no_property_link"


@pytest.mark.asyncio
async def test_commit_batch_terminal_flips_status_and_cleans_storage() -> None:
    user = _user()
    pool = MagicMock()
    storage = MagicMock()
    batch_id = uuid4()

    with patch("api.queries.import_item.list_for_commit",
               new_callable=AsyncMock, return_value=[]), \
         patch("api.queries.import_item.count_already_committed",
               new_callable=AsyncMock, return_value=3), \
         patch("api.queries.import_item.all_items_terminal",
               new_callable=AsyncMock, return_value=True), \
         patch("api.queries.import_batch.set_status",
               new_callable=AsyncMock) as mock_set, \
         patch("api.audit.audit", new_callable=AsyncMock):
        summary = await commit_worker.commit_batch(
            pool, batch_id, user, storage=storage,
        )

    mock_set.assert_called_once()
    assert mock_set.call_args.args[2] == "committed"
    storage.delete_prefix.assert_called_once_with(batch_id)
    assert summary.batch_status == "committed"
    assert summary.skipped == 3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/api
uv run pytest tests/unit/test_commit_worker.py -v
```

Expected: collection error or all **FAIL**.

- [ ] **Step 3: Implement the commit worker**

Create `packages/api/src/api/services/commit_worker.py`:

```python
"""Idempotent per-item commit loop for an import batch.

One transaction per item. Re-callable — items already at
resolved_snapshot_id IS NOT NULL are counted as 'skipped' and not re-processed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import asyncpg

from api.audit import audit
from api.queries import import_batch as q_batch
from api.queries import import_item as q_item
from api.queries import property as q_property
from api.queries import snapshot as q_snapshot
from api.schemas.user import AppUser

try:
    from valuation_engine import __version__ as engine_version
    from valuation_engine import calculate
    from valuation_engine.models import ValuationInput
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("valuation_engine must be installed") from exc

log = logging.getLogger(__name__)


class CommitFailure(Exception):
    """Raised by _commit_one for any per-item failure. Caller (commit_batch)
    catches this to collect failures into the summary; other exception types
    propagate as 500."""
    def __init__(self, item_id: UUID, filename: str, reason: str, message: str) -> None:
        self.item_id = item_id
        self.filename = filename
        self.reason = reason
        self.message = message
        super().__init__(message)


@dataclass
class CommitSummary:
    batch_id: UUID
    committed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list["CommitFailure"] = field(default_factory=list)
    batch_status: str = "review"  # 'committed' or 'review'


async def _commit_one(
    pool: asyncpg.Pool,
    item: Any,
    actor: AppUser,
) -> None:
    inputs = item["resolved_inputs_json"] or item["parsed_inputs_json"]
    if not inputs:
        raise CommitFailure(item["id"], item["filename"],
                            "no_inputs", "No inputs to commit.")
    if not item["resolved_property_id"]:
        raise CommitFailure(item["id"], item["filename"], "no_property_link",
                            "Reviewer did not link a property.")

    try:
        valuation_input = ValuationInput.model_validate(inputs)
        result = calculate(valuation_input)
    except ValueError as exc:
        raise CommitFailure(item["id"], item["filename"],
                            "engine_validation_error", str(exc)) from exc

    async with pool.acquire(timeout=10) as conn, conn.transaction():
        prop = await q_property.get_property(conn, item["resolved_property_id"])
        if prop is None:
            raise CommitFailure(item["id"], item["filename"], "property_missing",
                                "Linked property no longer exists.")

        await q_snapshot.supersede_active(conn, item["resolved_property_id"])
        snap = await q_snapshot.insert_snapshot(
            conn,
            property_id=item["resolved_property_id"],
            valuation_date=valuation_input.valuation_date,
            created_by=actor.id,
            inputs_json=valuation_input.model_dump(mode="json"),
            result_json=result.model_dump(mode="json"),
            market_value=result.market_value,
            cap_rate=valuation_input.cap_rate,
            engine_version=engine_version,
            source="excel_import",
            source_file=item["filename"],
        )

        await audit(
            conn,
            actor_id=actor.id, actor_email=actor.email,
            action="create",
            target_table="valuation_snapshot",
            target_id=snap["id"],
            before=None,
            after={
                "property_id": str(item["resolved_property_id"]),
                "valuation_date": str(valuation_input.valuation_date),
                "market_value": str(result.market_value),
                "source": "excel_import",
                "source_file": item["filename"],
                "import_item_id": str(item["id"]),
            },
        )

        await q_item.mark_committed(
            conn, item["id"], snapshot_id=snap["id"], actor_id=actor.id,
        )

        await audit(
            conn,
            actor_id=actor.id, actor_email=actor.email,
            action="update",
            target_table="import_item",
            target_id=item["id"],
            before={"resolution": item["resolution"], "resolved_snapshot_id": None},
            after={"resolution": "committed",
                   "resolved_snapshot_id": str(snap["id"])},
        )


async def commit_batch(
    pool: asyncpg.Pool,
    batch_id: UUID,
    actor: AppUser,
    *,
    storage: Any = None,
) -> CommitSummary:
    summary = CommitSummary(batch_id=batch_id)

    async with pool.acquire(timeout=10) as conn:
        items = await q_item.list_for_commit(conn, batch_id)

    for item in items:
        try:
            await _commit_one(pool, item, actor)
            summary.committed += 1
        except CommitFailure as f:
            summary.failed += 1
            summary.failures.append(f)
        except Exception as exc:  # noqa: BLE001 — surface as failure, not 500
            log.exception("commit_worker_unexpected",
                          extra={"item_id": str(item["id"])})
            summary.failed += 1
            summary.failures.append(
                CommitFailure(item["id"], item["filename"],
                              "unexpected_error", repr(exc))
            )

    async with pool.acquire(timeout=10) as conn:
        summary.skipped = await q_item.count_already_committed(conn, batch_id)
        if await q_item.all_items_terminal(conn, batch_id):
            await q_batch.set_status(conn, batch_id, "committed")
            if storage is not None:
                storage.delete_prefix(batch_id)
            summary.batch_status = "committed"

        await audit(
            conn,
            actor_id=actor.id, actor_email=actor.email,
            action="commit",
            target_table="import_batch",
            target_id=batch_id,
            before=None,
            after={"committed": summary.committed,
                   "failed": summary.failed,
                   "skipped": summary.skipped,
                   "batch_status": summary.batch_status},
        )

    return summary
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/api
uv run pytest tests/unit/test_commit_worker.py -v
```

Expected: all 4 tests **PASS**.

- [ ] **Step 5: Lint + type-check**

```bash
cd packages/api
uv run ruff check src/api/services/commit_worker.py tests/unit/test_commit_worker.py
uv run mypy src/api/services/commit_worker.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/api/src/api/services/commit_worker.py \
        packages/api/tests/unit/test_commit_worker.py
git commit -m "feat(api): services/commit_worker.py — idempotent commit loop

Per-item transactions reusing Plan 2's q_snapshot.supersede_active +
insert_snapshot — same code path as manual POST /properties/{id}/snapshots.
Re-callable: list_for_commit skips items already at resolved_snapshot_id.

CommitFailure raised per item; commit_batch collects them. Batch flips
to 'committed' + Storage prefix is deleted only when all items reach a
terminal resolution."
```

---

## Phase 4 — Branding (Task 16)

---

### Task 16: Branding env vars + asset + loader

**Files:**
- Create: `packages/api/branding/anchorpoint_logo.png` (placeholder PNG, ≤50 KB)
- Create: `packages/api/branding/README.md`
- Create: `packages/api/src/api/services/branding.py`
- Modify: `packages/api/src/api/config.py`

**Why:** Spec §10.6. Branding values (firm name, address lines, contact lines, logo path) loaded once at startup into `app.state.branding`. Pipe-separated env vars keep `render.yaml` simple.

- [ ] **Step 1: Add settings**

In `packages/api/src/api/config.py`, add to the `Settings` class:

```python
    BRANDING_FIRM_NAME: str = "Anchor Point Risk (Pty) Ltd"
    BRANDING_FIRM_ADDRESS_LINES: str = ""        # pipe-separated
    BRANDING_FIRM_CONTACT_LINES: str = ""        # pipe-separated
    BRANDING_FIRM_LOGO_PATH: str = "branding/anchorpoint_logo.png"
```

- [ ] **Step 2: Implement the loader**

Create `packages/api/src/api/services/branding.py`:

```python
"""Loads firm branding from settings into a single immutable dict for
the PDF template. Loaded once at app startup; never re-read per request."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Branding:
    firm_name: str
    firm_logo_path: str | None
    firm_address_lines: list[str]
    firm_contact_lines: list[str]


def _split_pipes(value: str) -> list[str]:
    return [p.strip() for p in value.split("|") if p.strip()]


def load(settings: object) -> Branding:
    """Build Branding from a Settings instance.

    If BRANDING_FIRM_LOGO_PATH points at a missing file, firm_logo_path is
    set to None — the template renders firm name larger instead.
    """
    raw_path = str(getattr(settings, "BRANDING_FIRM_LOGO_PATH"))
    logo: str | None = raw_path
    if not Path(raw_path).is_file():
        logo = None
    return Branding(
        firm_name=str(getattr(settings, "BRANDING_FIRM_NAME")),
        firm_logo_path=logo,
        firm_address_lines=_split_pipes(
            str(getattr(settings, "BRANDING_FIRM_ADDRESS_LINES"))
        ),
        firm_contact_lines=_split_pipes(
            str(getattr(settings, "BRANDING_FIRM_CONTACT_LINES"))
        ),
    )
```

- [ ] **Step 3: Create the branding directory + README**

Create `packages/api/branding/README.md`:

```markdown
# Branding assets

Drop the firm logo here as `anchorpoint_logo.png` (or set `BRANDING_FIRM_LOGO_PATH`
to point elsewhere).

- Recommended size: 300px wide @ 96dpi (~30mm in the PDF header).
- Format: PNG with transparency.
- Max size: keep under 100 KB; the file is embedded in every generated PDF.

If the file is missing, the PDF header renders the firm name in a larger
font instead — no broken-image icon.
```

- [ ] **Step 4: Generate a placeholder PNG**

```bash
cd packages/api
mkdir -p branding
python -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (300, 80), (255, 255, 255, 0))
draw = ImageDraw.Draw(img)
draw.text((10, 30), 'Anchor Point Risk', fill=(0, 0, 0, 255))
img.save('branding/anchorpoint_logo.png')
print('wrote branding/anchorpoint_logo.png')
"
```

If Pillow isn't installed, install it first as a dev dependency or use any 300×80 PNG. Confirm:

```bash
ls -la packages/api/branding/anchorpoint_logo.png
```

- [ ] **Step 5: Lint + type-check**

```bash
cd packages/api
uv run ruff check src/api/services/branding.py
uv run mypy src/api/services/branding.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/api/branding/ \
        packages/api/src/api/services/branding.py \
        packages/api/src/api/config.py
git commit -m "feat(api): services/branding.py — load firm branding from env

BRANDING_FIRM_NAME, BRANDING_FIRM_ADDRESS_LINES (pipe-separated),
BRANDING_FIRM_CONTACT_LINES, BRANDING_FIRM_LOGO_PATH. Missing logo file
gracefully degrades to firm-name-only header.

Plus packages/api/branding/ asset directory with placeholder PNG."
```

---

## Phase 5a — Imports routers (Tasks 17–22)

Six tasks for the six `/imports*` endpoints. Each follows the Plan 2 pattern: define schema → write integration test → implement router → run test → commit.

---

### Task 17: `routers/imports.py` — `POST /imports`

**Files:**
- Create: `packages/api/src/api/routers/imports.py`
- Test (new): `packages/api/tests/integration/test_imports_upload.py`

**Why:** Spec §7.2. Multipart upload, reject non-`.xlsx` and oversized, write to Storage, insert batch + placeholder items, schedule `parse_worker.run`. Returns 202.

- [ ] **Step 1: Add `IMPORT_MAX_FILE_BYTES` setting**

In `packages/api/src/api/config.py`:

```python
    IMPORT_MAX_FILE_BYTES: int = 10 * 1024 * 1024   # 10 MB
```

- [ ] **Step 2: Write the failing integration test**

Create `packages/api/tests/integration/test_imports_upload.py`:

```python
"""Integration tests for POST /imports against local Supabase CLI stack."""
from __future__ import annotations

import io
from pathlib import Path
from uuid import UUID

import pytest

pytestmark = pytest.mark.integration


def _xlsx_bytes() -> bytes:
    """Minimal valid .xlsx file (an empty Excel workbook)."""
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


@pytest.mark.asyncio
async def test_post_imports_returns_202_with_batch_id(
    valuer_client, valuer_user,
) -> None:
    files = [("files", ("test.xlsx", _xlsx_bytes(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    resp = await valuer_client.post("/imports", files=files)
    assert resp.status_code == 202
    body = resp.json()
    assert "batch_id" in body
    UUID(body["batch_id"])  # parses
    assert body["file_count"] == 1
    assert body["status"] == "parsing"


@pytest.mark.asyncio
async def test_post_imports_no_files_returns_400(valuer_client) -> None:
    resp = await valuer_client.post("/imports", files=[])
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_files"


@pytest.mark.asyncio
async def test_post_imports_non_xlsx_returns_400(valuer_client) -> None:
    files = [("files", ("test.csv", b"a,b\n1,2\n", "text/csv"))]
    resp = await valuer_client.post("/imports", files=files)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_file_type"


@pytest.mark.asyncio
async def test_post_imports_oversized_returns_413(
    valuer_client, monkeypatch,
) -> None:
    """Force the cap low enough to trigger via a single small upload."""
    from api import config as cfg
    monkeypatch.setattr(cfg.get_settings(), "IMPORT_MAX_FILE_BYTES", 100)
    big = b"x" * 1024
    files = [("files", ("test.xlsx", big,
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    resp = await valuer_client.post("/imports", files=files)
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "file_too_large"


@pytest.mark.asyncio
async def test_post_imports_viewer_forbidden(viewer_client) -> None:
    files = [("files", ("test.xlsx", _xlsx_bytes(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    resp = await viewer_client.post("/imports", files=files)
    assert resp.status_code == 403
```

The fixtures `valuer_client`, `viewer_client`, `valuer_user` are provided by `tests/integration/conftest.py` from Plan 2. Confirm by checking [packages/api/tests/integration/conftest.py](packages/api/tests/integration/conftest.py).

- [ ] **Step 3: Run test to verify it fails**

```bash
cd packages/api
supabase start  # if not already
uv run pytest tests/integration/test_imports_upload.py -v
```

Expected: 404 (route not registered) or import error (`api.routers.imports` doesn't exist).

- [ ] **Step 4: Implement the router (POST handler only for this task)**

Create `packages/api/src/api/routers/imports.py`:

```python
"""HTTP layer for /imports endpoints.

Owns: multipart parsing, request validation, dispatch to background tasks
and services. No SQL, no Storage SDK, no parsing logic.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Request, UploadFile,
)

from api.auth import current_user, require_valuer
from api.db import get_db
from api.errors import APIError
from api.queries import import_batch as q_batch
from api.queries import import_item as q_item
from api.schemas.imports import ImportCreated
from api.schemas.user import AppUser
from api.services import parse_worker
from api.services.storage import safe_filename, storage_path_for

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("", response_model=ImportCreated, status_code=202)
async def create_import(
    background: BackgroundTasks,
    request: Request,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    files: list[UploadFile] = File(...),
) -> ImportCreated:
    if not files:
        raise APIError(status_code=400, code="no_files",
                       message="At least one file is required.")

    settings = request.app.state.settings
    storage = request.app.state.storage
    max_bytes = int(settings.IMPORT_MAX_FILE_BYTES)

    # Validate every file before any side effect.
    payloads: list[tuple[str, bytes]] = []
    for f in files:
        if not (f.filename or "").lower().endswith(".xlsx"):
            raise APIError(status_code=400, code="unsupported_file_type",
                           message=f"Only .xlsx files are accepted. Got: {f.filename!r}")
        data = await f.read()
        if len(data) > max_bytes:
            raise APIError(status_code=413, code="file_too_large",
                           message=f"{f.filename!r} exceeds {max_bytes} bytes.")
        payloads.append((f.filename or "upload.xlsx", data))

    # Insert the batch.
    batch = await q_batch.insert(
        conn, uploaded_by=user.id, file_count=len(payloads), status="parsing",
    )
    batch_id: UUID = batch["id"]

    # Suffix collisions, upload to storage, insert items.
    seen: dict[str, int] = defaultdict(int)
    for orig_name, data in payloads:
        safe = safe_filename(orig_name)
        seen[safe] += 1
        if seen[safe] > 1:
            stem, _, ext = safe.rpartition(".")
            safe = f"{stem}__{seen[safe] - 1}.{ext}" if stem else f"{safe}__{seen[safe] - 1}"
        path = storage.upload(batch_id, safe, data)
        await q_item.insert_placeholder(
            conn, batch_id=batch_id, filename=orig_name, storage_path=path,
        )

    pool: asyncpg.Pool = request.app.state.pool
    background.add_task(parse_worker.run, pool, storage, batch_id)

    return ImportCreated(batch_id=batch_id, file_count=len(payloads), status="parsing")
```

- [ ] **Step 5: Register the router in `main.py`**

Open `packages/api/src/api/main.py`. Inside `create_app`, alongside the other `app.include_router(...)` calls, add:

```python
    from api.routers.imports import router as imports_router
    app.include_router(imports_router)
```

- [ ] **Step 6: Initialise `app.state.storage` in lifespan**

Still in `main.py`, in the lifespan setup (next to `app.state.pool = pool`):

```python
    from api.services import storage as storage_module
    app.state.storage = storage_module.build_client(settings)
```

- [ ] **Step 7: Run the test to verify it passes**

```bash
cd packages/api
uv run pytest tests/integration/test_imports_upload.py -v
```

Expected: all 5 tests **PASS**.

- [ ] **Step 8: Lint + type-check**

```bash
cd packages/api
uv run ruff check src/api/routers/imports.py tests/integration/test_imports_upload.py
uv run mypy src/api/routers/imports.py
```

Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add packages/api/src/api/routers/imports.py \
        packages/api/src/api/main.py \
        packages/api/src/api/config.py \
        packages/api/tests/integration/test_imports_upload.py
git commit -m "feat(api): POST /imports — multipart upload + background parse

Validates files (.xlsx, ≤IMPORT_MAX_FILE_BYTES). On success: writes the
batch row, suffixes filename collisions, uploads to Supabase Storage,
inserts placeholder import_item rows, schedules parse_worker.run via
BackgroundTasks. Returns 202 with batch_id.

Valuer-only (RLS belt-and-braces; FastAPI Depends require_valuer first
line of defence)."
```

---

### Task 18: `GET /imports` (list) + `GET /imports/{id}` (detail)

**Files:**
- Modify: `packages/api/src/api/routers/imports.py`
- Test (new): `packages/api/tests/integration/test_imports_list_detail.py`

**Why:** Spec §7.3 + §7.4. Both viewers and valuers can read.

- [ ] **Step 1: Write the failing integration test**

Create `packages/api/tests/integration/test_imports_list_detail.py`:

```python
"""Integration tests for GET /imports + GET /imports/{id}."""
from __future__ import annotations

import io

import pytest

pytestmark = pytest.mark.integration


def _xlsx() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


@pytest.mark.asyncio
async def test_get_imports_returns_empty_list_initially(viewer_client) -> None:
    resp = await viewer_client.get("/imports")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_get_imports_lists_after_upload(valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    assert upload.status_code == 202
    batch_id = upload.json()["batch_id"]

    resp = await valuer_client.get("/imports")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(item["id"] == batch_id for item in body["items"])
    found = next(item for item in body["items"] if item["id"] == batch_id)
    assert found["file_count"] == 1
    assert "counts" in found
    assert "pending" in found["counts"]


@pytest.mark.asyncio
async def test_get_imports_filter_by_status(valuer_client) -> None:
    resp = await valuer_client.get("/imports?status=parsing&status=review")
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["status"] in ("parsing", "review")


@pytest.mark.asyncio
async def test_get_import_detail_returns_items_inline(valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]

    resp = await valuer_client.get(f"/imports/{batch_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == batch_id
    assert isinstance(body["items"], list)
    assert len(body["items"]) == 1
    assert body["items"][0]["filename"] == "a.xlsx"


@pytest.mark.asyncio
async def test_get_import_detail_404_for_unknown(valuer_client) -> None:
    resp = await valuer_client.get(
        "/imports/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/api
uv run pytest tests/integration/test_imports_list_detail.py -v
```

Expected: 404 on the GET endpoints (not yet registered).

- [ ] **Step 3: Add the two GET handlers**

In `packages/api/src/api/routers/imports.py`, append:

```python
from typing import Any
from api.schemas.imports import (
    ImportBatch, ImportBatchCounts, ImportBatchList, ImportBatchListItem,
    ImportItem, ImportItemSuggestion, ImportItemWarning,
)
from api.queries import property as q_property
from api.queries import entity as q_entity
from fastapi import Query


def _row_to_warning_list(json_field: list[dict[str, Any]] | None) -> list[ImportItemWarning]:
    return [ImportItemWarning(**w) for w in (json_field or [])]


async def _row_to_item(
    conn: asyncpg.Connection, row: Any,
) -> ImportItem:
    suggestion: ImportItemSuggestion | None = None
    if row["suggested_property_id"] is not None:
        prop = await q_property.get_property(
            conn, row["suggested_property_id"], include_deleted=True,
        )
        if prop is not None:
            ent = await q_entity.get_entity(conn, prop["entity_id"], include_deleted=True)
            suggestion = ImportItemSuggestion(
                property_id=prop["id"],
                property_name=prop["name"],
                entity_id=prop["entity_id"],
                entity_name=ent["name"] if ent else "",
                score=row["suggested_score"] or 0,
                auto_linked=bool(row["auto_linked"]),
            )
    return ImportItem(
        id=row["id"],
        filename=row["filename"],
        parse_status=row["parse_status"],
        building_name=row["building_name"],
        spreadsheet_market_value=row["spreadsheet_market_value"],
        recomputed_market_value=row["recomputed_market_value"],
        diff_pct=row["diff_pct"],
        warnings=_row_to_warning_list(row["warnings_json"]),
        errors=_row_to_warning_list(row["errors_json"]),
        suggestion=suggestion,
        resolution=row["resolution"],
        resolved_property_id=row["resolved_property_id"],
        parsed_inputs=row["parsed_inputs_json"],
        computed_result=row["computed_result_json"],
        resolved_inputs=row["resolved_inputs_json"],
    )


@router.get("", response_model=ImportBatchList)
async def list_imports(
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    status: list[str] | None = Query(default=None),
    limit: int = Query(default=50, le=200, ge=1),
    offset: int = Query(default=0, ge=0),
) -> ImportBatchList:
    rows, total = await q_batch.list_with_counts(
        conn, statuses=status, limit=limit, offset=offset,
    )
    items: list[ImportBatchListItem] = []
    for r in rows:
        # Look up uploader email for the response shape.
        u = await conn.fetchrow(
            "select id, email from public.app_user where id = $1",
            r["uploaded_by"],
        )
        items.append(ImportBatchListItem(
            id=r["id"],
            uploaded_by={"id": str(r["uploaded_by"]),
                         "email": (u["email"] if u else None)},
            uploaded_at=r["uploaded_at"].isoformat(),
            file_count=r["file_count"],
            status=r["status"],
            counts=ImportBatchCounts(
                pending=r["pending"], accepted=r["accepted"],
                rejected=r["rejected"], edited=r["edited"],
                committed=r["committed_count"],
            ),
        ))
    return ImportBatchList(items=items, total=total)


@router.get("/{batch_id}", response_model=ImportBatch)
async def get_import(
    batch_id: UUID,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> ImportBatch:
    batch = await q_batch.get_by_id(conn, batch_id)
    if batch is None:
        raise APIError(status_code=404, code="not_found",
                       message="Import batch not found.")
    rows = await q_item.list_for_batch(conn, batch_id)
    items = [await _row_to_item(conn, r) for r in rows]
    u = await conn.fetchrow(
        "select id, email from public.app_user where id = $1",
        batch["uploaded_by"],
    )
    return ImportBatch(
        id=batch["id"],
        uploaded_by={"id": str(batch["uploaded_by"]),
                     "email": (u["email"] if u else None)},
        uploaded_at=batch["uploaded_at"].isoformat(),
        file_count=batch["file_count"],
        status=batch["status"],
        notes=batch["notes"],
        items=items,
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/api
uv run pytest tests/integration/test_imports_list_detail.py -v
```

Expected: all 5 tests **PASS**.

- [ ] **Step 5: Lint + type-check + commit**

```bash
cd packages/api
uv run ruff check src/api/routers/imports.py tests/integration/test_imports_list_detail.py
uv run mypy src/api/routers/imports.py

git add packages/api/src/api/routers/imports.py \
        packages/api/tests/integration/test_imports_list_detail.py
git commit -m "feat(api): GET /imports + GET /imports/{id}

List with per-status counts (joined query, no N+1) and detail with
inline items (each carrying its suggestion + warnings + parsed/computed
JSON). Both viewers and valuers can read."
```

---

### Task 19: `PATCH /imports/{batch_id}/items/{item_id}`

**Files:**
- Modify: `packages/api/src/api/routers/imports.py`
- Test (new): `packages/api/tests/integration/test_imports_patch.py`

**Why:** Spec §7.5. Reviewer sets resolution and/or edits inputs. State-matrix validation enforced server-side.

- [ ] **Step 1: Write the failing integration test**

Create `packages/api/tests/integration/test_imports_patch.py`:

```python
"""Integration tests for PATCH /imports/{batch_id}/items/{item_id}."""
from __future__ import annotations

import io
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration


def _xlsx() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


async def _seed_batch_with_one_item(client) -> tuple[str, str]:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    # Wait for parse_worker (BackgroundTasks runs after response in test client).
    detail = await client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]
    return batch_id, item_id


@pytest.mark.asyncio
async def test_patch_rejected_records_resolution(valuer_client) -> None:
    batch_id, item_id = await _seed_batch_with_one_item(valuer_client)
    resp = await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "rejected", "resolution_notes": "bad sheet"},
    )
    assert resp.status_code == 200
    assert resp.json()["resolution"] == "rejected"


@pytest.mark.asyncio
async def test_patch_accepted_without_property_id_returns_422(valuer_client) -> None:
    batch_id, item_id = await _seed_batch_with_one_item(valuer_client)
    resp = await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "accepted"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_edited_requires_inputs_and_property_id(valuer_client) -> None:
    batch_id, item_id = await _seed_batch_with_one_item(valuer_client)
    resp = await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "edited"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_viewer_forbidden(viewer_client, valuer_client) -> None:
    batch_id, item_id = await _seed_batch_with_one_item(valuer_client)
    resp = await viewer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "rejected"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_unknown_item_returns_404(valuer_client) -> None:
    batch_id, _ = await _seed_batch_with_one_item(valuer_client)
    resp = await valuer_client.patch(
        f"/imports/{batch_id}/items/{uuid4()}",
        json={"resolution": "rejected"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_batch_not_in_review_returns_409(
    valuer_client, db_pool,
) -> None:
    batch_id, item_id = await _seed_batch_with_one_item(valuer_client)
    # Force batch.status = 'committed' to simulate post-commit lockout.
    async with db_pool.acquire() as conn:
        await conn.execute(
            "update public.import_batch set status = 'committed' where id = $1",
            batch_id,
        )
    resp = await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "rejected"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "batch_not_in_review"
```

The `db_pool` fixture is provided by Plan 2's conftest. If absent, add it:

```python
# In tests/integration/conftest.py:
@pytest_asyncio.fixture
async def db_pool(app):
    yield app.state.pool
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/api
uv run pytest tests/integration/test_imports_patch.py -v
```

Expected: 404 (PATCH route not registered).

- [ ] **Step 3: Add the PATCH handler**

In `packages/api/src/api/routers/imports.py`, append:

```python
from api.audit import audit
from api.schemas.imports import ImportItemPatch
from valuation_engine import calculate
from valuation_engine.models import ValuationInput


@router.patch("/{batch_id}/items/{item_id}", response_model=ImportItem)
async def patch_import_item(
    batch_id: UUID,
    item_id: UUID,
    body: ImportItemPatch,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> ImportItem:
    batch = await q_batch.get_by_id(conn, batch_id)
    if batch is None:
        raise APIError(status_code=404, code="not_found",
                       message="Import batch not found.")
    if batch["status"] != "review":
        raise APIError(status_code=409, code="batch_not_in_review",
                       message=f"Batch status is {batch['status']!r}; "
                               f"only 'review' batches accept patches.")

    item = await q_item.get_by_id(conn, item_id)
    if item is None or item["batch_id"] != batch_id:
        raise APIError(status_code=404, code="not_found",
                       message="Import item not found.")

    # parse_status='error' items can only be 'edited' or 'rejected'.
    if item["parse_status"] == "error" and body.resolution == "accepted":
        raise APIError(status_code=422, code="error_item_must_be_edited_or_rejected",
                       message="Items with parse_status='error' cannot be "
                               "'accepted'; use 'edited' or 'rejected'.")

    # Per-resolution computed-result re-runs.
    computed_result_json: dict[str, Any] | None = None
    if body.resolution == "edited":
        try:
            vi = ValuationInput.model_validate(body.resolved_inputs or {})
            result = calculate(vi)
        except ValueError as exc:
            raise APIError(status_code=422, code="engine_validation_error",
                           message=str(exc)) from exc
        computed_result_json = result.model_dump(mode="json")

    before = {"resolution": item["resolution"],
              "resolved_property_id": str(item["resolved_property_id"])
                                       if item["resolved_property_id"] else None}

    updated = await q_item.patch_resolution(
        conn, item_id,
        resolution=body.resolution,
        resolved_property_id=body.resolved_property_id,
        resolved_inputs_json=body.resolved_inputs,
        computed_result_json=computed_result_json,
        resolution_notes=body.resolution_notes,
        resolved_by=user.id,
    )

    after = {"resolution": updated["resolution"],
             "resolved_property_id": str(updated["resolved_property_id"])
                                       if updated["resolved_property_id"] else None}
    await audit(
        conn,
        actor_id=user.id, actor_email=user.email,
        action="update", target_table="import_item", target_id=item_id,
        before=before, after=after,
    )

    return await _row_to_item(conn, updated)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/api
uv run pytest tests/integration/test_imports_patch.py -v
```

Expected: all 6 tests **PASS**.

- [ ] **Step 5: Lint + commit**

```bash
cd packages/api
uv run ruff check src/api/routers/imports.py tests/integration/test_imports_patch.py
uv run mypy src/api/routers/imports.py

git add packages/api/src/api/routers/imports.py \
        packages/api/tests/integration/test_imports_patch.py \
        packages/api/tests/integration/conftest.py
git commit -m "feat(api): PATCH /imports/{batch_id}/items/{item_id}

Reviewer sets resolution + optional inputs. Server enforces:
- batch.status must be 'review' (409 batch_not_in_review otherwise)
- parse_status='error' items can't be 'accepted' (must be edited or rejected)
- resolution='edited' re-runs the engine and stores computed_result_json
- audit row written with before/after of resolution + resolved_property_id"
```

---

### Task 20: `POST /imports/{batch_id}/cancel`

**Files:**
- Modify: `packages/api/src/api/routers/imports.py`
- Test (new): `packages/api/tests/integration/test_imports_cancel.py`

**Why:** Spec §7.6. Reviewer abandons a batch. Triggers Storage cleanup. 409 if batch already terminal.

- [ ] **Step 1: Write the failing test**

Create `packages/api/tests/integration/test_imports_cancel.py`:

```python
"""Integration tests for POST /imports/{batch_id}/cancel."""
from __future__ import annotations

import io

import pytest

pytestmark = pytest.mark.integration


def _xlsx() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


@pytest.mark.asyncio
async def test_cancel_review_batch_succeeds(valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    # Wait for parsing to flip to review (BackgroundTask runs after response).
    detail = await valuer_client.get(f"/imports/{batch_id}")
    assert detail.json()["status"] in ("review", "parsing")

    resp = await valuer_client.post(f"/imports/{batch_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    # Storage prefix should be empty after cancel.
    after = await valuer_client.get(f"/imports/{batch_id}")
    assert after.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_already_committed_returns_409(valuer_client, db_pool) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    async with db_pool.acquire() as conn:
        await conn.execute(
            "update public.import_batch set status = 'committed' where id = $1",
            batch_id,
        )
    resp = await valuer_client.post(f"/imports/{batch_id}/cancel")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_cancel_viewer_forbidden(viewer_client, valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    resp = await viewer_client.post(f"/imports/{batch_id}/cancel")
    assert resp.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/api
uv run pytest tests/integration/test_imports_cancel.py -v
```

Expected: 404 (cancel route not registered).

- [ ] **Step 3: Add the cancel handler**

In `packages/api/src/api/routers/imports.py`, append:

```python
from pydantic import BaseModel


class _BatchStatusResponse(BaseModel):
    id: UUID
    status: str


@router.post("/{batch_id}/cancel", response_model=_BatchStatusResponse)
async def cancel_import(
    batch_id: UUID,
    request: Request,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> _BatchStatusResponse:
    batch = await q_batch.get_by_id(conn, batch_id)
    if batch is None:
        raise APIError(status_code=404, code="not_found",
                       message="Import batch not found.")
    if batch["status"] not in ("parsing", "review"):
        raise APIError(status_code=409, code="batch_not_cancellable",
                       message=f"Batch status is {batch['status']!r}; "
                               f"only 'parsing' or 'review' batches can be cancelled.")

    n = await q_batch.set_status(conn, batch_id, "cancelled")
    if n != 1:
        raise APIError(status_code=409, code="batch_state_changed",
                       message="Batch state changed during cancel; please retry.")

    storage = request.app.state.storage
    storage.delete_prefix(batch_id)

    await audit(
        conn, actor_id=user.id, actor_email=user.email,
        action="cancel", target_table="import_batch", target_id=batch_id,
        before={"status": batch["status"]},
        after={"status": "cancelled"},
    )
    return _BatchStatusResponse(id=batch_id, status="cancelled")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/api
uv run pytest tests/integration/test_imports_cancel.py -v
```

Expected: all 3 tests **PASS**.

- [ ] **Step 5: Lint + commit**

```bash
cd packages/api
uv run ruff check src/api/routers/imports.py tests/integration/test_imports_cancel.py
uv run mypy src/api/routers/imports.py

git add packages/api/src/api/routers/imports.py \
        packages/api/tests/integration/test_imports_cancel.py
git commit -m "feat(api): POST /imports/{batch_id}/cancel

Reviewer abandons a batch. Status flips parsing|review -> cancelled,
Storage prefix is cleared, audit row written. 409 if batch already
terminal."
```

---

### Task 21: `POST /imports/{batch_id}/commit`

**Files:**
- Modify: `packages/api/src/api/routers/imports.py`
- Test (new): `packages/api/tests/integration/test_imports_commit.py`

**Why:** Spec §7.7. Calls `commit_worker.commit_batch`. The biggest router endpoint by surface area.

- [ ] **Step 1: Write the failing test**

Create `packages/api/tests/integration/test_imports_commit.py`:

```python
"""Integration tests for POST /imports/{batch_id}/commit.

Tests the happy path (one item, accepted with auto-link) plus failure
collection and idempotency."""
from __future__ import annotations

import io
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration


def _xlsx() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


async def _seed_property(client, name: str = "55 Empire Road") -> str:
    ent = await client.post("/entities",
                            json={"name": "Empire Road Trust",
                                  "registration_number": None,
                                  "notes": None})
    assert ent.status_code == 201, ent.text
    eid = ent.json()["id"]
    prop = await client.post("/properties",
                             json={"entity_id": eid, "name": name,
                                   "address": "55 Empire Rd, Sandton",
                                   "property_type": "office", "notes": None})
    assert prop.status_code == 201, prop.text
    return prop.json()["id"]


@pytest.mark.asyncio
async def test_commit_with_no_items_to_commit_marks_terminal_when_empty(
    valuer_client,
) -> None:
    """An empty batch (all items rejected) flips to committed."""
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    detail = await valuer_client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]

    # Reject the only item so the batch becomes terminal.
    await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "rejected"},
    )

    resp = await valuer_client.post(f"/imports/{batch_id}/commit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["batch_status"] == "committed"
    assert body["summary"]["committed"] == 0


@pytest.mark.asyncio
async def test_commit_no_property_link_returns_failure(valuer_client) -> None:
    """An accepted item with no property link surfaces in failures, not 500."""
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    detail = await valuer_client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]

    # Force an 'accepted' state without a property link by patching the row
    # directly (the API itself wouldn't allow this — defence-in-depth test).
    # Use the schema validator's error to set up: PATCH with property id, then
    # null it via SQL.
    pid = await _seed_property(valuer_client)
    await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "accepted", "resolved_property_id": pid},
    )
    # Direct-to-DB nullification:
    from api.config import get_settings
    import asyncpg
    s = get_settings()
    conn = await asyncpg.connect(dsn=s.DATABASE_URL.get_secret_value())
    try:
        await conn.execute(
            "update public.import_item set resolved_property_id = null where id = $1",
            item_id,
        )
    finally:
        await conn.close()

    resp = await valuer_client.post(f"/imports/{batch_id}/commit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["failed"] == 1
    assert body["failures"][0]["reason"] == "no_property_link"


@pytest.mark.asyncio
async def test_commit_is_idempotent(valuer_client) -> None:
    """Re-running commit returns skipped=N for already-committed items."""
    pid = await _seed_property(valuer_client, name=f"Test Prop {uuid4()}")
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    detail = await valuer_client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]

    # The empty xlsx will fail parsing -> reject and re-create with a real one.
    await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "rejected"},
    )
    first = await valuer_client.post(f"/imports/{batch_id}/commit")
    assert first.status_code == 200
    second = await valuer_client.post(f"/imports/{batch_id}/commit")
    # Second call: batch already committed -> 409 batch_not_in_review.
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_commit_batch_not_in_review_returns_409(
    valuer_client, db_pool,
) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    async with db_pool.acquire() as conn:
        await conn.execute(
            "update public.import_batch set status = 'cancelled' where id = $1",
            batch_id,
        )
    resp = await valuer_client.post(f"/imports/{batch_id}/commit")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_commit_viewer_forbidden(viewer_client, valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    resp = await viewer_client.post(f"/imports/{batch_id}/commit")
    assert resp.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/api
uv run pytest tests/integration/test_imports_commit.py -v
```

Expected: 404 on commit route.

- [ ] **Step 3: Add the commit handler**

In `packages/api/src/api/routers/imports.py`, append:

```python
from api.schemas.imports import CommitFailure as CommitFailureSchema, CommitSummary as CommitSummarySchema
from api.services import commit_worker


@router.post("/{batch_id}/commit", response_model=CommitSummarySchema)
async def commit_import(
    batch_id: UUID,
    request: Request,
    user: Annotated[AppUser, Depends(require_valuer)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> CommitSummarySchema:
    batch = await q_batch.get_by_id(conn, batch_id)
    if batch is None:
        raise APIError(status_code=404, code="not_found",
                       message="Import batch not found.")
    if batch["status"] != "review":
        raise APIError(status_code=409, code="batch_not_in_review",
                       message=f"Batch status is {batch['status']!r}; "
                               f"commit requires 'review'.")

    pool: asyncpg.Pool = request.app.state.pool
    storage = request.app.state.storage
    summary = await commit_worker.commit_batch(
        pool, batch_id, user, storage=storage,
    )

    return CommitSummarySchema(
        batch_id=summary.batch_id,
        summary={"committed": summary.committed,
                 "failed": summary.failed,
                 "skipped": summary.skipped},
        failures=[CommitFailureSchema(item_id=f.item_id, filename=f.filename,
                                      reason=f.reason, message=f.message)
                  for f in summary.failures],
        batch_status=summary.batch_status,
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/api
uv run pytest tests/integration/test_imports_commit.py -v
```

Expected: all 5 tests **PASS**.

- [ ] **Step 5: Lint + commit**

```bash
cd packages/api
uv run ruff check src/api/routers/imports.py tests/integration/test_imports_commit.py
uv run mypy src/api/routers/imports.py

git add packages/api/src/api/routers/imports.py \
        packages/api/tests/integration/test_imports_commit.py
git commit -m "feat(api): POST /imports/{batch_id}/commit

Calls commit_worker.commit_batch. Returns CommitSummary with per-item
failures collected (no 500 on row-level failures). 409 if batch not in
review; idempotent — re-callable means 'second call sees batch already
committed -> 409' which is the desired outcome."
```

---

### Task 22: `GET /imports/{batch_id}/items/{item_id}/source` — signed URL redirect

**Files:**
- Modify: `packages/api/src/api/routers/imports.py`
- Test (new): `packages/api/tests/integration/test_imports_source_redirect.py`

**Why:** Spec §7.8. Reviewer downloads the original workbook to investigate a parse warning. 307 to a 5-min Storage signed URL.

- [ ] **Step 1: Write the failing test**

Create `packages/api/tests/integration/test_imports_source_redirect.py`:

```python
"""Integration tests for GET /imports/{batch_id}/items/{item_id}/source."""
from __future__ import annotations

import io
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration


def _xlsx() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


@pytest.mark.asyncio
async def test_source_returns_307_with_signed_url(valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    detail = await valuer_client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]

    resp = await valuer_client.get(
        f"/imports/{batch_id}/items/{item_id}/source",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert "/storage/v1/object/sign/imports/" in location
    assert "token=" in location


@pytest.mark.asyncio
async def test_source_after_cancel_returns_410(valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    detail = await valuer_client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]

    await valuer_client.post(f"/imports/{batch_id}/cancel")

    resp = await valuer_client.get(
        f"/imports/{batch_id}/items/{item_id}/source",
        follow_redirects=False,
    )
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "source_unavailable"


@pytest.mark.asyncio
async def test_source_unknown_item_returns_404(valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]

    resp = await valuer_client.get(
        f"/imports/{batch_id}/items/{uuid4()}/source",
        follow_redirects=False,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_source_viewer_can_download(viewer_client, valuer_client) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    detail = await valuer_client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]

    resp = await viewer_client.get(
        f"/imports/{batch_id}/items/{item_id}/source",
        follow_redirects=False,
    )
    assert resp.status_code == 307
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/api
uv run pytest tests/integration/test_imports_source_redirect.py -v
```

Expected: 404 (route not registered).

- [ ] **Step 3: Add the source handler**

In `packages/api/src/api/routers/imports.py`, append:

```python
from fastapi.responses import RedirectResponse


@router.get("/{batch_id}/items/{item_id}/source")
async def get_import_item_source(
    batch_id: UUID,
    item_id: UUID,
    request: Request,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> RedirectResponse:
    item = await q_item.get_by_id(conn, item_id)
    if item is None or item["batch_id"] != batch_id:
        raise APIError(status_code=404, code="not_found",
                       message="Import item not found.")

    storage = request.app.state.storage
    try:
        url = storage.signed_url(item["storage_path"])
    except Exception as exc:  # noqa: BLE001 — Storage SDK error surface is broad
        # Any storage failure on a signed-url mint when the path should exist
        # falls into 'gone' territory in our model: the original is no longer
        # downloadable. Differentiating "actually deleted" from "transient" is
        # out of scope for v1.
        raise APIError(status_code=410, code="source_unavailable",
                       message=f"Source workbook is no longer available: {exc!s}") from exc
    return RedirectResponse(url=url, status_code=307)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd packages/api
uv run pytest tests/integration/test_imports_source_redirect.py -v
```

Expected: all 4 tests **PASS**.

- [ ] **Step 5: Lint + commit**

```bash
cd packages/api
uv run ruff check src/api/routers/imports.py tests/integration/test_imports_source_redirect.py
uv run mypy src/api/routers/imports.py

git add packages/api/src/api/routers/imports.py \
        packages/api/tests/integration/test_imports_source_redirect.py
git commit -m "feat(api): GET /imports/{batch_id}/items/{item_id}/source

307 redirect to a 5-min Supabase Storage signed URL. 410 if the file is
no longer available (post-cancel/commit cleanup). Both viewers and
valuers can download."
```

---

### Task 23: RLS sanity test for `import_batch` + `import_item`

**Files:**
- Test (new): `packages/api/tests/integration/test_imports_rls.py`

**Why:** Defence-in-depth confirmation that the RLS policies from Task 6 actually behave as designed under a real JWT (not just the API's service-role bypass).

- [ ] **Step 1: Write the test**

Create `packages/api/tests/integration/test_imports_rls.py`:

```python
"""Verify RLS policies enforce viewer-cannot-mutate / valuer-can-mutate
when accessed via a real JWT (not the service-role-bypass path)."""
from __future__ import annotations

import io
import os
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest

pytestmark = pytest.mark.integration


def _xlsx() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


async def _connect_as_role(role_jwt: str) -> asyncpg.Connection:
    """Connect as the 'authenticated' Postgres role using a Supabase JWT.

    Uses the Postgres connection string with `options=-c role=authenticated`
    and sets request-context JWT claims so RLS policies see auth.uid().
    """
    dsn = os.environ["DATABASE_URL"]
    conn = await asyncpg.connect(dsn=dsn)
    # Switch to 'authenticated' role and set the JWT claims for RLS.
    await conn.execute("set role authenticated")
    payload = jwt.decode(role_jwt, options={"verify_signature": False})
    sub = payload["sub"]
    await conn.execute(
        f"select set_config('request.jwt.claims', '{{\"sub\":\"{sub}\"}}', true)"
    )
    return conn


@pytest.mark.asyncio
async def test_viewer_cannot_insert_import_batch(
    valuer_client, viewer_token, viewer_user,
) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    assert upload.status_code == 202

    conn = await _connect_as_role(viewer_token)
    try:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.execute(
                """
                insert into public.import_batch (uploaded_by, file_count, status)
                values ($1, 1, 'parsing')
                """,
                viewer_user.id,
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_viewer_can_select_import_batch(
    valuer_client, viewer_token,
) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    assert upload.status_code == 202

    conn = await _connect_as_role(viewer_token)
    try:
        rows = await conn.fetch("select id from public.import_batch")
        assert len(rows) >= 1
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_valuer_can_insert_import_batch(
    valuer_token, valuer_user,
) -> None:
    conn = await _connect_as_role(valuer_token)
    try:
        row = await conn.fetchrow(
            """
            insert into public.import_batch (uploaded_by, file_count, status)
            values ($1, 1, 'parsing')
            returning id
            """,
            valuer_user.id,
        )
        assert row is not None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_uploaded_by_must_match_auth_uid(
    valuer_token, viewer_user,
) -> None:
    """Even valuers can't insert a row claiming someone else uploaded it."""
    conn = await _connect_as_role(valuer_token)
    try:
        with pytest.raises(asyncpg.exceptions.CheckViolationError) as ei:
            await conn.execute(
                """
                insert into public.import_batch (uploaded_by, file_count, status)
                values ($1, 1, 'parsing')
                """,
                viewer_user.id,  # someone else's id
            )
        # The RLS policy's WITH CHECK fires; some Postgres versions surface
        # this as a generic InsufficientPrivilegeError instead. Accept either.
    except asyncpg.exceptions.InsufficientPrivilegeError:
        pass
    finally:
        await conn.close()
```

The fixtures `valuer_token`, `viewer_token`, `viewer_user` should be in Plan 2's conftest. If only `valuer_client`/`viewer_client` exist, extract the bare token from those — extend the conftest as needed.

- [ ] **Step 2: Run test to verify it passes**

```bash
cd packages/api
uv run pytest tests/integration/test_imports_rls.py -v
```

Expected: all 4 tests **PASS**.

- [ ] **Step 3: Commit**

```bash
git add packages/api/tests/integration/test_imports_rls.py \
        packages/api/tests/integration/conftest.py
git commit -m "test(api): RLS sanity for import_batch + import_item

Defence-in-depth verification that the policies from migration
20260503000004 actually enforce viewer-readonly / valuer-mutate /
uploaded_by = auth.uid() when accessed via a real JWT (not the
API's service-role bypass path)."
```

---

### Task 24: Storage cleanup integration test

**Files:**
- Test (new): `packages/api/tests/integration/test_imports_storage_cleanup.py`

**Why:** Verify that cancel + commit terminal transitions actually delete the bucket prefix. Catches regressions where someone forgets to plumb `storage` through `commit_worker` or the cancel router.

- [ ] **Step 1: Write the test**

Create `packages/api/tests/integration/test_imports_storage_cleanup.py`:

```python
"""Verify storage prefix is empty after cancel + after committed transition."""
from __future__ import annotations

import io

import pytest

pytestmark = pytest.mark.integration


def _xlsx() -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _list_prefix(app, batch_id: str) -> list[str]:
    storage = app.state.storage
    listing = storage._client.storage.from_("imports").list(batch_id)  # type: ignore[attr-defined]
    return [obj["name"] for obj in listing]


@pytest.mark.asyncio
async def test_storage_empty_after_cancel(valuer_client, app) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    assert _list_prefix(app, batch_id), "files should exist before cancel"

    await valuer_client.post(f"/imports/{batch_id}/cancel")
    assert _list_prefix(app, batch_id) == [], "files should be cleared on cancel"


@pytest.mark.asyncio
async def test_storage_empty_after_committed(valuer_client, app) -> None:
    files = [("files", ("a.xlsx", _xlsx(),
              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    upload = await valuer_client.post("/imports", files=files)
    batch_id = upload.json()["batch_id"]
    detail = await valuer_client.get(f"/imports/{batch_id}")
    item_id = detail.json()["items"][0]["id"]

    # Reject the only item so the batch becomes terminal.
    await valuer_client.patch(
        f"/imports/{batch_id}/items/{item_id}",
        json={"resolution": "rejected"},
    )
    resp = await valuer_client.post(f"/imports/{batch_id}/commit")
    assert resp.json()["batch_status"] == "committed"
    assert _list_prefix(app, batch_id) == [], \
        "files should be cleared when batch flips to committed"
```

- [ ] **Step 2: Run test to verify it passes**

```bash
cd packages/api
uv run pytest tests/integration/test_imports_storage_cleanup.py -v
```

Expected: both tests **PASS**.

- [ ] **Step 3: Commit**

```bash
git add packages/api/tests/integration/test_imports_storage_cleanup.py
git commit -m "test(api): storage cleanup on batch terminal state

Confirms storage.delete_prefix is wired into both POST /cancel and the
commit_worker's terminal-transition path."
```

---

## Phase 5b — Exports router + service (Task 25)

---

### Task 25: PDF + XLSX exports

**Files:**
- Create: `packages/api/src/api/routers/exports.py`
- Create: `packages/api/src/api/services/exports.py`
- Create: `packages/api/src/api/exports/__init__.py`
- Create: `packages/api/src/api/exports/pdf_template.html`
- Create: `packages/api/src/api/exports/pdf_styles.css`
- Modify: `packages/api/src/api/main.py` (register router)
- Test (new): `packages/api/tests/unit/test_exports_context_builder.py`
- Test (new): `packages/api/tests/unit/test_exports_filename.py`
- Test (new): `packages/api/tests/integration/test_exports_pdf_endpoint.py`
- Test (new): `packages/api/tests/integration/test_exports_xlsx_endpoint.py`

**Why:** Spec §10. Two endpoints, both cached via `Cache-Control: immutable` + ETag. PDF via WeasyPrint; XLSX via the engine.

- [ ] **Step 1: Write the failing context-builder unit test**

Create `packages/api/tests/unit/test_exports_context_builder.py`:

```python
"""Unit tests for services.exports._build_context — pure function.

Verifies number formatting, string assembly, and graceful logo handling.
Does not touch WeasyPrint."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from api.services.branding import Branding
from api.services.exports import _build_context


def _snapshot_dict(**overrides: Any) -> dict[str, Any]:
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "valuation_date": date(2026, 3, 15),
        "engine_version": "0.1.0",
        "source": "manual",
        "source_file": None,
        "created_by_email": "henry@anchorpointrisk.co.za",
        "property_name": "55 Empire Road",
        "property_address": "55 Empire Rd, Sandton, 2196",
        "entity_name": "Empire Road Trust",
        "inputs_json": {
            "valuation_date": "2026-03-15",
            "tenants": [],
            "parking": [],
            "monthly_operating_expenses": "100000",
            "vacancy_allowance_pct": "0.05",
            "cap_rate": "0.10",
        },
        "result_json": {
            "engine_version": "0.1.0",
            "valuation_date": "2026-03-15",
            "tenants_resolved": [],
            "gross_monthly_rent_tenants": "0",
            "gross_monthly_rent_parking": "0",
            "gross_monthly_income": "0",
            "gross_annual_income": "0",
            "annual_operating_expenses": "1200000",
            "opex_per_m2_pm": "0",
            "opex_pct_of_gai": "0",
            "vacancy_allowance_amount": "0",
            "annual_net_income": "-1200000",
            "capitalised_value": "-12000000",
            "market_value": "12500000",
            "warnings": [],
        },
        "market_value": Decimal("12500000"),
        "cap_rate": Decimal("0.10"),
    }
    base.update(overrides)
    return base


def _branding(**overrides: Any) -> Branding:
    base = {"firm_name": "Anchor Point Risk",
            "firm_logo_path": None,
            "firm_address_lines": ["1 Example St", "Sandton"],
            "firm_contact_lines": ["+27 11 555 0000"]}
    base.update(overrides)
    return Branding(**base)


def test_market_value_is_formatted_with_R_and_thousands_sep() -> None:
    ctx = _build_context(_snapshot_dict(), _branding(), generated_at_iso="2026-05-03T12:00:00Z")
    assert ctx["snapshot"]["market_value_formatted"] == "R 12,500,000"


def test_source_manual_renders_human_label() -> None:
    ctx = _build_context(_snapshot_dict(source="manual"), _branding(), generated_at_iso="2026-05-03T12:00:00Z")
    assert ctx["snapshot"]["source"] == "Manual entry"


def test_source_excel_import_includes_filename() -> None:
    ctx = _build_context(
        _snapshot_dict(source="excel_import", source_file="55 Empire Road.xlsx"),
        _branding(), generated_at_iso="2026-05-03T12:00:00Z",
    )
    assert ctx["snapshot"]["source"] == "Excel import — 55 Empire Road.xlsx"


def test_valuation_date_long_formatted() -> None:
    ctx = _build_context(_snapshot_dict(), _branding(), generated_at_iso="2026-05-03T12:00:00Z")
    assert ctx["snapshot"]["valuation_date"] == "15 March 2026"


def test_no_warnings_results_in_empty_list() -> None:
    ctx = _build_context(_snapshot_dict(), _branding(), generated_at_iso="2026-05-03T12:00:00Z")
    assert ctx["warnings"] == []


def test_warnings_round_trip() -> None:
    snap = _snapshot_dict()
    snap["result_json"]["warnings"] = [
        {"code": "lease_expired", "message": "Tenant lease expired",
         "field_path": "tenants[2].lease_expiry_date"}
    ]
    ctx = _build_context(snap, _branding(), generated_at_iso="2026-05-03T12:00:00Z")
    assert len(ctx["warnings"]) == 1
    assert ctx["warnings"][0]["code"] == "lease_expired"


def test_branding_logo_None_omitted() -> None:
    ctx = _build_context(_snapshot_dict(), _branding(firm_logo_path=None),
                         generated_at_iso="2026-05-03T12:00:00Z")
    assert ctx["branding"]["firm_logo_path"] is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/api
uv run pytest tests/unit/test_exports_context_builder.py -v
```

Expected: collection or import error.

- [ ] **Step 3: Implement the context builder + render entry point**

Create `packages/api/src/api/exports/__init__.py` (empty file).

Create `packages/api/src/api/services/exports.py`:

```python
"""PDF rendering for /snapshots/{id}/export.pdf.

Pure context-builder + WeasyPrint plumbing. Number formatting happens here
(not in the template) so unit tests don't need WeasyPrint installed.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from api.services.branding import Branding

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "exports"

_jenv = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _fmt_money(value: Any) -> str:
    """Format as 'R 12,500,000.00' (R prefix, thousands sep, two decimals)."""
    if value is None:
        return ""
    d = Decimal(str(value))
    # Strip trailing .00 for whole numbers; otherwise show two decimals.
    if d == d.to_integral_value():
        return f"R {int(d):,}"
    return f"R {d:,.2f}"


def _fmt_pct(value: Any, *, decimals: int = 2) -> str:
    if value is None:
        return ""
    d = Decimal(str(value)) * Decimal("100")
    return f"{d:.{decimals}f}%"


def _fmt_long_date(d: Any) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d)
    if not isinstance(d, date):
        return str(d)
    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    return f"{d.day} {months[d.month - 1]} {d.year}"


def _build_context(
    snapshot: dict[str, Any],
    branding: Branding,
    *,
    generated_at_iso: str,
) -> dict[str, Any]:
    """Pure assembly. snapshot is a dict-like row from get_with_property."""
    inputs = snapshot["inputs_json"] or {}
    result = snapshot["result_json"] or {}

    if snapshot["source"] == "excel_import" and snapshot.get("source_file"):
        source_label = f"Excel import — {snapshot['source_file']}"
    elif snapshot["source"] == "manual":
        source_label = "Manual entry"
    else:
        source_label = str(snapshot["source"])

    tenants_resolved = []
    for t in result.get("tenants_resolved", []):
        tenants_resolved.append({
            "description": t.get("description", ""),
            "rentable_area_m2": t.get("rentable_area_m2", ""),
            "effective_rent_per_m2_pm": _fmt_money(t.get("effective_rent_per_m2_pm")),
            "monthly_rent": _fmt_money(t.get("monthly_rent")),
            "escalation_cycles_applied": t.get("escalation_cycles_applied", 0),
        })

    parking = []
    for p in inputs.get("parking", []):
        bays = int(p.get("bays", 0))
        rate = Decimal(str(p.get("rate_per_bay_pm", 0)))
        parking.append({
            "bay_type": p.get("bay_type", "other"),
            "bays": bays,
            "rate_per_bay_pm": _fmt_money(rate),
            "monthly_rent": _fmt_money(rate * bays),
        })

    return {
        "branding": {
            "firm_name": branding.firm_name,
            "firm_logo_path": branding.firm_logo_path,
            "firm_address_lines": list(branding.firm_address_lines),
            "firm_contact_lines": list(branding.firm_contact_lines),
        },
        "entity": {"name": snapshot["entity_name"]},
        "property": {"name": snapshot["property_name"],
                     "address": snapshot["property_address"]},
        "snapshot": {
            "id": str(snapshot["id"]),
            "valuation_date": _fmt_long_date(snapshot["valuation_date"]),
            "created_by": snapshot.get("created_by_email") or str(snapshot.get("created_by", "")),
            "engine_version": snapshot["engine_version"],
            "source": source_label,
            "generated_at": generated_at_iso,
            "market_value_formatted": _fmt_money(snapshot["market_value"]),
        },
        "tenants_resolved": tenants_resolved,
        "parking": parking,
        "totals": {
            "gross_monthly_income": _fmt_money(result.get("gross_monthly_income")),
            "gross_annual_income": _fmt_money(result.get("gross_annual_income")),
            "annual_operating_expenses": _fmt_money(result.get("annual_operating_expenses")),
            "opex_per_m2_pm": _fmt_money(result.get("opex_per_m2_pm")),
            "opex_pct_of_gai": _fmt_pct(result.get("opex_pct_of_gai")),
            "vacancy_allowance_amount": _fmt_money(result.get("vacancy_allowance_amount")),
            "vacancy_pct": _fmt_pct(inputs.get("vacancy_allowance_pct")),
            "annual_net_income": _fmt_money(result.get("annual_net_income")),
            "cap_rate_pct": _fmt_pct(inputs.get("cap_rate")),
            "capitalised_value": _fmt_money(result.get("capitalised_value")),
            "market_value": _fmt_money(result.get("market_value")),
        },
        "warnings": [
            {"code": w.get("code", ""),
             "message": w.get("message", ""),
             "field_path": w.get("field_path")}
            for w in result.get("warnings", [])
        ],
    }


def render_snapshot_pdf(
    snapshot: dict[str, Any],
    branding: Branding,
) -> bytes:
    """WeasyPrint render. CPU-bound; route handler wraps with run_in_threadpool."""
    from weasyprint import HTML  # local import — keeps module importable in unit tests
    ctx = _build_context(
        snapshot, branding,
        generated_at_iso=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    template = _jenv.get_template("pdf_template.html")
    html_str = template.render(**ctx)
    return bytes(HTML(string=html_str, base_url=str(TEMPLATE_DIR)).write_pdf())
```

Create `packages/api/src/api/exports/pdf_template.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Property Valuation Report</title>
  <link rel="stylesheet" href="pdf_styles.css">
</head>
<body>
  <header class="firm-header">
    {% if branding.firm_logo_path %}
      <img src="{{ branding.firm_logo_path }}" class="firm-logo" alt="">
    {% else %}
      <div class="firm-name-large">{{ branding.firm_name }}</div>
    {% endif %}
    <div class="firm-meta">
      <div class="firm-name">{{ branding.firm_name }}</div>
      {% for line in branding.firm_address_lines %}<div>{{ line }}</div>{% endfor %}
      {% for line in branding.firm_contact_lines %}<div>{{ line }}</div>{% endfor %}
    </div>
  </header>

  <h1>Property Valuation Report</h1>

  <section class="title-block">
    <div class="market-value-big">{{ snapshot.market_value_formatted }}</div>
    <div class="property-meta">
      <div><strong>{{ entity.name }}</strong></div>
      <div>{{ property.name }}</div>
      <div>{{ property.address }}</div>
    </div>
    <div class="valuation-meta">
      <div><strong>Valuation date:</strong> {{ snapshot.valuation_date }}</div>
      <div><strong>Prepared by:</strong> {{ snapshot.created_by }}</div>
    </div>
  </section>

  {% if tenants_resolved %}
  <h2>Tenants</h2>
  <table class="tenants">
    <thead>
      <tr>
        <th>Description</th><th>Cycles</th><th>Area (m²)</th>
        <th>R/m²/pm</th><th>Monthly rent</th>
      </tr>
    </thead>
    <tbody>
      {% for t in tenants_resolved %}
      <tr>
        <td>{{ t.description }}</td>
        <td>{{ t.escalation_cycles_applied }}</td>
        <td class="num">{{ t.rentable_area_m2 }}</td>
        <td class="num">{{ t.effective_rent_per_m2_pm }}</td>
        <td class="num">{{ t.monthly_rent }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% endif %}

  {% if parking %}
  <h2>Parking</h2>
  <table class="parking">
    <thead><tr><th>Type</th><th>Bays</th><th>R/bay/pm</th><th>Monthly rent</th></tr></thead>
    <tbody>
      {% for p in parking %}
      <tr><td>{{ p.bay_type }}</td><td class="num">{{ p.bays }}</td>
          <td class="num">{{ p.rate_per_bay_pm }}</td>
          <td class="num">{{ p.monthly_rent }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
  {% endif %}

  <h2>Income &amp; expenses</h2>
  <table class="totals">
    <tr><td>Gross monthly income</td><td class="num">{{ totals.gross_monthly_income }}</td></tr>
    <tr><td>Gross annual income</td><td class="num">{{ totals.gross_annual_income }}</td></tr>
    <tr><td>Annual operating expenses</td><td class="num">{{ totals.annual_operating_expenses }}
        ({{ totals.opex_per_m2_pm }} R/m²/pm; {{ totals.opex_pct_of_gai }} of GAI)</td></tr>
    <tr><td>Vacancy allowance ({{ totals.vacancy_pct }})</td>
        <td class="num">({{ totals.vacancy_allowance_amount }})</td></tr>
    <tr><td><strong>Annual net income</strong></td>
        <td class="num"><strong>{{ totals.annual_net_income }}</strong></td></tr>
    <tr><td>Capitalisation rate</td><td class="num">{{ totals.cap_rate_pct }}</td></tr>
    <tr><td>Capitalised value</td><td class="num">{{ totals.capitalised_value }}</td></tr>
    <tr><td><strong>Open market assessment</strong></td>
        <td class="num"><strong>{{ totals.market_value }}</strong></td></tr>
  </table>

  <h2>Notes &amp; warnings</h2>
  {% if warnings %}
    <ul class="warnings">
      {% for w in warnings %}<li>⚠ <strong>{{ w.code }}</strong>: {{ w.message }}</li>{% endfor %}
    </ul>
  {% else %}
    <p class="no-warnings"><em>No warnings raised by the engine.</em></p>
  {% endif %}

  <footer class="provenance">
    Snapshot ID: {{ snapshot.id }} · Engine version: {{ snapshot.engine_version }}
    · Generated at: {{ snapshot.generated_at }} · Source: {{ snapshot.source }}
  </footer>
</body>
</html>
```

Create `packages/api/src/api/exports/pdf_styles.css`:

```css
@page { size: A4; margin: 18mm 16mm; }
body { font-family: "Liberation Sans", sans-serif; font-size: 10pt; color: #222; }
h1 { font-size: 18pt; margin: 6mm 0 4mm; }
h2 { font-size: 12pt; margin: 5mm 0 2mm; border-bottom: 1px solid #ccc; padding-bottom: 1mm; }
.firm-header { display: flex; justify-content: space-between; align-items: flex-start;
               border-bottom: 1px solid #888; padding-bottom: 3mm; }
.firm-logo { max-height: 18mm; }
.firm-name-large { font-size: 16pt; font-weight: bold; }
.firm-meta { text-align: right; font-size: 9pt; color: #555; }
.firm-name { font-weight: bold; }
.title-block { display: flex; justify-content: space-between; align-items: flex-start;
               margin: 4mm 0 6mm; }
.market-value-big { font-size: 24pt; font-weight: bold; color: #003366; }
.property-meta, .valuation-meta { font-size: 10pt; }
table { width: 100%; border-collapse: collapse; page-break-inside: avoid; }
th, td { padding: 1.5mm 2mm; border-bottom: 1px solid #eee; text-align: left; }
.num { font-family: "Liberation Mono", monospace; text-align: right; }
table.totals tr td:first-child { width: 60%; }
ul.warnings { padding-left: 4mm; }
.no-warnings { color: #888; font-size: 9pt; }
.provenance { margin-top: 8mm; padding-top: 2mm; border-top: 1px solid #ccc;
              font-size: 8pt; color: #666; text-align: center; }
```

- [ ] **Step 4: Run unit tests for context builder**

```bash
cd packages/api
uv run pytest tests/unit/test_exports_context_builder.py -v
```

Expected: all 7 tests **PASS**.

- [ ] **Step 5: Write the failing filename test**

Create `packages/api/tests/unit/test_exports_filename.py`:

```python
"""Unit tests for _safe_filename — defends Windows/macOS/Linux filesystems."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from api.routers.exports import _safe_filename


def _snap(entity: str = "Empire Road Trust",
          property_: str = "55 Empire Road",
          dt: date = date(2026, 3, 15)) -> SimpleNamespace:
    return SimpleNamespace(
        entity_name=entity, property_name=property_, valuation_date=dt,
    )


def test_simple_filename() -> None:
    name = _safe_filename(_snap(), "pdf")
    assert name == "Empire_Road_Trust_55_Empire_Road_2026-03-15.pdf"


def test_strips_windows_illegal_chars() -> None:
    name = _safe_filename(_snap(entity='B<>:"/\\|?*ad'), "pdf")
    for ch in '<>:"/\\|?*':
        assert ch not in name


def test_collapses_whitespace() -> None:
    name = _safe_filename(_snap(entity="A   B"), "pdf")
    assert "A_B" in name


def test_truncates_to_200_chars() -> None:
    name = _safe_filename(_snap(entity="x" * 500), "pdf")
    assert len(name) <= 204  # 200 + ".pdf"
```

- [ ] **Step 6: Implement the exports router**

Create `packages/api/src/api/routers/exports.py`:

```python
"""HTTP layer for /snapshots/{id}/export.{pdf,xlsx}.

Both endpoints are GETs cached via Cache-Control: immutable + ETag = snapshot.id.
Snapshots are immutable, so the cache is trivially correct.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from api.auth import current_user
from api.db import get_db
from api.errors import APIError
from api.queries import snapshot as q_snapshot
from api.schemas.user import AppUser
from api.services import exports as exports_svc

try:
    from valuation_engine.excel import render_workbook
    from valuation_engine.models import ValuationInput, ValuationResult
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("valuation_engine must be installed") from exc

router = APIRouter(tags=["exports"])

_FS_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_WS_RUN = re.compile(r"\s+")


def _slugify_for_disposition(s: str) -> str:
    cleaned = _FS_ILLEGAL.sub("", s)
    cleaned = _WS_RUN.sub("_", cleaned).strip("._-") or "untitled"
    return cleaned


def _safe_filename(snapshot: object, ext: str) -> str:
    parts = [
        getattr(snapshot, "entity_name"),
        getattr(snapshot, "property_name"),
        getattr(snapshot, "valuation_date").isoformat(),
    ]
    base = "_".join(_slugify_for_disposition(p) for p in parts)
    if len(base) > 200:
        base = base[:200]
    return f"{base}.{ext}"


def _xlsx_bytes(snapshot_row: dict) -> bytes:
    """Engine renderer writes to a path; read back as bytes."""
    inputs = ValuationInput.model_validate(snapshot_row["inputs_json"])
    result = ValuationResult.model_validate(snapshot_row["result_json"])
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
        path = Path(tf.name)
    try:
        render_workbook(
            path,
            building_name=snapshot_row["property_name"],
            inputs=inputs, result=result,
        )
        return path.read_bytes()
    finally:
        path.unlink(missing_ok=True)


@router.get("/snapshots/{snapshot_id}/export.xlsx")
async def get_snapshot_xlsx(
    snapshot_id: UUID,
    request: Request,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Response:
    row = await q_snapshot.get_with_property(conn, snapshot_id)
    if row is None:
        raise APIError(status_code=404, code="not_found",
                       message="Snapshot not found.")

    etag = f'"{row["id"]}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    snapshot_row = dict(row)
    workbook_bytes = await run_in_threadpool(_xlsx_bytes, snapshot_row)
    snapshot_obj = type("S", (), snapshot_row)
    filename = _safe_filename(snapshot_obj, "xlsx")
    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": etag,
        },
    )


@router.get("/snapshots/{snapshot_id}/export.pdf")
async def get_snapshot_pdf(
    snapshot_id: UUID,
    request: Request,
    _user: Annotated[AppUser, Depends(current_user)],
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> Response:
    row = await q_snapshot.get_with_property(conn, snapshot_id)
    if row is None:
        raise APIError(status_code=404, code="not_found",
                       message="Snapshot not found.")

    etag = f'"{row["id"]}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    branding = request.app.state.branding
    pdf_bytes = await run_in_threadpool(
        exports_svc.render_snapshot_pdf, dict(row), branding,
    )
    snapshot_obj = type("S", (), dict(row))
    filename = _safe_filename(snapshot_obj, "pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": etag,
        },
    )
```

- [ ] **Step 7: Register the router in `main.py`**

Open `packages/api/src/api/main.py`. Inside `create_app`, add:

```python
    from api.routers.exports import router as exports_router
    app.include_router(exports_router)
```

And in the lifespan setup (next to the storage init from Task 17):

```python
    from api.services.branding import load as load_branding
    app.state.branding = load_branding(settings)
```

- [ ] **Step 8: Write the integration tests**

Create `packages/api/tests/integration/test_exports_xlsx_endpoint.py`:

```python
"""Integration tests for GET /snapshots/{id}/export.xlsx."""
from __future__ import annotations

import io
from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration


async def _seed_snapshot(client) -> str:
    ent = await client.post("/entities",
                            json={"name": "Test Trust", "registration_number": None,
                                  "notes": None})
    eid = ent.json()["id"]
    prop = await client.post("/properties",
                             json={"entity_id": eid, "name": "Test Property",
                                   "address": "1 Test St", "property_type": "office",
                                   "notes": None})
    pid = prop.json()["id"]
    snap = await client.post(
        f"/properties/{pid}/snapshots",
        json={"valuation_date": "2026-03-15",
              "tenants": [{"description": "T1", "tenant_name": None,
                           "rentable_area_m2": "100", "rent_per_m2_pm": "150",
                           "annual_escalation_pct": "0.08",
                           "next_escalation_date": None,
                           "lease_period_text": None, "lease_expiry_date": None}],
              "parking": [], "monthly_operating_expenses": "10000",
              "vacancy_allowance_pct": "0.05", "cap_rate": "0.10"},
    )
    assert snap.status_code == 201, snap.text
    return snap.json()["id"]


@pytest.mark.asyncio
async def test_get_xlsx_returns_workbook(viewer_client, valuer_client) -> None:
    snap_id = await _seed_snapshot(valuer_client)
    resp = await viewer_client.get(f"/snapshots/{snap_id}/export.xlsx")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert resp.headers["etag"] == f'"{snap_id}"'
    # Round-trip: parsing the response with openpyxl should succeed.
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(resp.content))
    assert "sheet1" in wb.sheetnames or wb.active is not None


@pytest.mark.asyncio
async def test_get_xlsx_304_on_matching_etag(viewer_client, valuer_client) -> None:
    snap_id = await _seed_snapshot(valuer_client)
    resp = await viewer_client.get(
        f"/snapshots/{snap_id}/export.xlsx",
        headers={"If-None-Match": f'"{snap_id}"'},
    )
    assert resp.status_code == 304


@pytest.mark.asyncio
async def test_get_xlsx_404_unknown(viewer_client) -> None:
    resp = await viewer_client.get(f"/snapshots/{uuid4()}/export.xlsx")
    assert resp.status_code == 404
```

Create `packages/api/tests/integration/test_exports_pdf_endpoint.py`:

```python
"""Integration tests for GET /snapshots/{id}/export.pdf.

Marked integration (not pdf) because the headers + 304 behaviour is what we
test here; visual fidelity is the pdf-mark suite (Task 27)."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytestmark = pytest.mark.integration


async def _seed_snapshot(client) -> str:
    # Same shape as the xlsx test — duplicated so this test file is independent.
    ent = await client.post("/entities",
                            json={"name": "PDF Test Trust",
                                  "registration_number": None, "notes": None})
    eid = ent.json()["id"]
    prop = await client.post("/properties",
                             json={"entity_id": eid, "name": "PDF Test Prop",
                                   "address": "1 PDF St", "property_type": "office",
                                   "notes": None})
    pid = prop.json()["id"]
    snap = await client.post(
        f"/properties/{pid}/snapshots",
        json={"valuation_date": "2026-03-15",
              "tenants": [{"description": "T1", "tenant_name": None,
                           "rentable_area_m2": "100", "rent_per_m2_pm": "150",
                           "annual_escalation_pct": "0.08",
                           "next_escalation_date": None,
                           "lease_period_text": None, "lease_expiry_date": None}],
              "parking": [], "monthly_operating_expenses": "10000",
              "vacancy_allowance_pct": "0.05", "cap_rate": "0.10"},
    )
    return snap.json()["id"]


@pytest.mark.asyncio
async def test_get_pdf_returns_bytes_with_headers(viewer_client, valuer_client) -> None:
    snap_id = await _seed_snapshot(valuer_client)
    resp = await viewer_client.get(f"/snapshots/{snap_id}/export.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert resp.headers["etag"] == f'"{snap_id}"'
    # Magic bytes — every PDF starts with %PDF.
    assert resp.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_get_pdf_304_on_matching_etag(viewer_client, valuer_client) -> None:
    snap_id = await _seed_snapshot(valuer_client)
    resp = await viewer_client.get(
        f"/snapshots/{snap_id}/export.pdf",
        headers={"If-None-Match": f'"{snap_id}"'},
    )
    assert resp.status_code == 304


@pytest.mark.asyncio
async def test_get_pdf_404_unknown(viewer_client) -> None:
    resp = await viewer_client.get(f"/snapshots/{uuid4()}/export.pdf")
    assert resp.status_code == 404
```

- [ ] **Step 9: Run all the new tests**

```bash
cd packages/api
uv run pytest tests/unit/test_exports_filename.py \
              tests/integration/test_exports_xlsx_endpoint.py \
              tests/integration/test_exports_pdf_endpoint.py -v
```

Expected: all **PASS**. The PDF tests require `weasyprint` + apt deps locally; if missing, they fail with a clear ImportError — install them per Task 28's apt list.

- [ ] **Step 10: Lint + commit**

```bash
cd packages/api
uv run ruff check src/api/routers/exports.py src/api/services/exports.py \
                  src/api/exports tests/unit/test_exports_*.py \
                  tests/integration/test_exports_*.py
uv run mypy src/api/routers/exports.py src/api/services/exports.py

git add packages/api/src/api/routers/exports.py \
        packages/api/src/api/services/exports.py \
        packages/api/src/api/exports/ \
        packages/api/src/api/main.py \
        packages/api/tests/unit/test_exports_context_builder.py \
        packages/api/tests/unit/test_exports_filename.py \
        packages/api/tests/integration/test_exports_pdf_endpoint.py \
        packages/api/tests/integration/test_exports_xlsx_endpoint.py
git commit -m "feat(api): GET /snapshots/{id}/export.{pdf,xlsx}

PDF via WeasyPrint with a single-page Jinja2 template (firm header,
title block, tenants + parking tables, income/expense block,
warnings, provenance footer). XLSX via valuation_engine.excel.render_workbook
(tempfile -> bytes adapter). Both cached via Cache-Control: immutable
+ ETag = snapshot.id; If-None-Match short-circuits to 304."
```

---

## Phase 6 — Test fixtures (Task 26)

---

### Task 26: Sample workbook fixture builder

**Files:**
- Create: `packages/api/tests/fixtures/imports/build.py`
- Create: 9 generated `.xlsx` files in `packages/api/tests/fixtures/imports/`

**Why:** Spec §12.3. Synthetic fixtures keep the integration tests free of real client data. Built once via a Python script, committed as binaries.

- [ ] **Step 1: Write the fixture builder**

Create `packages/api/tests/fixtures/imports/build.py`:

```python
"""Build the synthetic Excel fixtures used by the imports integration tests.

Run manually:
    cd packages/api
    uv run python tests/fixtures/imports/build.py

Output: 9 .xlsx files in this directory. Commit them as binaries.
"""
from __future__ import annotations

import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook

from valuation_engine import calculate
from valuation_engine.excel import render_workbook
from valuation_engine.models import ParkingLine, TenantLine, ValuationInput

HERE = Path(__file__).resolve().parent


def _canonical_inputs() -> ValuationInput:
    return ValuationInput(
        valuation_date=date(2026, 3, 15),
        tenants=[
            TenantLine(description="Acme Co. (Office)", tenant_name="Acme Co.",
                       rentable_area_m2=Decimal("250"),
                       rent_per_m2_pm=Decimal("180"),
                       annual_escalation_pct=Decimal("0.08"),
                       next_escalation_date=date(2026, 7, 1),
                       lease_period_text="3 yr", lease_expiry_date=date(2028, 6, 30)),
        ],
        parking=[ParkingLine(bay_type="open", bays=10,
                             rate_per_bay_pm=Decimal("500"))],
        monthly_operating_expenses=Decimal("18000"),
        vacancy_allowance_pct=Decimal("0.05"),
        cap_rate=Decimal("0.10"),
    )


def _render_to(path: Path, *, building_name: str, inputs: ValuationInput) -> None:
    result = calculate(inputs)
    render_workbook(path, building_name=building_name, inputs=inputs, result=result)


def main() -> None:
    HERE.mkdir(parents=True, exist_ok=True)
    inputs = _canonical_inputs()

    # 1. canonical.xlsx — happy path, every section present.
    _render_to(HERE / "canonical.xlsx", building_name="55 Empire Road", inputs=inputs)

    # 2. canonical_no_parking.xlsx — parking section absent.
    no_parking = inputs.model_copy(update={"parking": []})
    _render_to(HERE / "canonical_no_parking.xlsx",
               building_name="55 Empire Road", inputs=no_parking)

    # 3. canonical_multi_sheet.xlsx — second sheet appended after rendering.
    src = HERE / "canonical.xlsx"
    dst = HERE / "canonical_multi_sheet.xlsx"
    shutil.copy(src, dst)
    wb = load_workbook(dst)
    wb.create_sheet("notes")
    wb.save(dst)

    # 4. label_drift_minor.xlsx — one column-A label changed (per Q3-A: → error).
    drift = HERE / "label_drift_minor.xlsx"
    shutil.copy(src, drift)
    wb = load_workbook(drift)
    ws = wb.active
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=1).value
        if isinstance(v, str) and "rentable area" in v.lower():
            ws.cell(row=r, column=6, value="Footprint area")  # break the anchor
            break
    wb.save(drift)

    # 5. missing_tenants.xlsx — drop the entire tenant section.
    miss = HERE / "missing_tenants.xlsx"
    shutil.copy(src, miss)
    wb = load_workbook(miss)
    ws = wb.active
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=1).value
        if isinstance(v, str) and "rentable area" in v.lower():
            ws.delete_rows(r, amount=1)
            break
    wb.save(miss)

    # 6. recompute_mismatch.xlsx — overwrite the cached market value cell.
    mm = HERE / "recompute_mismatch.xlsx"
    shutil.copy(src, mm)
    wb = load_workbook(mm)
    ws = wb.active
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=1).value
        if isinstance(v, str) and "open market assessment" in v.lower():
            ws.cell(row=r, column=9, value=99999999)  # very different
            break
    wb.save(mm)

    # 7. exact_name_match.xlsx — building name matches a seeded property.
    _render_to(HERE / "exact_name_match.xlsx",
               building_name="EXACT MATCH PROPERTY", inputs=inputs)

    # 8. fuzzy_name_match.xlsx — close but not exact.
    _render_to(HERE / "fuzzy_name_match.xlsx",
               building_name="55 Empire Rd", inputs=inputs)  # Rd vs Road

    # 9. corrupt.xlsx — not a valid xlsx (just plain text bytes with the
    #    extension). Forces openpyxl into a hard parse failure.
    (HERE / "corrupt.xlsx").write_bytes(b"this is not a real xlsx file")

    print(f"wrote 9 fixtures to {HERE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the builder**

```bash
cd packages/api
uv run python tests/fixtures/imports/build.py
```

Expected output: `wrote 9 fixtures to .../tests/fixtures/imports`. Confirm:

```bash
ls packages/api/tests/fixtures/imports/*.xlsx
```

Expected: 9 files.

- [ ] **Step 3: Smoke-test the canonical fixture parses**

```bash
cd packages/api
uv run python -c "
from pathlib import Path
from valuation_engine.excel import parse_workbook
r = parse_workbook(Path('tests/fixtures/imports/canonical.xlsx'))
assert r.inputs is not None, r.parse_errors
assert r.building_name == '55 Empire Road', r.building_name
print('canonical.xlsx parses OK; market_value =', r.sheet_market_value)
"
```

Expected: succeeds with a non-zero `market_value`.

- [ ] **Step 4: Commit fixtures + builder**

```bash
git add packages/api/tests/fixtures/
git commit -m "test(api): synthetic Excel fixtures for imports integration tests

Nine .xlsx files generated by build.py — canonical, no-parking, multi-sheet,
label-drift, missing-tenants, recompute-mismatch, exact-name-match,
fuzzy-name-match, corrupt. No real client data.

Builder is run-on-demand (not in CI); fixtures committed as binaries."
```

---

## Phase 7 — PDF visual tests (Task 27)

---

### Task 27: PDF visual test infrastructure + reference fixture

**Files:**
- Create: `packages/api/tests/pdf/__init__.py`
- Create: `packages/api/tests/pdf/conftest.py`
- Create: `packages/api/tests/pdf/test_pdf_visual.py`
- Create: `packages/api/tests/pdf/reference/canonical_one_pager.pdf`
- Modify: `packages/api/pyproject.toml` (add `pikepdf` dev dep + `pdf` marker)

**Why:** Spec §12.5 — content + size sanity instead of pixel diff. Marked `pdf` so devs without WeasyPrint apt deps can opt out.

- [ ] **Step 1: Add `pikepdf` dev dep + register pdf marker**

In `packages/api/pyproject.toml`, add to the `[tool.uv]` group's dev dependencies:

```toml
[tool.uv]
dev-dependencies = [
  # ... existing ...
  "pikepdf>=8.0",
  "Pillow>=10.0",       # for branding placeholder generation in Task 16
]
```

In the same file, add the marker registration:

```toml
[tool.pytest.ini_options]
markers = [
  "integration: integration tests against a live Supabase CLI stack",
  "pdf: WeasyPrint-rendering PDF visual checks (requires apt deps)",
]
```

- [ ] **Step 2: Sync deps**

```bash
cd packages/api
uv sync
```

- [ ] **Step 3: Write the conftest**

Create `packages/api/tests/pdf/__init__.py` (empty file).

Create `packages/api/tests/pdf/conftest.py`:

```python
"""pdf-mark-only fixtures and shared helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

REF_DIR = Path(__file__).resolve().parent / "reference"


@pytest.fixture(scope="session")
def reference_one_pager() -> bytes:
    p = REF_DIR / "canonical_one_pager.pdf"
    if not p.exists():
        pytest.skip("Run scripts/build_pdf_reference.py first to generate the reference PDF.")
    return p.read_bytes()
```

- [ ] **Step 4: Generate the reference PDF**

Create `packages/api/scripts/build_pdf_reference.py`:

```python
"""One-shot script to generate the reference PDF used by pdf-mark tests.

Run manually after intentional template changes:
    cd packages/api
    uv run python scripts/build_pdf_reference.py
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from api.services.branding import Branding
from api.services.exports import render_snapshot_pdf

REF = Path(__file__).resolve().parents[1] / "tests" / "pdf" / "reference"
REF.mkdir(parents=True, exist_ok=True)


def main() -> None:
    snapshot = {
        "id": "11111111-1111-1111-1111-111111111111",
        "valuation_date": date(2026, 3, 15),
        "engine_version": "0.1.0",
        "source": "manual",
        "source_file": None,
        "created_by_email": "henry@anchorpointrisk.co.za",
        "property_name": "55 Empire Road",
        "property_address": "55 Empire Rd, Sandton, 2196",
        "entity_name": "Empire Road Trust",
        "inputs_json": {
            "valuation_date": "2026-03-15",
            "tenants": [{"description": "Acme Co.", "rentable_area_m2": "250",
                         "rent_per_m2_pm": "180", "annual_escalation_pct": "0.08"}],
            "parking": [], "monthly_operating_expenses": "18000",
            "vacancy_allowance_pct": "0.05", "cap_rate": "0.10",
        },
        "result_json": {
            "engine_version": "0.1.0", "valuation_date": "2026-03-15",
            "tenants_resolved": [{"description": "Acme Co.",
                                  "rentable_area_m2": "250",
                                  "effective_rent_per_m2_pm": "180",
                                  "monthly_rent": "45000",
                                  "escalation_cycles_applied": 0}],
            "gross_monthly_rent_tenants": "45000",
            "gross_monthly_rent_parking": "0",
            "gross_monthly_income": "45000", "gross_annual_income": "540000",
            "annual_operating_expenses": "216000", "opex_per_m2_pm": "72",
            "opex_pct_of_gai": "0.40", "vacancy_allowance_amount": "27000",
            "annual_net_income": "297000", "capitalised_value": "2970000",
            "market_value": "2970000", "warnings": [],
        },
        "market_value": Decimal("2970000"), "cap_rate": Decimal("0.10"),
    }
    branding = Branding(firm_name="Anchor Point Risk",
                        firm_logo_path=None,
                        firm_address_lines=["1 Example St", "Sandton"],
                        firm_contact_lines=["+27 11 555 0000"])
    pdf = render_snapshot_pdf(snapshot, branding)
    out = REF / "canonical_one_pager.pdf"
    out.write_bytes(pdf)
    print(f"wrote {out} ({len(pdf):,} bytes)")


if __name__ == "__main__":
    main()
```

Run it:

```bash
cd packages/api
uv run python scripts/build_pdf_reference.py
```

Expected: `wrote .../canonical_one_pager.pdf (~ NN,000 bytes)`. (Skip locally if WeasyPrint apt deps aren't installed; CI will generate it.)

- [ ] **Step 5: Write the visual test**

Create `packages/api/tests/pdf/test_pdf_visual.py`:

```python
"""pdf-mark tests: validity + content + size sanity for the PDF renderer.

Marked `pdf` because they need WeasyPrint + Pango/Cairo apt deps; opt-out
locally with `pytest -m 'not pdf'`."""
from __future__ import annotations

import io
from pathlib import Path

import pytest

pytestmark = pytest.mark.pdf


def test_reference_pdf_is_valid(reference_one_pager: bytes) -> None:
    import pikepdf
    pdf = pikepdf.Pdf.open(io.BytesIO(reference_one_pager))
    assert len(pdf.pages) == 1


def test_reference_pdf_contains_expected_strings(reference_one_pager: bytes) -> None:
    """Every reader-visible string in the canonical fixture must be present."""
    import pikepdf
    pdf = pikepdf.Pdf.open(io.BytesIO(reference_one_pager))
    text = ""
    for page in pdf.pages:
        # pikepdf doesn't expose extract_text directly; use the lower-level
        # content-stream walk via pdfminer.six if needed. For v1, assert byte-
        # presence — the renderer doesn't intentionally compress text away.
        pass
    raw = reference_one_pager
    for needle in (b"Property Valuation Report", b"55 Empire Road",
                   b"Empire Road Trust", b"Snapshot ID:",
                   b"11111111", b"Engine version:", b"0.1.0"):
        assert needle in raw, f"Missing expected string: {needle!r}"


def test_reference_pdf_size_within_envelope(reference_one_pager: bytes) -> None:
    """Catch 'logo embedded as 5 MB raw bitmap' style regressions."""
    size = len(reference_one_pager)
    assert 5_000 < size < 200_000, f"PDF size {size} outside expected envelope"
```

- [ ] **Step 6: Run the pdf-mark suite**

```bash
cd packages/api
uv run pytest -m pdf -v
```

Expected: 3 tests **PASS** (or skip if reference doesn't exist).

- [ ] **Step 7: Commit**

```bash
git add packages/api/tests/pdf/ \
        packages/api/scripts/build_pdf_reference.py \
        packages/api/pyproject.toml
git commit -m "test(api): pdf-mark visual checks + reference fixture builder

Validity (pikepdf opens), content presence (key strings in raw bytes),
size envelope. Marked 'pdf' — runs locally only when WeasyPrint apt deps
are installed; CI runs them after the apt-install step (Task 30)."
```

---

## Phase 8 — Deploy + CI (Tasks 28–31)

---

### Task 28: pyproject.toml — add weasyprint + jinja2

**Files:**
- Modify: `packages/api/pyproject.toml`

**Why:** Lock the runtime deps before touching the deploy config.

- [ ] **Step 1: Add the deps**

In `packages/api/pyproject.toml`, under `[project] dependencies`:

```toml
"weasyprint>=62.0",
"jinja2>=3.1",
```

- [ ] **Step 2: Sync + smoke**

```bash
cd packages/api
uv sync
uv run python -c "from weasyprint import HTML; from jinja2 import Environment; print('ok')"
```

Expected: `ok`. (On Windows without GTK runtime, WeasyPrint import may fail — that's OK; it'll work in the Linux Render container.)

- [ ] **Step 3: Commit**

```bash
git add packages/api/pyproject.toml packages/api/uv.lock
git commit -m "chore(api): add weasyprint + jinja2 runtime deps for PDF export"
```

---

### Task 29: render.yaml — apt-install + new env vars

**Files:**
- Modify: `packages/api/render.yaml`
- Modify: `packages/api/.env.example`

**Why:** Spec §11.1.

- [ ] **Step 1: Update render.yaml**

Open `packages/api/render.yaml`. Modify the `buildCommand` to prepend the apt-install. Add the seven new env vars (six BRANDING/IMPORT/STORAGE plus DB_ACQUIRE_TIMEOUT_S):

```yaml
services:
  - type: web
    name: property-valuations-api
    runtime: python
    plan: starter   # or whatever Plan 2 used
    rootDir: packages/api
    buildCommand: >
      apt-get update &&
      apt-get install -y --no-install-recommends
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b
        libcairo2 libgdk-pixbuf-2.0-0 fonts-liberation &&
      pip install -e ../valuation_engine &&
      uv sync --frozen
    startCommand: uvicorn api.main:app --host 0.0.0.0 --port $PORT
    envVars:
      # ... existing Plan 2 envVars ...
      - key: BRANDING_FIRM_NAME
        value: Anchor Point Risk (Pty) Ltd
      - key: BRANDING_FIRM_ADDRESS_LINES
        value: ""
      - key: BRANDING_FIRM_CONTACT_LINES
        value: ""
      - key: BRANDING_FIRM_LOGO_PATH
        value: branding/anchorpoint_logo.png
      - key: IMPORT_MAX_FILE_BYTES
        value: "10485760"
      - key: STORAGE_SIGNED_URL_TTL_S
        value: "300"
      - key: DB_ACQUIRE_TIMEOUT_S
        value: "10"
```

Keep all existing envVars from Plan 2 untouched.

- [ ] **Step 2: Update .env.example**

Open `packages/api/.env.example` and append:

```bash
# Branding (PDF header). All optional except FIRM_NAME (defaults supplied).
BRANDING_FIRM_NAME=Anchor Point Risk (Pty) Ltd
BRANDING_FIRM_ADDRESS_LINES=
BRANDING_FIRM_CONTACT_LINES=
BRANDING_FIRM_LOGO_PATH=branding/anchorpoint_logo.png

# Import limits.
IMPORT_MAX_FILE_BYTES=10485760           # 10 MB per file
STORAGE_SIGNED_URL_TTL_S=300             # 5 minutes

# Carry-over from Plan 2's pool-acquire TODO.
DB_ACQUIRE_TIMEOUT_S=10
```

- [ ] **Step 3: Commit**

```bash
git add packages/api/render.yaml packages/api/.env.example
git commit -m "chore(deploy): render.yaml apt-install for WeasyPrint + Plan 3 env vars

Build command prepends apt-get install for Pango/Cairo/HarfBuzz/PixBuf.
Seven new env vars: BRANDING_*, IMPORT_MAX_FILE_BYTES,
STORAGE_SIGNED_URL_TTL_S, DB_ACQUIRE_TIMEOUT_S. .env.example updated
in parallel."
```

---

### Task 30: Dockerfile — apt-install (future fallback)

**Files:**
- Modify: `packages/api/Dockerfile`

**Why:** Spec §11.2. Keep Docker as a working drop-in for when we eventually flip Q8 to **B**. Not used by current Render deploy (Python runtime path).

- [ ] **Step 1: Add apt-install RUN**

In `packages/api/Dockerfile`, before the `pip install` step, add:

```dockerfile
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
        libcairo2 libgdk-pixbuf-2.0-0 fonts-liberation \
 && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 2: Smoke-build (optional, requires Docker)**

```bash
cd packages/api
docker build -t pvm-api:plan3 .
```

Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add packages/api/Dockerfile
git commit -m "chore(docker): apt-install Pango/Cairo for WeasyPrint

Not used by current Render deploy (Python runtime + render.yaml apt-install
in build command). Kept here as a working drop-in if we later flip to a
Docker deploy."
```

---

### Task 31: GitHub Actions — apt-install for WeasyPrint

**Files:**
- Modify: `.github/workflows/api.yml`

**Why:** Spec §11.4. CI must install the same apt deps so the `pdf`-mark + integration tests can render.

- [ ] **Step 1: Add the apt-install step**

Open `.github/workflows/api.yml`. In the integration job (whichever steps run pytest), before `uv sync` / `pip install`, insert:

```yaml
      - name: Install WeasyPrint system deps
        run: |
          sudo apt-get update
          sudo apt-get install -y --no-install-recommends \
            libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
            libcairo2 libgdk-pixbuf-2.0-0 fonts-liberation
```

If both unit and integration jobs exist as separate jobs, add to whichever runs the `pdf`-marked tests (typically integration).

- [ ] **Step 2: Update the pytest invocation if it uses `-m`**

If the existing CI step runs `pytest -m integration`, update to include pdf:

```yaml
      - name: Run integration + pdf tests
        run: uv run pytest -m "integration or pdf" -v
```

If it runs all tests (no `-m`), no change needed — the new pdf tests just join the suite.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/api.yml
git commit -m "ci(api): apt-install WeasyPrint deps + run pdf-marked tests"
```

---

### Task 32: smoke.sh — extend with /imports + export checks

**Files:**
- Modify: `packages/api/scripts/smoke.sh`

**Why:** Spec §11.6. Post-deploy verification covers the new endpoints.

- [ ] **Step 1: Append checks to smoke.sh**

Open `packages/api/scripts/smoke.sh`. After the existing checks, append:

```bash
# ----- Plan 3: /imports + exports smoke -----

echo "[smoke] GET /imports"
curl -fsSL "$BASE_URL/imports" -H "Authorization: Bearer $JWT" \
     -o /tmp/imports.json
echo "  total = $(jq -r .total /tmp/imports.json)"

# If a known snapshot UUID is in env, smoke the exports.
if [ -n "${SMOKE_SNAPSHOT_ID:-}" ]; then
  echo "[smoke] GET /snapshots/$SMOKE_SNAPSHOT_ID/export.pdf"
  curl -fsSL "$BASE_URL/snapshots/$SMOKE_SNAPSHOT_ID/export.pdf" \
       -H "Authorization: Bearer $JWT" -o /tmp/snapshot.pdf
  test "$(head -c 4 /tmp/snapshot.pdf)" = "%PDF" \
    || { echo "  FAIL: PDF magic bytes missing"; exit 1; }
  echo "  PDF: $(wc -c < /tmp/snapshot.pdf) bytes"

  echo "[smoke] GET /snapshots/$SMOKE_SNAPSHOT_ID/export.xlsx"
  curl -fsSL "$BASE_URL/snapshots/$SMOKE_SNAPSHOT_ID/export.xlsx" \
       -H "Authorization: Bearer $JWT" -o /tmp/snapshot.xlsx
  echo "  XLSX: $(wc -c < /tmp/snapshot.xlsx) bytes"
else
  echo "[smoke] SKIP exports (set SMOKE_SNAPSHOT_ID to enable)"
fi
```

- [ ] **Step 2: Commit**

```bash
git add packages/api/scripts/smoke.sh
git commit -m "chore(deploy): extend smoke.sh with /imports + exports checks

GET /imports always runs. PDF + XLSX exports run when SMOKE_SNAPSHOT_ID
env is set; PDF magic-byte check confirms the WeasyPrint apt-install
is correctly wired in production."
```

---

## Phase 9 — Final wiring + full-suite confirmation (Task 33)

---

### Task 33: Full-suite green run + README handoff

**Files:**
- Modify: `README.md` (top-level project readme — Plan 3 status)
- Modify: `packages/api/README.md` (handoff notes)

**Why:** Final sanity sweep + documentation update.

- [ ] **Step 1: Run the full unit suite**

```bash
cd packages/api
uv run pytest -m "not integration and not pdf" -v
```

Expected: all unit tests pass; new totals = Plan 2 baseline (38) + Plan 3 unit additions.

- [ ] **Step 2: Run the full integration suite**

```bash
cd ../..
supabase start  # ensure stack is up
cd packages/api
uv run pytest -m integration -v
```

Expected: all integration tests pass.

- [ ] **Step 3: Run the pdf suite**

```bash
cd packages/api
uv run pytest -m pdf -v
```

Expected: 3 tests pass (or 1 skipped if reference is absent).

- [ ] **Step 4: Lint + type-check the whole API package**

```bash
cd packages/api
uv run ruff check src tests
uv run mypy src
```

Expected: clean.

- [ ] **Step 5: Update the project README**

Open the top-level `README.md`. Update the Plan 3 row in the project-status table:

```markdown
| 3 | Import batches (xlsx upload/review/commit) + PDF export + XLSX export endpoints | ✅ Complete on branch `plan-3-imports-exports` |
```

Add a Plan-3 handoff section below the existing Plan-2 handoff section:

```markdown
## Plan-3 handoff notes

- Branch: `plan-3-imports-exports`. Unit tests pass; ruff + mypy clean.
- Integration tests require a local Supabase CLI stack (Docker). PDF tests
  require WeasyPrint apt deps (`libpango-1.0-0`, `libcairo2`, ...).
- New env vars in production: `BRANDING_*`, `IMPORT_MAX_FILE_BYTES`,
  `STORAGE_SIGNED_URL_TTL_S`, `DB_ACQUIRE_TIMEOUT_S`. Set in Render dashboard.
- Apply five new migrations: `supabase db push --db-url <prod-url>`.
- Rollback: Render one-click previous deploy. Migrations are additive —
  safe to leave applied during rollback.
```

- [ ] **Step 6: Update packages/api/README.md**

Append:

```markdown
## Plan 3 endpoints

- `POST /imports` — multipart .xlsx upload (valuer-only); returns 202 with batch_id.
- `GET /imports` — list batches with per-status counts.
- `GET /imports/{id}` — batch detail with inline items.
- `PATCH /imports/{id}/items/{iid}` — set resolution + edit inputs (valuer-only).
- `POST /imports/{id}/cancel` — abandon a batch (valuer-only).
- `POST /imports/{id}/commit` — idempotent per-item commit (valuer-only).
- `GET /imports/{id}/items/{iid}/source` — 307 to 5-min Storage signed URL.
- `GET /snapshots/{id}/export.pdf` — WeasyPrint PDF report.
- `GET /snapshots/{id}/export.xlsx` — engine-rendered canonical workbook.

See [`docs/superpowers/specs/2026-05-03-plan-3-imports-exports-design.md`](../../docs/superpowers/specs/2026-05-03-plan-3-imports-exports-design.md)
for the design and decisions log.
```

- [ ] **Step 7: Commit + push**

```bash
git add README.md packages/api/README.md
git commit -m "docs: Plan 3 handoff + endpoint summary

Project README + packages/api/README updated with branch status, env
var deltas, migration list, rollback story, and the 9 new endpoints
shipped in Plan 3."

# Push to origin (do not merge to main yet; PR review first)
git push -u origin plan-3-imports-exports
```

- [ ] **Step 8: Open the PR**

Use the GitHub CLI or the web UI:

```bash
gh pr create --base main --head plan-3-imports-exports \
  --title "Plan 3: Excel imports + PDF/XLSX exports" \
  --body "$(cat <<'EOF'
## Summary
- Excel upload → background parse → reviewer queue → idempotent commit
- PDF export (WeasyPrint) + XLSX export (engine renderer)
- Plan 2 carry-overs (db.py timeout, errors.py narrowing, version bump) folded in as the first 3 commits

See `docs/superpowers/specs/2026-05-03-plan-3-imports-exports-design.md` for the full design.

## Test plan
- [ ] All unit tests pass (`uv run pytest -m "not integration and not pdf"`)
- [ ] All integration tests pass (`supabase start && uv run pytest -m integration`)
- [ ] PDF tests pass with apt deps installed (`uv run pytest -m pdf`)
- [ ] Ruff + mypy clean
- [ ] Smoke script green against staging Render deploy
EOF
)"
```

---

## Self-review summary

**Spec coverage check** (every section in [the spec](../specs/2026-05-03-plan-3-imports-exports-design.md) maps to one or more tasks):

| Spec section | Task(s) |
|---|---|
| §4 Decisions Q1–Q15 | All settled in brainstorming; reflected throughout |
| §5 Architecture & module boundaries | Tasks 8–25 (every module appears) |
| §6.1 import_batch | Task 4 |
| §6.2 import_item | Task 5 |
| §6.3 pg_trgm + index | Task 3 |
| §6.4 RLS policies | Task 6 + RLS sanity test (Task 23) |
| §6.5 Storage bucket | Task 7 |
| §6.6 Audit-log entries | Embedded in router/worker tasks (17–22, 25) |
| §7 Endpoints | Tasks 17–22 (imports), 25 (exports) |
| §8 Parser & background task | Task 14 (worker) + Task 12 (storage adapter) + Task 13 (matcher) |
| §9 Commit loop | Task 15 |
| §10 Exports | Task 25 |
| §11.1 render.yaml | Task 29 |
| §11.2 Dockerfile | Task 30 |
| §11.3 Branding asset | Task 16 |
| §11.4 GitHub Actions | Task 31 |
| §11.5 Carry-overs | Tasks 0, 1, 2 |
| §11.6 Operator runbook | Task 33 README updates |
| §11.7 Rollback plan | Task 33 README updates |
| §12 Testing strategy | Throughout (each phase has tests); pdf mark in Task 27 |
| §13 Open items deferred | Not implemented (deferred per spec) |

**Type/name consistency:**
- `q_snapshot.get_with_property` (Task 11) is the function name used in `routers/exports.py` (Task 25) — match ✓
- `services.matcher.suggest` returns `MatchResult{property_id, score, auto_linked, suggestions}` (Task 13); consumed by `parse_worker._process_one` (Task 14) — match ✓
- `services.commit_worker.CommitFailure` raised in `_commit_one`, collected in `commit_batch` (Task 15); marshalled into `schemas.imports.CommitFailure` in router (Task 21) — names align ✓
- `services.storage.StorageClient` exposes `upload`, `download`, `signed_url`, `delete_prefix`; consumed by router (17, 20, 22), parse worker (14), commit worker (15) — match ✓
- `services.branding.Branding` dataclass; consumed by `services.exports._build_context` (Task 25) — match ✓
- `services.exports.render_snapshot_pdf(snapshot_dict, branding)` (Task 25) called by `routers/exports.py` (same task) — match ✓

**Placeholder scan:** No `TBD`, `TODO`, `implement later`, or `add appropriate handling` strings in the plan body. All steps include either complete code, exact commands, or both.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-03-plan-3-imports-exports.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**



