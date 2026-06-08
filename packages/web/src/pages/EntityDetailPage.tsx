import { Link, useParams } from 'react-router-dom'
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
import { useEntity } from '@/hooks/useEntities'
import { useProperties } from '@/hooks/useProperties'
import { formatDate } from '@/lib/format'

export default function EntityDetailPage() {
  const { id = '' } = useParams()
  const { isPending, error, data: entity } = useEntity(id)
  const { isPending: propsPending, error: propsError, data: allProperties } = useProperties()

  const entityProperties = allProperties?.filter((p) => p.entity_id === id) ?? []

  return (
    <div className="space-y-8">
      <PageHeader title={entity?.name ?? 'Entity'} />

      <DataState isPending={isPending} error={error}>
        {entity && (
          <div className="space-y-6">
            <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <DetailField label="Name" value={entity.name} />
              <DetailField
                label="Registration #"
                value={entity.registration_number ?? '—'}
              />
              <DetailField
                label="Created"
                value={formatDate(entity.created_at)}
              />
              <DetailField
                label="Updated"
                value={formatDate(entity.updated_at)}
              />
              {entity.notes && (
                <div className="sm:col-span-2 lg:col-span-3">
                  <DetailField label="Notes" value={entity.notes} />
                </div>
              )}
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold">Properties</h2>
              <DataState isPending={propsPending} error={propsError}>
                {entityProperties.length === 0 ? (
                  <EmptyState title="No properties for this entity." />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Type</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {entityProperties.map((prop) => (
                        <TableRow key={prop.id}>
                          <TableCell>
                            <Link
                              to={`/properties/${prop.id}`}
                              className="font-medium text-primary hover:underline"
                            >
                              {prop.name}
                            </Link>
                          </TableCell>
                          <TableCell>
                            <Badge variant="secondary">
                              {prop.property_type}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </DataState>
            </section>
          </div>
        )}
      </DataState>
    </div>
  )
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className="text-sm text-foreground">{value}</p>
    </div>
  )
}
