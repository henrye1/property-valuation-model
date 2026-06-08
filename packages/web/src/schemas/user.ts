import { z } from 'zod'

// Mirrors api/schemas/user.py AppUser
export const RoleSchema = z.enum(['valuer', 'viewer'])
export type Role = z.infer<typeof RoleSchema>

export const AppUserSchema = z.object({
  id: z.string(),
  // Real model: email is str | None (nullable, not optional)
  email: z.string().nullable(),
  display_name: z.string().nullable(),
  role: RoleSchema,
  // Real model: created_at and last_seen_at are both required fields (not optional)
  created_at: z.string(),
  last_seen_at: z.string().nullable(),
})
export type AppUser = z.infer<typeof AppUserSchema>
