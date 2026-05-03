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
