import { z } from 'zod'

// Mirrors api/schemas/property.py Property (response shape)
export const PropertyTypeSchema = z.enum(['office', 'retail', 'industrial', 'mixed', 'residential', 'other'])
export type PropertyType = z.infer<typeof PropertyTypeSchema>

// updated_at and deleted_at are datetime | None in the real model
export const PropertySchema = z.object({
  id: z.string(),
  entity_id: z.string(),
  name: z.string(),
  address: z.string().nullable(),
  property_type: PropertyTypeSchema,
  notes: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string().nullable(),
  deleted_at: z.string().nullable(),
})
export type Property = z.infer<typeof PropertySchema>
