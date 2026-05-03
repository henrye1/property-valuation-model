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
