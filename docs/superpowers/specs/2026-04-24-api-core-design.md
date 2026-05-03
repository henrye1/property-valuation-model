# API Core — Design (Plan 2)

**Date:** 2026-04-24
**Status:** Approved (brainstorming)
**Author:** Henry (<henry@anchorpointrisk.co.za>)
**Supersedes / refines:** `docs/superpowers/specs/2026-04-23-property-valuations-model-design.md` §4, §5, §7, §11 (scoped to the API core deliverable)

## 1. Purpose

Ship `packages/api/` — a FastAPI service that exposes the CRUD surface for entities, properties, valuation snapshots, portfolio summaries, audit log, and user info, backed by Supabase Postgres and secured by Supabase-issued JWTs.

This is **Plan 2** in a three-plan split of spec §7:

- Plan 2 (this spec) — API core: auth, entities, properties, snapshots, `/calculate` preview, portfolio, audit, users, CI, Render deploy artifacts.
- Plan 3 (deferred) — import batches (Excel upload/review/commit) + PDF export + XLSX export endpoints.
- Plan 4 (deferred) — React web UI.

Plan 2 is independently deployable: once merged, a valuer can drive the entire CRUD surface via `curl` or Postman. Plan 3 layers on top without changing Plan 2 endpoints.

## 2. Goals

- A service that verifies Supabase JWTs, auto-provisions `app_user` rows, and enforces the two-role model (valuer / viewer).
- Hand-written SQL migrations in `supabase/migrations/` covering `app_user`, `entity`, `property`, `valuation_snapshot`, `audit_log`, and RLS policies.
- All endpoints from §7.2 except imports and exports (those are Plan 3).
- Audit-log row written in the same transaction as every mutation.
- Two-layer test suite: fast unit tests (no DB) + integration tests against the Supabase CLI local stack.
- GitHub Actions CI that lints, type-checks, runs unit tests always, and integration tests via the Supabase CLI action.
- Render deploy artifacts (`render.yaml`, `Dockerfile`, env-var docs, `/healthz`, smoke-test script) — no agent-driven deploy.

## 3. Non-goals (Plan 2)

- Import batches and the review queue.
- PDF or XLSX export endpoints.
- WeasyPrint system libs in the deploy config.
- Web UI of any kind.
- pgTAP SQL tests.
- Optimistic concurrency (`If-Match`).
- Filter query params on `/portfolio/*`.
- In-app endpoints for changing a user's role — role bumps happen via the Supabase dashboard SQL editor.
- Real-time subscriptions / WebSockets.
- Multi-tenant isolation.

## 4. Architecture

```text
property-valuations-model/
├── packages/
│   ├── valuation_engine/        # Plan 1, shipped
│   └── api/                     # NEW (this plan)
│       ├── pyproject.toml
│       ├── Dockerfile
│       ├── README.md
│       ├── render.yaml
│       ├── src/api/
│       │   ├── __init__.py
│       │   ├── _version.py
│       │   ├── main.py              # FastAPI app factory
│       │   ├── config.py            # pydantic-settings
│       │   ├── db.py                # asyncpg pool + get_db dependency
│       │   ├── auth.py              # JWT verify + current_user dep + role guard
│       │   ├── audit.py             # audit(tx, ...) helper
│       │   ├── errors.py            # exception handlers + envelope
│       │   ├── schemas/             # Pydantic request/response models
│       │   │   ├── __init__.py
│       │   │   ├── common.py
│       │   │   ├── entity.py
│       │   │   ├── property.py
│       │   │   ├── snapshot.py
│       │   │   ├── portfolio.py
│       │   │   ├── user.py
│       │   │   └── audit.py
│       │   ├── queries/             # async query functions (one file per table)
│       │   │   ├── __init__.py
│       │   │   ├── app_user.py
│       │   │   ├── entity.py
│       │   │   ├── property.py
│       │   │   ├── snapshot.py
│       │   │   ├── audit.py
│       │   │   └── portfolio.py
│       │   └── routers/
│       │       ├── __init__.py
│       │       ├── health.py
│       │       ├── me.py
│       │       ├── entities.py
│       │       ├── properties.py
│       │       ├── snapshots.py
│       │       ├── calculate.py
│       │       ├── portfolio.py
│       │       ├── users.py
│       │       └── audit.py
│       ├── tests/
│       │   ├── conftest.py
│       │   ├── unit/                # no DB
│       │   │   ├── test_auth.py
│       │   │   ├── test_errors.py
│       │   │   ├── test_calculate_router.py
│       │   │   └── test_schemas.py
│       │   └── integration/         # @pytest.mark.integration, live Supabase
│       │       ├── conftest.py
│       │       ├── test_health.py
│       │       ├── test_me.py
│       │       ├── test_entities.py
│       │       ├── test_properties.py
│       │       ├── test_snapshots.py
│       │       ├── test_portfolio.py
│       │       ├── test_audit.py
│       │       └── test_users.py
│       └── scripts/
│           └── smoke.sh             # post-deploy smoke test
├── supabase/
│   ├── config.toml                  # Supabase CLI project config
│   └── migrations/
│       ├── 20260424000001_app_user.sql
│       ├── 20260424000002_entity.sql
│       ├── 20260424000003_property.sql
│       ├── 20260424000004_valuation_snapshot.sql
│       ├── 20260424000005_audit_log.sql
│       └── 20260424000006_rls_policies.sql
└── .github/workflows/api.yml        # NEW (this plan)
```

**Boundaries.**

- `schemas/` defines request/response shapes (Pydantic v2). No DB knowledge.
- `queries/` owns SQL. One file per table, async functions taking an `asyncpg.Connection` or transaction.
- `routers/` owns the HTTP surface. Depends on `schemas/` and `queries/`. Never writes raw SQL.
- `auth.py` is the only place JWTs are verified. `audit.py` is the only place audit rows are written.
- `valuation_engine` is imported only in `routers/calculate.py` and `routers/snapshots.py`; the rest of the API treats inputs/results as JSONB blobs.

## 5. Data access

### 5.1 Driver & pool

- `asyncpg` with a single application-wide pool created in FastAPI's `lifespan` handler.
- `DATABASE_URL` env var (service-role DSN, server-only) drives the pool.
- Per-request dependency `async def get_db() -> asyncpg.Connection` checks out a connection from the pool for the request's duration.
- Mutations wrap work in `async with conn.transaction()`; audit rows are written inside the same transaction.

### 5.2 Query layout

Each `queries/<table>.py` exposes narrow async functions:

```python
# queries/entity.py
async def list_entities(conn, *, include_deleted: bool = False) -> list[Record]: ...
async def get_entity(conn, entity_id: UUID) -> Record | None: ...
async def insert_entity(conn, **cols) -> Record: ...
async def update_entity(conn, entity_id: UUID, **patch) -> Record: ...
async def soft_delete_entity(conn, entity_id: UUID) -> Record: ...
async def count_live_children(conn, entity_id: UUID) -> int: ...
```

Dynamic UPDATE statements for PATCH build a `SET col = $n` list from non-None patch fields, with parameter placeholders — never string-interpolated.

### 5.3 Migrations

- Hand-written SQL in `supabase/migrations/`, timestamped-prefix naming (`YYYYMMDDNNNNNN_<name>.sql`).
- Applied via `supabase db reset` in tests and `supabase db push` against the hosted dev project.
- Columns: `id UUID DEFAULT gen_random_uuid()`, timestamps as `timestamptz DEFAULT now()`.
- Soft-delete columns: `deleted_at timestamptz NULL`.
- `valuation_snapshot.inputs_json` / `result_json` are `jsonb NOT NULL`. `market_value`, `cap_rate`, `engine_version`, `source` are denormalised columns on the row.
- Indexes: `(entity_id)` on `property`, `(property_id, valuation_date DESC)` on `valuation_snapshot`, `(created_at DESC)` on `audit_log`, partial indexes filtering `deleted_at IS NULL` where queries filter that way.

### 5.4 RLS

- Every table has `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`.
- The API connects as service-role, which bypasses RLS — policies exist for future direct-Supabase-client access (web client in Plan 4 or external tools).
- Policies encoded in `20260424000006_rls_policies.sql`:
  - `authenticated` role: `SELECT` on all tables.
  - `authenticated` + valuer check (`app_user.role = 'valuer'` for the current `auth.uid()`): `INSERT`, `UPDATE` on `entity`, `property`; `INSERT` on `valuation_snapshot`, `audit_log`.
- Integration tests verify the policies are at least syntactically valid (migrations apply) and that the service-role path works; full RLS enforcement is covered later when the web client goes direct (if ever).

## 6. Auth & user provisioning

### 6.1 JWT verification

```python
# auth.py
def verify_jwt(token: str) -> JWTClaims:
    return jwt.decode(
        token,
        key=settings.SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        audience="authenticated",
        options={"require": ["sub", "exp"]},
    )
```

Errors → 401 with `{"error": {"code": "unauthorized", ...}}`.

### 6.2 Current-user dependency

```python
async def current_user(
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
) -> AppUser:
    token = _extract_bearer(request)
    claims = verify_jwt(token)
    user = await queries.app_user.upsert_from_claims(
        conn,
        auth_uid=UUID(claims["sub"]),
        email=claims.get("email"),
        default_role="viewer",
    )
    request.state.user = user
    return user
```

`upsert_from_claims` uses `INSERT ... ON CONFLICT (id) DO UPDATE SET last_seen_at = now() RETURNING *`. First hit creates the row with `role='viewer'`.

### 6.3 Role guard

```python
def require_valuer(user: AppUser = Depends(current_user)) -> AppUser:
    if user.role != "valuer":
        raise HTTPException(403, {"error": {"code": "forbidden", ...}})
    return user
```

Every non-GET router depends on `require_valuer`. GET routers depend on `current_user` only.

### 6.4 Role changes

Done manually via Supabase dashboard SQL:

```sql
UPDATE app_user SET role = 'valuer' WHERE email = 'alice@example.com';
```

No in-app endpoint for this in Plan 2. Per the spec, audit rows are written in application code, so manual DB changes do not produce audit-log entries; Supabase's own dashboard activity log is the fallback trail. Acceptable trade-off given how rare role changes are in a two-role single-tenant system.

## 7. Endpoints

### 7.1 Inventory

| Method | Path | Role | Notes |
|---|---|---|---|
| `GET` | `/healthz` | none | No auth; liveness only |
| `GET` | `/me` | any | Returns `AppUser` |
| `GET` | `/entities` | any | `?include_deleted=false` |
| `POST` | `/entities` | valuer | |
| `GET` | `/entities/{id}` | any | 404 if soft-deleted and not `?include_deleted=true` |
| `PATCH` | `/entities/{id}` | valuer | Partial; empty body → 422 |
| `DELETE` | `/entities/{id}` | valuer | Soft; 409 if live children |
| `GET` | `/properties` | any | `?entity_id=`, `?property_type=` |
| `POST` | `/properties` | valuer | |
| `GET` | `/properties/{id}` | any | |
| `PATCH` | `/properties/{id}` | valuer | Partial |
| `DELETE` | `/properties/{id}` | valuer | Soft; 409 if live snapshots |
| `GET` | `/properties/{id}/snapshots` | any | Ordered by `valuation_date DESC` |
| `POST` | `/properties/{id}/snapshots` | valuer | Body = `ValuationInput`; runs engine, persists |
| `GET` | `/snapshots/{id}` | any | |
| `POST` | `/calculate` | valuer | Preview only; no DB write |
| `GET` | `/portfolio/summary` | any | `?limit=` for top N properties |
| `GET` | `/portfolio/timeseries` | any | `?bucket=year` (only `year` supported in v1) |
| `GET` | `/users` | any | Lists `app_user` rows |
| `GET` | `/audit` | any | `?limit=&offset=&target_table=&actor_id=` |

Deferred to Plan 3: `POST /imports`, `GET /imports/{id}`, `PATCH /imports/{id}/items/{id}`, `POST /imports/{id}/commit`, `GET /snapshots/{id}/export.pdf`, `GET /snapshots/{id}/export.xlsx`.

### 7.2 Request/response shapes

Defined in `schemas/`. Request and response Pydantic models are distinct (avoids leaking internals like `deleted_at` inadvertently on create).

`EntityCreate`: `{name: str, registration_number: str | None, notes: str | None}`.
`EntityUpdate`: `{name?: str, registration_number?: str | None, notes?: str | None}`; all fields optional; empty body → 422.
`Entity`: full row including timestamps, `deleted_at`.

`PropertyCreate`: `{entity_id, name, address, property_type, notes}`.
`PropertyUpdate`: all fields optional.
`Property`: full row.

`Snapshot`:

```python
{
    "id": UUID, "property_id": UUID, "valuation_date": date,
    "created_by": UUID, "created_at": datetime, "status": "active"|"superseded",
    "inputs_json": dict, "result_json": dict,
    "market_value": Decimal, "cap_rate": Decimal,
    "engine_version": str, "source": "manual"|"excel_import",
    "source_file": str | None,
}
```

Snapshots are append-only. On every new snapshot for a property, the API first marks prior active snapshots as `superseded`; only the latest is `active`. See §7.3 for the flow.

`AppUser`, `AuditEntry` as per spec §5 with camelCase→snake_case mapping handled by Pydantic `model_config` aliases where needed (not expected to diverge).

`PortfolioSummary`:

```python
{
    "total_market_value": Decimal,
    "property_count": int,
    "entity_count": int,
    "last_snapshot_date": date | None,
    "value_by_type": [{"type": str, "value": Decimal, "count": int}],
    "value_by_entity": [{"entity_id": UUID, "name": str, "value": Decimal, "count": int}],
    "top_properties": [{"property_id": UUID, "name": str, "value": Decimal}]
}
```

`PortfolioTimeseries`: `[{"bucket_date": date, "total_market_value": Decimal, "property_count": int}]`.

### 7.3 Snapshot creation flow

`POST /properties/{id}/snapshots`:

1. Verify property exists and is not soft-deleted; 404/410 otherwise.
2. Validate body as `ValuationInput` (via the engine's own Pydantic model).
3. Call `calculate(inputs)` → `result`.
4. Start transaction:
   - `UPDATE valuation_snapshot SET status='superseded' WHERE property_id=$1 AND status='active'`
   - `INSERT INTO valuation_snapshot (...) VALUES (...) RETURNING *`
   - `audit(tx, actor, "create", "valuation_snapshot", snapshot.id, before=null, after=row)`
5. Commit; return the inserted row.

Denormalised `market_value` and `cap_rate` columns mirror `result_json.market_value` and `inputs_json.cap_rate` at write time. `engine_version` = `valuation_engine.__version__`; `source = "manual"`; `source_file = null`.

### 7.4 Error envelope

```json
{ "error": { "code": "snake_case", "message": "...", "details": { "..." } } }
```

Mapped by `errors.py`:

- `ValueError` from engine → 422, `code="engine_validation_error"`.
- Pydantic `ValidationError` → 422, `code="invalid_input"`, `details.errors = err.errors()`.
- `jwt.InvalidTokenError` → 401, `code="unauthorized"`.
- Missing Authorization header → 401, `code="missing_token"`.
- Role check fail → 403, `code="forbidden"`.
- Not found → 404, `code="not_found"`.
- Soft-delete conflict → 409, `code="has_live_children"`, `details.blocking_count=N`.
- Unexpected → 500, `code="internal_error"`.

## 8. Audit log

### 8.1 Helper

```python
# audit.py
async def audit(
    tx: asyncpg.Connection,
    actor: AppUser,
    *,
    action: Literal["create", "update", "soft_delete"],
    target_table: Literal["entity", "property", "valuation_snapshot", "app_user"],
    target_id: UUID,
    before: dict | None,
    after: dict | None,
) -> None:
    await tx.execute(
        """
        INSERT INTO audit_log (
            actor_id, actor_email, action, target_table, target_id,
            before_json, after_json, created_at
        ) VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb, now())
        """,
        actor.id, actor.email, action, target_table, target_id,
        json.dumps(before, default=_json_default) if before else None,
        json.dumps(after, default=_json_default) if after else None,
    )
```

`_json_default` stringifies `Decimal` and `date`/`datetime`/`UUID` to ISO strings, matching the engine's wire format.

### 8.2 Coverage

| Mutation | action | target_table |
|---|---|---|
| `POST /entities` | create | entity |
| `PATCH /entities/{id}` | update | entity |
| `DELETE /entities/{id}` | soft_delete | entity |
| `POST /properties` | create | property |
| `PATCH /properties/{id}` | update | property |
| `DELETE /properties/{id}` | soft_delete | property |
| `POST /properties/{id}/snapshots` | create | valuation_snapshot |

`app_user` auto-provisioning on first request is *not* audited (internal bookkeeping, not a user action).

### 8.3 `GET /audit`

Paginated via `?limit=` (default 50, max 200) and `?offset=`. Filters: `?target_table=`, `?actor_id=`. Ordered by `created_at DESC`.

## 9. Configuration

`config.py` via `pydantic-settings`:

```python
class Settings(BaseSettings):
    DATABASE_URL: str                         # asyncpg DSN, service-role
    SUPABASE_URL: str
    SUPABASE_JWT_SECRET: str
    ALLOWED_ORIGINS: str = ""                 # comma-separated
    LOG_LEVEL: str = "INFO"
    ENV: Literal["dev", "ci", "prod"] = "dev"
```

Env vars only — no `.env` in repo. `.env.example` committed for local dev (with dummy values that match the Supabase CLI local defaults).

## 10. Logging & observability

- Structured JSON logs to stdout. One line per request at `INFO`: `{"ts", "level", "method", "path", "status", "duration_ms", "user_id"}`.
- 5xx logs include `traceback`.
- `GET /healthz` returns `{"status": "ok", "engine_version": "0.1.0", "api_version": "0.1.0"}`.
- Sentry wiring is a TODO-hook but not required for Plan 2 (env var recognised but no SDK installed).

## 11. Testing

### 11.1 Layer split

- `tests/unit/` — no Docker, no DB. Tests import `api.main.create_app(settings=TestSettings)` with a mocked `asyncpg.Pool`. Unit tests cover:
  - JWT verification (happy + expired + wrong audience).
  - Error envelope mapping.
  - `/calculate` happy-path (engine integration, no DB).
  - Pydantic schema validation (create vs. update semantics).
  - Audit payload shape (pure function test).

- `tests/integration/` — `@pytest.mark.integration`. Require a running Supabase CLI stack (`supabase start`). Conftest:
  - Creates a fresh DB via `supabase db reset` at session scope.
  - Truncates all tables between tests (`TRUNCATE ... CASCADE`).
  - Fixture `make_token(sub, email, role="valuer")` mints an HS256 JWT against `SUPABASE_JWT_SECRET`, inserts an `app_user` row with the desired role, and returns `Authorization: Bearer <token>`.
  - Uses `httpx.AsyncClient` against the FastAPI app.

Integration coverage hits every endpoint at least once: happy path, role-gated 403, soft-delete 409, audit-row existence, portfolio math on a small fixture of 2 entities + 4 properties + 8 snapshots.

### 11.2 Running tests

- Unit only: `uv run pytest -m "not integration"` — no Docker required.
- All: `supabase start && uv run pytest`.
- CI runs both layers. Unit job is ~10s; integration job is ~1–2 min because of the stack startup.

## 12. CI

`.github/workflows/api.yml`:

```yaml
name: api
on:
  push:
    paths: ['packages/api/**', 'supabase/**', '.github/workflows/api.yml']
  pull_request:
jobs:
  lint-type:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
        working-directory: packages/api
      - run: uv run ruff check .
        working-directory: packages/api
      - run: uv run mypy src
        working-directory: packages/api
  unit:
    needs: lint-type
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
        working-directory: packages/api
      - run: uv run pytest -m "not integration" -v
        working-directory: packages/api
  integration:
    needs: unit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: supabase/setup-cli@v1
      - run: supabase start
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
        working-directory: packages/api
      - run: uv run pytest -m integration -v
        working-directory: packages/api
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:54322/postgres
          SUPABASE_URL: http://localhost:54321
          SUPABASE_JWT_SECRET: super-secret-jwt-token-with-at-least-32-characters-long
```

(Values above are Supabase CLI local defaults; the actual secret string comes from `supabase status` output at CI time — CI pins the known default from `supabase/config.toml`.)

## 13. Deploy artifacts (no deploy)

### 13.1 `Dockerfile`

Multi-stage: `python:3.11-slim` base, `uv` for install, copies `packages/valuation_engine` so the editable path-install works in the image, runs as non-root, entry `uvicorn api.main:app --host 0.0.0.0 --port $PORT`.

### 13.2 `render.yaml`

Declares one Web Service pointing at the Dockerfile, with env vars templated and `healthCheckPath: /healthz`. User sets real values in the Render dashboard (`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `ALLOWED_ORIGINS`).

### 13.3 `scripts/smoke.sh`

Takes `BASE_URL` and a valid Supabase user JWT, hits `/healthz`, `/me`, `/entities`, and asserts JSON shapes. Run manually post-deploy.

### 13.4 `packages/api/README.md`

- Prerequisites (Docker, `uv`, Supabase CLI).
- Local dev: `supabase start` → `.env` → `uv run uvicorn api.main:app --reload`.
- Running tests (unit vs. integration).
- Env var reference.
- Release-vs-dev engine dependency note (uv sources override for local path; CI/release uses the tagged git ref).

## 14. Engine dependency

`packages/api/pyproject.toml`:

```toml
[project]
dependencies = [
    "fastapi>=0.110,<1",
    "uvicorn[standard]>=0.29,<1",
    "asyncpg>=0.29,<1",
    "pydantic>=2.6,<3",
    "pydantic-settings>=2,<3",
    "pyjwt>=2.8,<3",
    "httpx>=0.27,<1",
    "valuation-engine>=0.1,<0.2",
]

[tool.uv.sources]
valuation-engine = { path = "../valuation_engine", editable = true }
```

Release builds (Render, CI release job in a later plan) run `uv sync --no-sources` or invoke pip with the tagged git ref — the version constraint in `[project.dependencies]` is the single source of truth.

## 15. Tech-stack summary

- Python 3.11+, FastAPI 0.110+, asyncpg, Pydantic v2, pydantic-settings.
- `pyjwt[crypto]` for HS256 JWT verification.
- `uv` as package manager and CLI runner.
- `hatchling` as build backend (matches the engine).
- `pytest`, `pytest-asyncio`, `httpx` for tests.
- `ruff`, `mypy` (strict) for lint/type-check.
- Supabase CLI for local Postgres + auth + migrations.
- GitHub Actions for CI.

## 16. Decisions log

| # | Decision |
|---|---|
| Q1 | Split §7 into Plan 2 (core) + Plan 3 (imports & exports). |
| Q2 | Local dev and tests use Supabase CLI Docker stack. |
| Q3 | Two test layers: fast unit (no DB) + integration (`@pytest.mark.integration`). |
| Q4 | DB access = raw SQL via asyncpg with per-table query functions. |
| Q5 | JWT verify = HS256 using `SUPABASE_JWT_SECRET`. |
| Q6 | Auth middleware auto-provisions `app_user` with default `viewer` role on first request. |
| Q7 | Audit log: every mutation (entity/property/snapshot/app_user role change) written in same tx; reads never audited. |
| Q8 | Engine dep: `[project.dependencies]` pin + `[tool.uv.sources]` override for local editable path. |
| Q9 | Plan 2 produces Render deploy artifacts; actual deploy is manual and out-of-plan. |
| Q10 | `POST /calculate` is valuer-only (viewer 403 rule has no exceptions). |
| Q11 | `/portfolio/summary` returns KPIs + value_by_type + value_by_entity + top_properties (default N=10); `/portfolio/timeseries?bucket=year`. No filter params in v1. |
| Q12 | `PATCH` = partial update, `extra='forbid'`, empty body → 422. No optimistic concurrency in v1. |
| Q13 | Soft-delete with 409 on live children (matches spec §5). No cascade. Snapshots have no DELETE. |
| Q14 | Hand-written SQL migrations in `supabase/migrations/`; 6 files for Plan 2. Import tables deferred. |
