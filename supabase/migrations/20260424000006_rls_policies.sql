-- 20260424000006_rls_policies.sql
-- RLS policies. The API connects as service-role which bypasses these,
-- so they primarily exist for forward-compat if any client ever connects
-- with a user JWT directly.

-- Helper: is_valuer() reads role from app_user for auth.uid().
create or replace function public.is_valuer() returns boolean
language sql stable as $$
    select exists (
        select 1 from public.app_user
        where id = auth.uid() and role = 'valuer'
    );
$$;

-- app_user: user can read their own row only
create policy "app_user_self_select" on public.app_user
    for select to authenticated
    using (id = auth.uid());

-- entity
create policy "entity_select_all_auth" on public.entity
    for select to authenticated using (true);

create policy "entity_insert_valuer" on public.entity
    for insert to authenticated with check (public.is_valuer());

create policy "entity_update_valuer" on public.entity
    for update to authenticated using (public.is_valuer());

-- property
create policy "property_select_all_auth" on public.property
    for select to authenticated using (true);

create policy "property_insert_valuer" on public.property
    for insert to authenticated with check (public.is_valuer());

create policy "property_update_valuer" on public.property
    for update to authenticated using (public.is_valuer());

-- valuation_snapshot: select for all auth; insert for valuer; never update/delete
create policy "snapshot_select_all_auth" on public.valuation_snapshot
    for select to authenticated using (true);

create policy "snapshot_insert_valuer" on public.valuation_snapshot
    for insert to authenticated with check (public.is_valuer());

-- audit_log: select for authenticated; writes only via service_role
create policy "audit_select_all_auth" on public.audit_log
    for select to authenticated using (true);
