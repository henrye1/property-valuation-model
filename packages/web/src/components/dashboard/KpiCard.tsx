import { Card, CardContent } from '@/components/ui/card'

interface KpiCardProps {
  label: string
  value: string
}

export function KpiCard({ label, value }: KpiCardProps) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-1 py-4">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          {label}
        </span>
        <span className="text-2xl font-semibold tabular-nums">{value}</span>
      </CardContent>
    </Card>
  )
}
