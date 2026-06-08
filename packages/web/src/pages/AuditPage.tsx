import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { DataState } from '@/components/layout/DataState'
import { EmptyState } from '@/components/layout/EmptyState'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAudit } from '@/hooks/useAudit'
import { formatDateTime } from '@/lib/format'
import type { AuditAction } from '@/schemas/audit'

const PAGE_SIZE = 50

function actionVariant(
  action: AuditAction,
): 'default' | 'secondary' | 'destructive' {
  switch (action) {
    case 'create':
      return 'default'
    case 'update':
      return 'secondary'
    case 'soft_delete':
      return 'destructive'
  }
}

function shortId(id: string): string {
  // Show first 8 chars of UUID for readability
  return id.slice(0, 8)
}

export default function AuditPage() {
  const [offset, setOffset] = useState(0)
  const { isPending, error, data } = useAudit(PAGE_SIZE, offset)

  const hasPrev = offset > 0
  const hasNext = data != null && offset + PAGE_SIZE < data.total

  return (
    <div className="space-y-6">
      <PageHeader title="Audit log" />
      <DataState isPending={isPending} error={error}>
        {data && data.items.length === 0 ? (
          <EmptyState title="No audit entries" />
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Target</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="whitespace-nowrap text-muted-foreground">
                      {formatDateTime(entry.created_at)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {entry.actor_email ?? entry.actor_id}
                    </TableCell>
                    <TableCell>
                      <Badge variant={actionVariant(entry.action)}>
                        {entry.action}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {entry.target_table}{' '}
                      <span className="font-mono text-xs">
                        {shortId(entry.target_id)}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {(hasPrev || hasNext) && (
              <div className="flex items-center justify-between pt-2">
                <span className="text-sm text-muted-foreground">
                  {data
                    ? `Showing ${offset + 1}–${Math.min(offset + PAGE_SIZE, data.total)} of ${data.total}`
                    : ''}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    disabled={!hasPrev}
                    onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    disabled={!hasNext}
                    onClick={() => setOffset((o) => o + PAGE_SIZE)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </DataState>
    </div>
  )
}
