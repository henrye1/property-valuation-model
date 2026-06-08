import { z } from 'zod'

// Mirrors api/schemas/imports.py
// Note: ImportItem field names differ substantially from the reference —
// confirmed against the real Pydantic model and router construction code.

export const ParseStatusSchema = z.enum(['ok', 'warning', 'error'])
export type ParseStatus = z.infer<typeof ParseStatusSchema>

// Real model: Resolution includes "committed" — reference omitted it
export const ResolutionSchema = z.enum(['pending', 'accepted', 'rejected', 'edited', 'committed'])
export type Resolution = z.infer<typeof ResolutionSchema>

export const BatchStatusSchema = z.enum(['parsing', 'review', 'committed', 'cancelled'])
export type BatchStatus = z.infer<typeof BatchStatusSchema>

// ImportItemWarning (also used for errors list)
export const ImportItemWarningSchema = z.object({
  code: z.string(),
  message: z.string(),
  field_path: z.string().nullable().optional(),
})
export type ImportItemWarning = z.infer<typeof ImportItemWarningSchema>

// ImportItemSuggestion (fuzzy-match result)
export const ImportItemSuggestionSchema = z.object({
  property_id: z.string(),
  property_name: z.string(),
  entity_id: z.string(),
  entity_name: z.string(),
  score: z.string(),
  auto_linked: z.boolean(),
})
export type ImportItemSuggestion = z.infer<typeof ImportItemSuggestionSchema>

// ImportItem: real field names differ from reference
// - has building_name (not in reference)
// - warnings/errors are lists (not warnings_json/errors_json)
// - parsed_inputs / computed_result / resolved_inputs (not *_json suffix)
// - has suggestion field
// - Decimals: spreadsheet_market_value, recomputed_market_value, diff_pct all Decimal|None → string|null
export const ImportItemSchema = z.object({
  id: z.string(),
  filename: z.string(),
  parse_status: ParseStatusSchema,
  building_name: z.string().nullable(),
  spreadsheet_market_value: z.string().nullable(),
  recomputed_market_value: z.string().nullable(),
  diff_pct: z.string().nullable(),
  warnings: z.array(ImportItemWarningSchema),
  errors: z.array(ImportItemWarningSchema),
  suggestion: ImportItemSuggestionSchema.nullable().optional(),
  resolution: ResolutionSchema,
  resolved_property_id: z.string().nullable(),
  parsed_inputs: z.record(z.string(), z.unknown()).nullable(),
  computed_result: z.record(z.string(), z.unknown()).nullable(),
  resolved_inputs: z.record(z.string(), z.unknown()).nullable(),
})
export type ImportItem = z.infer<typeof ImportItemSchema>

// Uploader actor reference shape
export const ActorRefSchema = z.object({
  id: z.string(),
  email: z.string().nullable().optional(),
})
export type ActorRef = z.infer<typeof ActorRefSchema>

// Resolution state counts embedded in list items
export const ImportBatchCountsSchema = z.object({
  pending: z.number().int(),
  accepted: z.number().int(),
  rejected: z.number().int(),
  edited: z.number().int(),
  committed: z.number().int(),
})
export type ImportBatchCounts = z.infer<typeof ImportBatchCountsSchema>

// ImportBatchListItem: list view — includes counts but not full items array
export const ImportBatchListItemSchema = z.object({
  id: z.string(),
  uploaded_by: ActorRefSchema,
  uploaded_at: z.string(),
  file_count: z.number().int(),
  status: BatchStatusSchema,
  counts: ImportBatchCountsSchema,
})
export type ImportBatchListItem = z.infer<typeof ImportBatchListItemSchema>

// ImportBatchList: GET /imports wrapper — {items, total}
export const ImportBatchListSchema = z.object({
  items: z.array(ImportBatchListItemSchema),
  total: z.number().int(),
})
export type ImportBatchList = z.infer<typeof ImportBatchListSchema>

// ImportBatch: GET /imports/{id} full detail — includes items array and notes
export const ImportBatchSchema = z.object({
  id: z.string(),
  uploaded_by: ActorRefSchema,
  uploaded_at: z.string(),
  file_count: z.number().int(),
  status: BatchStatusSchema,
  notes: z.string().nullable(),
  items: z.array(ImportItemSchema),
})
export type ImportBatch = z.infer<typeof ImportBatchSchema>

// ImportCreated: POST /imports response (202)
// Real model has file_count and status fields (reference only had batch_id)
export const ImportCreatedSchema = z.object({
  batch_id: z.string(),
  file_count: z.number().int(),
  status: z.literal('parsing'),
})
export type ImportCreated = z.infer<typeof ImportCreatedSchema>

// CommitFailure embedded in CommitSummary
export const CommitFailureSchema = z.object({
  item_id: z.string(),
  filename: z.string(),
  reason: z.string(),
  message: z.string(),
})
export type CommitFailure = z.infer<typeof CommitFailureSchema>

// CommitSummary: POST /imports/{id}/commit response
// Real shape: {batch_id, summary: {committed, failed, skipped}, failures[], batch_status}
export const CommitSummarySchema = z.object({
  batch_id: z.string(),
  summary: z.object({
    committed: z.number().int(),
    failed: z.number().int(),
    skipped: z.number().int(),
  }),
  failures: z.array(CommitFailureSchema),
  batch_status: z.enum(['committed', 'review']),
})
export type CommitSummary = z.infer<typeof CommitSummarySchema>
