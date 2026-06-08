import { z } from 'zod'

// Mirrors api/schemas/entity.py Entity (response shape)
// updated_at is datetime | None in the real model (nullable, not just optional)
export const EntitySchema = z.object({
  id: z.string(),
  name: z.string(),
  registration_number: z.string().nullable(),
  notes: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string().nullable(),
  deleted_at: z.string().nullable(),
})
export type Entity = z.infer<typeof EntitySchema>
