import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useAuth } from '@/lib/auth'
import { PropertySchema, type Property } from '@/schemas/property'

// Derive input types from Property — avoid redefining field sets
type CreatePropertyInput = Pick<Property, 'entity_id' | 'name' | 'property_type'> &
  Partial<Pick<Property, 'address' | 'notes'>>
type UpdatePropertyInput = Partial<Pick<Property, 'entity_id' | 'name' | 'address' | 'property_type' | 'notes'>>

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred'
}

export function useCreateProperty() {
  const { api } = useAuth()
  const qc = useQueryClient()

  return useMutation({
    mutationFn: async (input: CreatePropertyInput): Promise<Property> =>
      PropertySchema.parse(await api.post('/properties', input)),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['properties'] })
    },
    onError: (err) => {
      toast.error(errorMessage(err))
    },
  })
}

export function useUpdateProperty() {
  const { api } = useAuth()
  const qc = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, ...input }: UpdatePropertyInput & { id: string }): Promise<Property> =>
      PropertySchema.parse(await api.patch(`/properties/${id}`, input)),
    onSuccess: async (_data, { id }) => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['properties'] }),
        qc.invalidateQueries({ queryKey: ['property', id] }),
      ])
    },
    onError: (err) => {
      toast.error(errorMessage(err))
    },
  })
}

export function useDeleteProperty() {
  const { api } = useAuth()
  const qc = useQueryClient()

  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      await api.del(`/properties/${id}`)
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['properties'] })
    },
    onError: (err) => {
      toast.error(errorMessage(err))
    },
  })
}
