import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'
import { useAuth } from '@/lib/auth'
import { AppUserSchema, type AppUser } from '@/schemas/user'

/**
 * Fetch the list of app users.
 * GET /users → AppUser[]
 */
export function useUsers() {
  const { api } = useAuth()
  return useQuery<AppUser[]>({
    queryKey: ['users'],
    queryFn: async () =>
      z.array(AppUserSchema).parse(await api.get('/users')),
  })
}
