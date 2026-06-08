import { useState } from 'react'
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
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { useProperties } from '@/hooks/useProperties'
import { useEntities } from '@/hooks/useEntities'

export default function PropertiesPage() {
  const [filter, setFilter] = useState('')
  const { isPending: propsPending, error: propsError, data: properties } = useProperties()
  const { isPending: entitiesPending, error: entitiesError, data: entities } = useEntities()

  const isPending = propsPending || entitiesPending
  const error = propsError ?? entitiesError

  const entityMap = new Map((entities ?? []).map((e) => [e.id, e.name]))

  const q = filter.trim().toLowerCase()
  const filtered = (properties ?? []).filter((p) => {
    if (!q) return true
    return (
      p.name.toLowerCase().includes(q) ||
      (p.address ?? '').toLowerCase().includes(q)
    )
  })

  return (
    <div className="space-y-6">
      <PageHeader title="Properties" />

      <DataState isPending={isPending} error={error}>
        {properties && properties.length === 0 ? (
          <EmptyState title="No properties yet" />
        ) : (
          <div className="space-y-4">
            <Input
              placeholder="Filter by name or address…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="max-w-sm"
            />
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Entity</TableHead>
                  <TableHead>Address</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={4}
                      className="py-8 text-center text-sm text-muted-foreground"
                    >
                      No matches for &ldquo;{filter}&rdquo;.
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((prop) => (
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
                        <Badge variant="secondary">{prop.property_type}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {entityMap.get(prop.entity_id) ?? '—'}
                      </TableCell>
                      <TableCell
                        className="max-w-xs truncate text-muted-foreground"
                        title={prop.address ?? undefined}
                      >
                        {prop.address ?? '—'}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </DataState>
    </div>
  )
}
