import { z } from 'zod'

// Mirrors api/schemas/audit.py
// Reference guessed {entries[], next_cursor} — real shape is {items[], total, limit, offset}
// AuditAction and AuditTargetTable enums confirmed against real model

export const AuditActionSchema = z.enum(['create', 'update', 'soft_delete'])
export type AuditAction = z.infer<typeof AuditActionSchema>

export const AuditTargetTableSchema = z.enum(['entity', 'property', 'valuation_snapshot', 'app_user'])
export type AuditTargetTable = z.infer<typeof AuditTargetTableSchema>

export const AuditEntrySchema = z.object({
  id: z.string(),
  actor_id: z.string(),
  actor_email: z.string().nullable(),
  action: AuditActionSchema,
  target_table: AuditTargetTableSchema,
  target_id: z.string(),
  before_json: z.record(z.string(), z.unknown()).nullable(),
  after_json: z.record(z.string(), z.unknown()).nullable(),
  created_at: z.string(),
})
export type AuditEntry = z.infer<typeof AuditEntrySchema>

// Real model: AuditPage has {items, total, limit, offset}
// Reference guessed {entries, next_cursor} — both field names AND shape were wrong
export const AuditPageSchema = z.object({
  items: z.array(AuditEntrySchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
})
export type AuditPage = z.infer<typeof AuditPageSchema>
