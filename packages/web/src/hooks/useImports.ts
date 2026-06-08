import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useAuth } from '@/lib/auth'
import {
  CommitSummarySchema,
  ImportBatchListSchema,
  ImportBatchSchema,
  ImportCreatedSchema,
  ImportItemSchema,
  type CommitSummary,
  type ImportBatch,
  type ImportBatchList,
  type ImportCreated,
  type ImportItem,
} from '@/schemas/imports'

// ─── helpers ────────────────────────────────────────────────────────────────

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message
  return 'An unexpected error occurred'
}

// PATCH /imports/{batchId}/items/{itemId} request body.
// Mirrors the backend ImportItemPatch Pydantic model exactly.
export interface ImportItemPatchBody {
  /** Only 'accepted', 'rejected', or 'edited' are valid for a PATCH. */
  resolution: 'accepted' | 'rejected' | 'edited'
  resolved_property_id?: string | null
  resolved_inputs?: Record<string, unknown> | null
  resolution_notes?: string | null
}

// ─── queries ────────────────────────────────────────────────────────────────

/**
 * List all import batches.
 * GET /imports → ImportBatchList
 */
export function useImportBatches() {
  const { api } = useAuth()
  return useQuery<ImportBatchList>({
    queryKey: ['imports'],
    queryFn: async () =>
      ImportBatchListSchema.parse(await api.get('/imports')),
  })
}

/**
 * Fetch a single import batch (with items).
 * GET /imports/{id} → ImportBatch
 *
 * Polls every 1 500 ms while the batch status is 'parsing', otherwise disabled.
 */
export function useImportBatch(id: string | null | undefined) {
  const { api } = useAuth()
  return useQuery<ImportBatch>({
    queryKey: ['import', id],
    queryFn: async () =>
      ImportBatchSchema.parse(await api.get(`/imports/${id}`)),
    enabled: !!id,
    refetchInterval: (query) =>
      query.state.data?.status === 'parsing' ? 1500 : false,
  })
}

// ─── mutations ───────────────────────────────────────────────────────────────

/**
 * Upload one or more .xlsx files as a new import batch.
 * POST /imports (multipart, field name: "files") → ImportCreated (202)
 */
export function useUploadImport() {
  const { api } = useAuth()
  const qc = useQueryClient()

  return useMutation<ImportCreated, Error, File[]>({
    mutationFn: async (files: File[]): Promise<ImportCreated> => {
      const form = new FormData()
      for (const file of files) {
        // Backend expects the multipart field named "files" (list[UploadFile]).
        form.append('files', file)
      }
      return ImportCreatedSchema.parse(await api.postForm('/imports', form))
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['imports'] })
    },
    onError: (err) => {
      toast.error(errorMessage(err))
    },
  })
}

/**
 * Patch a single import item's resolution.
 * PATCH /imports/{batchId}/items/{itemId} → ImportItem
 */
export function usePatchImportItem(batchId: string) {
  const { api } = useAuth()
  const qc = useQueryClient()

  return useMutation<ImportItem, Error, { itemId: string; body: ImportItemPatchBody }>({
    mutationFn: async ({ itemId, body }) =>
      ImportItemSchema.parse(
        await api.patch(`/imports/${batchId}/items/${itemId}`, body),
      ),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['import', batchId] })
    },
    onError: (err) => {
      toast.error(errorMessage(err))
    },
  })
}

/**
 * Commit a batch (finalise all accepted/edited/rejected items).
 * POST /imports/{id}/commit → CommitSummary
 */
export function useCommitBatch(id: string) {
  const { api } = useAuth()
  const qc = useQueryClient()

  return useMutation<CommitSummary, Error, void>({
    mutationFn: async () =>
      CommitSummarySchema.parse(await api.post(`/imports/${id}/commit`)),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['import', id] }),
        qc.invalidateQueries({ queryKey: ['imports'] }),
      ])
    },
    onError: (err) => {
      toast.error(errorMessage(err))
    },
  })
}

/**
 * Cancel a batch (sets status to 'cancelled' and purges storage files).
 * POST /imports/{id}/cancel → { id, status }
 */
export function useCancelBatch(id: string) {
  const { api } = useAuth()
  const qc = useQueryClient()

  return useMutation<unknown, Error, void>({
    mutationFn: async () => api.post(`/imports/${id}/cancel`),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['import', id] }),
        qc.invalidateQueries({ queryKey: ['imports'] }),
      ])
    },
    onError: (err) => {
      toast.error(errorMessage(err))
    },
  })
}
