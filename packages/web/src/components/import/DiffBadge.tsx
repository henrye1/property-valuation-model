import { Badge } from '@/components/ui/badge'
import { formatPct } from '@/lib/format'

/** Threshold matches backend `recompute_mismatch` at 0.1 % (0.001 as a decimal). */
const THRESHOLD = 0.001

interface DiffBadgeProps {
  diffPct: string | null | undefined
}

export function DiffBadge({ diffPct }: DiffBadgeProps) {
  if (diffPct == null) {
    return <span>—</span>
  }

  const magnitude = Math.abs(parseFloat(diffPct))
  const isOk = magnitude <= THRESHOLD
  const state = isOk ? 'ok' : 'mismatch'

  return (
    <Badge
      data-diff={state}
      variant={isOk ? 'secondary' : 'destructive'}
    >
      {formatPct(diffPct)}
    </Badge>
  )
}
