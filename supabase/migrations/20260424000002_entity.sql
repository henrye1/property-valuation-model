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
