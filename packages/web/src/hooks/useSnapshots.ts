import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'
import { useAuth } from '@/lib/auth'
import { SnapshotSchema } from '@/schemas/snapshot'

export function usePropertySnapshots(propertyId: string) {
  const { api } = useAuth()
  return useQuery({
    queryKey: ['property', propertyId, 'snapshots'],
    queryFn: async () =>
      z.array(SnapshotSchema).parse(await api.get(`/properties/${propertyId}/snapshots`)),
    enabled: !!propertyId,
  })
}

export function useSnapshot(id: string) {
  const { api } = useAuth()
  return useQuery({
    queryKey: ['snapshot', id],
    queryFn: async () => SnapshotSchema.parse(await api.get(`/snapshots/${id}`)),
    enabled: !!id,
  })
}
