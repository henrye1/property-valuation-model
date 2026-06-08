# Plan 4 — React Web UI — Design

**Date:** 2026-06-08
**Status:** Approved (brainstorming)
**Author:** Henry (henry@anchorpointrisk.co.za)
**Branch (planned):** `plan-4-web-ui` (off `main` after Phase 0 merges Plan 3)
**Top-level spec reference:** [`docs/superpowers/specs/2026-04-23-property-valuations-model-design.md`](./2026-04-23-property-valuations-model-design.md) §8
**Prereq:** [`docs/superpowers/runbooks/2026-06-08-phase-0-backend-go-live.md`](../runbooks/2026-06-08-phase-0-backend-go-live.md) (backend live + OAuth configured)

## 1. Purpose

Build the user-facing web application — the last package in the monorepo (`packages/web/`). It is the only thing valuers and viewers ever touch: log in, browse the portfolio, create and view valuations, export reports, and run Excel batch imports. All data reads/writes go through the existing FastAPI service; the browser uses Supabase JS **only** for OAuth/session.

The backend (Plans 1–3) is complete and, after Phase 0, live. This plan adds **no backend code** — it consumes the finished API contract in §4.

## 2. Goals

- Clean, functional, professional UI on shadcn/ui + Tailwind (not a bespoke design system).
- Cover every route in top-level design §8.2 against the real API.
- Two roles enforced in the UI: `valuer` (full CRUD) and `viewer` (read-only; create/edit affordances hidden and gated).
- Live valuation editor with debounced `POST /calculate` preview and inline warnings.
- Import review queue mirroring the backend batch lifecycle.
- Deployed as a Render Static Site, wired to the live API.

## 3. Non-goals (this plan)

- Custom/branded visual design system, animations, marketing pages (functional baseline only).
- In-app user/role administration (role assignment stays in the Supabase dashboard; `/settings/users` is read-only).
- Inline entity/property creation *inside* the import commit flow (reviewer links to existing entities/properties created via the normal forms — matches the backend's Plan 3 non-goal).
- Offline support, PWA, mobile-first layouts (desktop-first; usable on tablet).
- Real-time subscriptions — import-batch status is polled, not socket-pushed.
- E2E test automation in CI beyond a typecheck + lint + unit smoke (Playwright deferred).

## 4. API contract consumed (live surface)

Confirmed from the merged backend. Base URL via `VITE_API_BASE_URL`. Every request carries `Authorization: Bearer <supabase access token>`.

```
GET    /me                                   -> AppUser (id, email, display_name, role)

GET    /entities                             -> Entity[]
POST   /entities                             (valuer) 201 -> Entity
GET    /entities/{id}                        -> Entity
PATCH  /entities/{id}                        (valuer) -> Entity
DELETE /entities/{id}                        (valuer) -> Entity   (soft; 4xx if children)

GET    /properties                           -> Property[]
POST   /properties                           (valuer) 201 -> Property
GET    /properties/{id}                      -> Property
PATCH  /properties/{id}                      (valuer) -> Property
DELETE /properties/{id}                      (valuer) -> Property (soft)

GET    /properties/{id}/snapshots            -> Snapshot[]
GET    /snapshots/{id}                        -> Snapshot
POST   /properties/{id}/snapshots            (valuer) 201 -> Snapshot   (body = ValuationInput)
POST   /calculate                            -> ValuationResult         (body = ValuationInput; no DB write)

POST   /imports                              (valuer) 202 -> ImportCreated {batch_id}   (multipart .xlsx)
GET    /imports                              -> ImportBatchList
GET    /imports/{batch_id}                   -> ImportBatch (with items)
PATCH  /imports/{batch_id}/items/{item_id}   (valuer) -> ImportItem
POST   /imports/{batch_id}/cancel            (valuer) -> {status}
POST   /imports/{batch_id}/commit            (valuer) -> CommitSummary
GET    /imports/{batch_id}/items/{item_id}/source   -> original uploaded file (signed)

GET    /snapshots/{id}/export.xlsx           -> application/xlsx (attachment)
GET    /snapshots/{id}/export.pdf            -> application/pdf  (attachment)

GET    /portfolio/summary                    -> PortfolioSummary (KPIs)
GET    /portfolio/timeseries                 -> PortfolioTimeseries

GET    /users                                -> AppUser[]
GET    /audit                                -> AuditPage
```

Error envelope (all non-2xx): `{"error": {"code": "...", "message": "...", "details": {...}}}`. 401 → force re-auth; 403 → "not permitted" toast (viewer hit a write); 404 → not-found page; 422 → field-level validation surfaced inline.

**Action for the plan:** before writing UI code, regenerate/confirm the exact JSON field names by hitting the live `/openapi.json`, so the zod schemas (§7) match byte-for-byte. The shapes in the top-level design §6.3 are the source of truth for `ValuationInput`/`ValuationResult`.

## 5. Stack

Vite + React 18 + TypeScript (strict) + Tailwind + shadcn/ui + TanStack Query v5 + React Router v6 + react-hook-form + zod + Recharts (charts) + `@supabase/supabase-js` (OAuth/session only). Vitest + Testing Library for unit tests. Package manager: `pnpm` (per top-level design §11.4).

## 6. Architecture & boundaries

```
packages/web/
├── src/
│   ├── lib/
│   │   ├── supabase.ts        # supabase-js client (OAuth/session only)
│   │   ├── api.ts             # fetch wrapper: base URL + bearer token + error-envelope unwrap
│   │   ├── queryClient.ts     # TanStack Query config (retry/staleTime)
│   │   └── auth.tsx           # AuthProvider: session, current AppUser (/me), role
│   ├── schemas/               # zod schemas mirroring Pydantic (one file per domain)
│   ├── hooks/                 # useEntities, useProperty, useSnapshot, useCalculate, useImports...
│   ├── components/
│   │   ├── ui/                # shadcn primitives (generated)
│   │   ├── layout/            # AppShell, Sidebar, TopBar, RoleGate
│   │   ├── valuation/         # TenantRow, ParkingRow, AssumptionsForm, ResultPanel, WarningChip
│   │   └── import/            # ImportItemTable, ImportItemPanel, DiffBadge, UploadDropzone
│   ├── pages/                 # one component per route
│   ├── routes.tsx
│   └── main.tsx
├── index.html
├── vite.config.ts
├── tailwind.config.ts
└── package.json
```

**Boundaries (each unit testable in isolation):**
- `lib/api.ts` is the *only* place that knows the API base URL, attaches the token, and unwraps the error envelope. Hooks call it; components never `fetch`.
- `lib/auth.tsx` is the *only* place that touches supabase-js. The rest of the app reads `useAuth()` for `{ session, user, role, signIn, signOut }`.
- `schemas/` validates every API response at the boundary; types flow from `z.infer`, so there's one source of truth for shapes.
- `components/valuation/ResultPanel` is a pure render of a `ValuationResult` — no fetching; the editor page owns the debounced `/calculate` call and passes the result down.
- `RoleGate` wraps any write affordance; `viewer` never sees create/edit/delete buttons, and route guards block direct navigation to editor/new routes.

## 7. Data validation & types

zod schemas mirror the Pydantic models (top-level design §6.3): `TenantLine`, `ParkingLine`, `ValuationInput`, `ResolvedTenant`, `Warning`, `ValuationResult`, plus `Entity`, `Property`, `Snapshot`, `ImportBatch`, `ImportItem`, `AppUser`, `AuditEntry`, `PortfolioSummary`, `PortfolioTimeseries`. Decimals arrive as **strings** (engine emits Decimal-as-string) — schemas keep them as strings and format for display; the editor parses to number only at input-edit time and re-serializes as string on submit, to preserve precision.

## 8. Routes & pages (build order = slice order)

Slices map 1:1 to the roadmap phases. Each slice ends demoable.

**Slice 1 — Foundation.** Scaffold; `lib/*`; `AuthProvider`; `/login` (Google/Microsoft buttons via supabase-js); AppShell with sidebar + role-aware nav; `/me` wired; protected-route wrapper. *Exit: log in, land on an authenticated empty dashboard, sign out.*

**Slice 2 — Read-only core.**
- `/` Portfolio dashboard: KPI cards (total value, # properties, # entities, last snapshot date) from `/portfolio/summary`; value-by-type donut + value-by-entity bar + value-over-time line from `/portfolio/timeseries`; top-N properties table.
- `/entities`, `/entities/:id` (properties owned).
- `/properties` (filter/search), `/properties/:id` (latest snapshot + history list).
- `/properties/:id/valuations/:sid` Snapshot viewer: read-only inputs+result+warnings+engine version+author+timestamp; **Export PDF / Export XLSX** buttons (authenticated file download via `lib/api.ts` blob fetch). *Exit: a viewer browses the whole portfolio and exports a report.*

**Slice 3 — Write flows.**
- `/entities/new`, edit entity; `/properties/new`, edit property (react-hook-form + zod).
- `/properties/:id/valuations/new` Valuation editor: three sections (Tenants / Parking / Assumptions); right-rail `ResultPanel` driven by `POST /calculate` **debounced 300ms**; warnings render inline next to offending fields via `field_path`; "Save snapshot" → `POST /properties/:id/snapshots` → route to viewer. "New valuation from this" on the viewer pre-fills the editor. *Exit: a valuer creates a valuation end-to-end.*

**Slice 4 — Import review.**
- `/imports` batches list (status badges); `/imports/new` drag-drop `.xlsx` upload → `POST /imports` → redirect to review.
- `/imports/:id` review queue: poll `GET /imports/{id}` while `status=parsing`; table of items (parsed entity/property, sheet value, recomputed value, diff %, parse status, resolution); side panel (`ImportItemPanel`) to edit parsed inputs, accept/reject/edit-and-accept (`PATCH .../items/{id}`), link/create entity+property, download original (`/source`). "Commit batch" (`POST .../commit`) enabled only when no item is `pending`; surface `CommitSummary`; rows that fail to commit stay `pending`. Cancel batch supported. *Exit: a valuer runs an Excel batch import to committed snapshots.*

**Slice 5 — Audit, users, polish, deploy.**
- `/audit` read-only paged table (`GET /audit`); `/settings/users` read-only list + role (`GET /users`).
- Cross-cutting: viewer role-gating verified on every write path; consistent loading skeletons, empty states, error toasts, and a 404 page; `lib/api.ts` 401 handler triggers re-auth.
- Deploy: Render Static Site (`pnpm build` → `dist/`); set build-time `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`; add the deployed origin to the API's `ALLOWED_ORIGINS` and to Supabase redirect URLs. *Exit: shipped; full end-to-end pass against prod.*

## 9. Cross-cutting conventions

- **Loading:** route-level skeletons; TanStack Query `isPending` drives them. **Errors:** error envelope `message` shown in a toast; 422 details mapped to form fields by `field_path`. **Empty:** every list has an explicit empty state with the primary action (valuer) or a neutral message (viewer).
- **Auth lifecycle:** supabase-js persists the session; `lib/api.ts` reads the current access token per request; on 401 it clears session and routes to `/login`. Token refresh handled by supabase-js.
- **Money formatting:** ZAR, thousands separators, 2 dp; a single `formatZar(str)` helper consuming the Decimal-string.
- **Downloads:** PDF/XLSX fetched as authenticated blobs (bearer header), then `URL.createObjectURL` + anchor click — never a bare `<a href>` (which can't send the token).

## 10. Testing

- Vitest unit tests for: `lib/api.ts` (token attach, envelope unwrap, 401 path), zod schema round-trips against captured fixtures, escalation/result formatting helpers, `ResultPanel` render, `RoleGate` (viewer hides affordances), import diff-badge logic.
- Manual end-to-end verification per slice exit criterion against the live API (Approach A) — captured in the plan's verification steps.
- CI web job (top-level design §11.3): eslint + `tsc --noEmit` + Vitest. Playwright deferred (non-goal).

## 11. CI & deploy

- Add a `web` job to `.github/workflows/` (or a new `web.yml`): `pnpm install`, `pnpm lint`, `pnpm typecheck`, `pnpm test`.
- Render Static Site as in top-level design §11.1. Build-time env vars only (anon key is public-safe; service-role key is **never** in the web build).

## 12. Decisions log

| # | Decision |
|---|---|
| Q1 | Finish the whole project: Phase 0 backend go-live + Plan 4 web UI + final deploy. |
| Q2 | Approach A — backend-first/live, then build UI against the real API. |
| Q3 | Clean functional baseline (shadcn/ui + Tailwind), not a bespoke branded design. |
| Q4 | Prod Supabase exists with Plan 1/2 migrations; OAuth + Render API deploy handled in Phase 0. |
| Q5 | Plan then build, in slices, with review checkpoints. |
| Q6 | Five vertical slices, each independently demoable, in dependency order. |
| Q7 | Import-batch status polled (no realtime); user/role admin stays in Supabase dashboard. |
| Q8 | Playwright/E2E automation deferred; CI runs lint + typecheck + Vitest only. |
