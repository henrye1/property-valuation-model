import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import type { ValueByEntity } from '@/schemas/portfolio'

interface ValueByEntityChartProps {
  data: ValueByEntity[]
}

export function ValueByEntityChart({ data }: ValueByEntityChartProps) {
  if (data.length === 0) {
    return (
      <p className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">
        No data yet
      </p>
    )
  }

  // Convert decimal strings to numbers only at the Recharts boundary.
  const chartData = data.map((item) => ({
    name: item.name,
    value: Number(item.value),
  }))

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis
          type="number"
          tickFormatter={(v: number) =>
            `R ${(v / 1_000_000).toFixed(1)}M`
          }
          tick={{ fontSize: 11 }}
        />
        <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11 }} />
        <Tooltip
          formatter={(v) => {
            const n = typeof v === 'number' ? v : Number(v)
            return `R ${n.toLocaleString('en-ZA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
          }}
        />
        <Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
