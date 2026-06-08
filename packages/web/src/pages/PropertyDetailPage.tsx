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
import { useProperty } from '@/hooks/useProperties'
import { usePropertySnapshots } from '@/hooks/useSnapshots'
import { formatZar, formatPct, formatDate } from '@/lib/format'
import type { Snapshot } from '@/schemas/snapshot'

export default function PropertyDetailPage() {
  const { id = '' } = useParams()
  const { isPending, error, data: property } = useProperty(id)
  const {
    isPending: snapsPending,
    error: snapsError,
    data: snapshots,
  } = usePropertySnapshots(id)

  const sortedSnapshots = snapshots
    ? [...snapshots].sort(
        (a: Snapshot, b: Snapshot) =>
          b.valuation_date.localeCompare(a.valuation_date),
      )
    : []

  return (
    <div className="space-y-8">
      <PageHeader title={property?.name ?? 'Property'} />

      <DataState isPending={isPending} error={error}>
        {property && (
          <div className="space-y-6">
            <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <DetailField label="Name" value={property.name} />
              <DetailField
                label="Type"
                value={property.property_type}
                badge
              />
              <div className="space-y-1">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Entity
                </p>
                <Link
                  to={`/entities/${property.entity_id}`}
                  className="text-sm text-primary hover:underline"
                >
                  View entity
                </Link>
              </div>
              <DetailField
                label="Address"
                value={property.address ?? '—'}
              />
              <DetailField
                label="Created"
                value={formatDate(property.created_at)}
              />
              <DetailField
                label="Updated"
                value={formatDate(property.updated_at)}
              />
              {property.notes && (
                <div className="sm:col-span-2 lg:col-span-3">
                  <DetailField label="Notes" value={property.notes} />
                </div>
              )}
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold">Valuation history</h2>
              <DataState isPending={snapsPending} error={snapsError}>
                {sortedSnapshots.length === 0 ? (
                  <EmptyState title="No valuations yet." />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Valuation date</TableHead>
                        <TableHead>Market value</TableHead>
                        <TableHead>Cap rate</TableHead>
                        <TableHead>Source</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sortedSnapshots.map((snap: Snapshot) => (
                        <TableRow
                          key={snap.id}
                          data-active={snap.status === 'active' || undefined}
                          className={
                            snap.status === 'active'
                              ? 'bg-primary/5'
                              : undefined
                          }
                        >
                          <TableCell>
                            <Link
                              to={`/properties/${id}/valuations/${snap.id}`}
                              className="font-medium text-primary hover:underline"
                            >
                              {formatDate(snap.valuation_date)}
                            </Link>
                          </TableCell>
                          <TableCell>
                            {formatZar(snap.market_value)}
                          </TableCell>
                          <TableCell>{formatPct(snap.cap_rate)}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{snap.source}</Badge>
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                snap.status === 'active'
                                  ? 'default'
                                  : 'secondary'
                              }
                            >
                              {snap.status}
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

function DetailField({
  label,
  value,
  badge,
}: {
  label: string
  value: string
  badge?: boolean
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      {badge ? (
        <Badge variant="secondary">{value}</Badge>
      ) : (
        <p className="text-sm text-foreground">{value}</p>
      )}
    </div>
  )
}
