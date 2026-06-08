import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'
import { useAuth } from '@/lib/auth'
import { PropertySchema } from '@/schemas/property'

export function useProperties(entityId?: string) {
  const { api } = useAuth()
  const path = entityId ? `/properties?entity_id=${entityId}` : '/properties'
  const queryKey = entityId ? ['properties', { entityId }] : ['properties']
  return useQuery({
    queryKey,
    queryFn: async () => z.array(PropertySchema).parse(await api.get(path)),
  })
}

export function useProperty(id: string) {
  const { api } = useAuth()
  return useQuery({
    queryKey: ['property', id],
    queryFn: async () => PropertySchema.parse(await api.get(`/properties/${id}`)),
    enabled: !!id,
  })
}
