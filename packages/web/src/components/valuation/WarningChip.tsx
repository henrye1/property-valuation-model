import { Badge } from '@/components/ui/badge'
import type { Warning } from '@/schemas/valuation'

interface WarningChipProps {
  warning: Warning
}

export function WarningChip({ warning }: WarningChipProps) {
  return (
    <Badge variant="secondary" title={warning.message} className="font-mono">
      {warning.code}
      {warning.message && (
        <span className="ml-1 font-sans normal-case font-normal text-muted-foreground">
          — {warning.message}
        </span>
      )}
    </Badge>
  )
}
