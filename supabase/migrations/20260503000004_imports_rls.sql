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
