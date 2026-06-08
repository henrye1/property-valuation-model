import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'
import { useAuth } from '@/lib/auth'
import { PropertySchema } from '@/schemas/property'

export function useProperties() {
  const { api } = useAuth()
  return useQuery({
    queryKey: ['properties'],
    queryFn: async () => z.array(PropertySchema).parse(await api.get('/properties')),
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
