import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { DiffBadge } from '@/components/import/DiffBadge'
import { formatZar } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { ImportItem, ParseStatus, Resolution } from '@/schemas/imports'

// ─── badge helpers ────────────────────────────────────────────────────────────

type BadgeVariant = 'default' | 'secondary' | 'outline' | 'destructive'

function parseStatusVariant(s: ParseStatus): BadgeVariant {
  switch (s) {
    case 'ok':
      return 'secondary'
    case 'warning':
      return 'default'
    case 'error':
      return 'destructive'
  }
}

function resolutionVariant(r: Resolution): BadgeVariant {
  switch (r) {
    case 'pending':
      return 'outline'
    case 'accepted':
      return 'secondary'
    case 'edited':
      return 'default'
    case 'rejected':
      return 'destructive'
    case 'committed':
      return 'outline'
  }
}

// ─── property name helper ─────────────────────────────────────────────────────

function displayPropertyName(item: ImportItem): string {
  if (item.building_name) return item.building_name
  if (item.suggestion?.property_name) return item.suggestion.property_name
  return '—'
}

// ─── component ───────────────────────────────────────────────────────────────

interface ImportItemTableProps {
  items: ImportItem[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export function ImportItemTable({ items, selectedId, onSelect }: ImportItemTableProps) {
  if (items.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No items — the batch may still be parsing.
      </p>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Filename</TableHead>
          <TableHead>Property</TableHead>
          <TableHead>Sheet value</TableHead>
          <TableHead>Recomputed</TableHead>
          <TableHead>Diff</TableHead>
          <TableHead>Parse</TableHead>
          <TableHead>Resolution</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow
            key={item.id}
            data-state={item.id === selectedId ? 'selected' : undefined}
            className={cn('cursor-pointer', item.id === selectedId && 'bg-muted')}
            onClick={() => onSelect(item.id)}
          >
            <TableCell className="max-w-48 truncate font-medium">{item.filename}</TableCell>
            <TableCell className="max-w-40 truncate text-muted-foreground">
              {displayPropertyName(item)}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatZar(item.spreadsheet_market_value)}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatZar(item.recomputed_market_value)}
            </TableCell>
            <TableCell>
              <DiffBadge diffPct={item.diff_pct} />
            </TableCell>
            <TableCell>
              <Badge variant={parseStatusVariant(item.parse_status)}>
                {item.parse_status}
              </Badge>
            </TableCell>
            <TableCell>
              <Badge variant={resolutionVariant(item.resolution)}>
                {item.resolution}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
