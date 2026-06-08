import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { DataState } from '@/components/layout/DataState'
import { EmptyState } from '@/components/layout/EmptyState'
import { RoleGate } from '@/components/layout/RoleGate'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useImportBatches } from '@/hooks/useImports'
import { formatDate } from '@/lib/format'
import type { BatchStatus } from '@/schemas/imports'

function statusVariant(
  status: BatchStatus,
): 'default' | 'secondary' | 'outline' | 'destructive' {
  switch (status) {
    case 'parsing':
      return 'secondary'
    case 'review':
      return 'default'
    case 'committed':
      return 'outline'
    case 'cancelled':
      return 'destructive'
  }
}

const newImportAction = (
  <RoleGate>
    <Button render={<Link to="/imports/new" />}>New import</Button>
  </RoleGate>
)

export default function ImportsPage() {
  const { isPending, error, data } = useImportBatches()

  return (
    <div className="space-y-6">
      <PageHeader title="Imports" action={newImportAction} />
      <DataState isPending={isPending} error={error}>
        {data && data.items.length === 0 ? (
          <EmptyState
            title="No imports yet"
            description="Upload one or more .xlsx valuation files to create an import batch."
            action={newImportAction}
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Uploaded</TableHead>
                <TableHead>Files</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Pending</TableHead>
                <TableHead>Accepted</TableHead>
                <TableHead>Rejected</TableHead>
                <TableHead>Committed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((batch) => (
                <TableRow key={batch.id}>
                  <TableCell>
                    <Link
                      to={`/imports/${batch.id}`}
                      className="font-medium text-primary hover:underline"
                    >
                      {formatDate(batch.uploaded_at)}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{batch.file_count}</TableCell>
                  <TableCell>
                    <Badge variant={statusVariant(batch.status)}>{batch.status}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{batch.counts.pending}</TableCell>
                  <TableCell className="text-muted-foreground">{batch.counts.accepted}</TableCell>
                  <TableCell className="text-muted-foreground">{batch.counts.rejected}</TableCell>
                  <TableCell className="text-muted-foreground">{batch.counts.committed}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DataState>
    </div>
  )
}
