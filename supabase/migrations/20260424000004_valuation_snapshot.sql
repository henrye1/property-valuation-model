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
