import { z } from 'zod'
import { ValuationInputSchema, ValuationResultSchema } from './valuation'

// Mirrors api/schemas/snapshot.py Snapshot (response shape)
export const SnapshotStatusSchema = z.enum(['active', 'superseded'])
export type SnapshotStatus = z.infer<typeof SnapshotStatusSchema>

export const SnapshotSourceSchema = z.enum(['manual', 'excel_import'])
export type SnapshotSource = z.infer<typeof SnapshotSourceSchema>

// Real model: created_by is UUID (NOT nullable) — reference guessed nullable
// market_value and cap_rate are Decimal in Python → string on the wire
export const SnapshotSchema = z.object({
  id: z.string(),
  property_id: z.string(),
  valuation_date: z.string(),
  // created_by: required UUID (not nullable per real Pydantic model)
  created_by: z.string(),
  created_at: z.string(),
  status: SnapshotStatusSchema,
  inputs_json: ValuationInputSchema,
  result_json: ValuationResultSchema,
  market_value: z.string(),
  cap_rate: z.string(),
  engine_version: z.string(),
  source: SnapshotSourceSchema,
  source_file: z.string().nullable(),
})
export type Snapshot = z.infer<typeof SnapshotSchema>
