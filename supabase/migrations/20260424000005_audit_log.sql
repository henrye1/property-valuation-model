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
