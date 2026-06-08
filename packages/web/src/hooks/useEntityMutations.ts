import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useAuth } from '@/lib/auth'
import { EntitySchema, type Entity } from '@/schemas/entity'

// Derive input types from Entity — avoid redefining field sets
type CreateEntityInput = Pick<Entity, 'name'> & Partial<Pick<Entity, 'registration_number' | 'notes'>>
type UpdateEntityInput = Partial<Pick<Entity, 'name' | 'registration_number' | 'notes'>>

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred'
}

export function useCreateEntity() {
  const { api } = useAuth()
  const qc = useQueryClient()

  return useMutation({
    mutationFn: async (input: CreateEntityInput): Promise<Entity> =>
      EntitySchema.parse(await api.post('/entities', input)),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['entities'] })
    },
    onError: (err) => {
      toast.error(errorMessage(err))
    },
  })
}

export function useUpdateEntity() {
  const { api } = useAuth()
  const qc = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, ...input }: UpdateEntityInput & { id: string }): Promise<Entity> =>
      EntitySchema.parse(await api.patch(`/entities/${id}`, input)),
    onSuccess: async (_data, { id }) => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['entities'] }),
        qc.invalidateQueries({ queryKey: ['entity', id] }),
      ])
    },
    onError: (err) => {
      toast.error(errorMessage(err))
    },
  })
}

export function useDeleteEntity() {
  const { api } = useAuth()
  const qc = useQueryClient()

  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      await api.del(`/entities/${id}`)
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['entities'] })
    },
    onError: (err) => {
      toast.error(errorMessage(err))
    },
  })
}
