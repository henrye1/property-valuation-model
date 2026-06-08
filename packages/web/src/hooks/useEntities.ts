import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'
import { useAuth } from '@/lib/auth'
import { EntitySchema } from '@/schemas/entity'

export function useEntities() {
  const { api } = useAuth()
  return useQuery({
    queryKey: ['entities'],
    queryFn: async () => z.array(EntitySchema).parse(await api.get('/entities')),
  })
}

export function useEntity(id: string) {
  const { api } = useAuth()
  return useQuery({
    queryKey: ['entity', id],
    queryFn: async () => EntitySchema.parse(await api.get(`/entities/${id}`)),
    enabled: !!id,
  })
}
