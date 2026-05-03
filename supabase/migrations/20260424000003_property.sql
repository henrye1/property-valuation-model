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
