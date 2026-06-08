import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useAuth } from '@/lib/auth'
import { SnapshotSchema, type Snapshot } from '@/schemas/snapshot'
import type { ValuationInput } from '@/schemas/valuation'

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred'
}

export function useCreateSnapshot(propertyId: string) {
  const { api } = useAuth()
  const qc = useQueryClient()

  return useMutation({
    mutationFn: async (input: ValuationInput): Promise<Snapshot> =>
      SnapshotSchema.parse(await api.post(`/properties/${propertyId}/snapshots`, input)),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['property', propertyId] }),
        qc.invalidateQueries({ queryKey: ['property', propertyId, 'snapshots'] }),
      ])
    },
    onError: (err) => {
      toast.error(errorMessage(err))
    },
  })
}
