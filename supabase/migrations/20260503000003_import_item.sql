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
