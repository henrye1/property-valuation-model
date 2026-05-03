-- Private bucket for raw uploaded workbooks. Reviewer downloads happen via
-- 5-minute signed URLs minted by services/storage.py; the browser must never
-- read this bucket directly.
insert into storage.buckets (id, name, public)
values ('imports', 'imports', false)
on conflict (id) do nothing;

-- No storage.objects policies for the 'authenticated' role are created;
-- only the API's service-role key (which bypasses RLS) reads/writes this bucket.
