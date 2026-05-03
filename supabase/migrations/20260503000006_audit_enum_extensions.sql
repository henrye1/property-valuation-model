-- Extend audit_log enums for Plan 3 (Excel imports + commit_worker).
--
-- New action values:
--   - 'cancel'  : reviewer aborts an import_batch
--   - 'commit'  : reviewer triggers POST /imports/{id}/commit
--
-- New target_table values:
--   - 'import_batch'
--   - 'import_item'
--
-- alter type ... add value is additive only (cannot remove enum values
-- without recreating the type). Safe to leave applied during rollback.

alter type public.audit_action add value if not exists 'cancel';
alter type public.audit_action add value if not exists 'commit';

alter type public.audit_target_table add value if not exists 'import_batch';
alter type public.audit_target_table add value if not exists 'import_item';
