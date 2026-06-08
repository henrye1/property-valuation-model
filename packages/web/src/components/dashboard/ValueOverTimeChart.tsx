import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import type { TimeseriesPoint } from '@/schemas/portfolio'
import { formatZar } from '@/lib/format'

interface ValueOverTimeChartProps {
  data: TimeseriesPoint[]
}

export function ValueOverTimeChart({ data }: ValueOverTimeChartProps) {
  if (data.length === 0) {
    return (
      <p className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">
        No data yet
      </p>
    )
  }

  // Convert decimal strings to numbers only at the Recharts boundary.
  const chartData = data.map((pt) => ({
    date: pt.bucket_date,
    value: Number(pt.total_market_value),
    // Keep the raw string for the tooltip formatter (no precision loss).
    rawValue: pt.total_market_value,
  }))

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={chartData} margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis
          tickFormatter={(v: number) => `R ${(v / 1_000_000).toFixed(1)}M`}
          tick={{ fontSize: 11 }}
          width={70}
        />
        <Tooltip
          formatter={(_v, _name, item) => {
            const rawValue = (item.payload as { rawValue?: string } | undefined)?.rawValue
            return [formatZar(rawValue), 'Total value']
          }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke="#6366f1"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
