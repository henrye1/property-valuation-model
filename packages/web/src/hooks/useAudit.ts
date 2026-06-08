import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/lib/auth'
import { AuditPageSchema, type AuditPage } from '@/schemas/audit'

/**
 * Fetch a page of audit-log entries.
 * GET /audit?limit=&offset=
 *
 * Backend supports limit (1–200, default 50) and offset (≥0, default 0).
 */
export function useAudit(limit = 50, offset = 0) {
  const { api } = useAuth()
  return useQuery<AuditPage>({
    queryKey: ['audit', limit, offset],
    queryFn: async () =>
      AuditPageSchema.parse(
        await api.get(`/audit?limit=${limit}&offset=${offset}`),
      ),
  })
}
