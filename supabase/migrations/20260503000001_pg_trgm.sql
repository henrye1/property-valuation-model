-- Enable trigram similarity for fuzzy matching of property names during
-- Excel imports (services/matcher.py).
create extension if not exists pg_trgm;

-- Partial GIN index: only over live (non-soft-deleted) properties, since the
-- matcher never suggests soft-deleted rows.
create index if not exists property_name_trgm_idx
  on public.property using gin (name gin_trgm_ops)
  where deleted_at is null;
