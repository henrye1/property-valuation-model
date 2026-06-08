import { Link } from 'react-router-dom'
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
import { useEntities } from '@/hooks/useEntities'

export default function EntitiesPage() {
  const { isPending, error, data: entities } = useEntities()

  return (
    <div className="space-y-6">
      <PageHeader title="Entities" />
      <DataState isPending={isPending} error={error}>
        {entities && entities.length === 0 ? (
          <EmptyState title="No entities yet" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Registration #</TableHead>
                <TableHead>Notes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entities?.map((entity) => (
                <TableRow key={entity.id}>
                  <TableCell>
                    <Link
                      to={`/entities/${entity.id}`}
                      className="font-medium text-primary hover:underline"
                    >
                      {entity.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {entity.registration_number ?? '—'}
                  </TableCell>
                  <TableCell
                    className="max-w-xs truncate text-muted-foreground"
                    title={entity.notes ?? undefined}
                  >
                    {entity.notes ?? '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DataState>
    </div>
  )
}
