import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { ValueByType } from '@/schemas/portfolio'

const COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#14b8a6', '#8b5cf6']

interface ValueByTypeChartProps {
  data: ValueByType[]
}

export function ValueByTypeChart({ data }: ValueByTypeChartProps) {
  if (data.length === 0) {
    return (
      <p className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">
        No data yet
      </p>
    )
  }

  // Convert decimal strings to numbers only at the Recharts boundary.
  const chartData = data.map((item) => ({
    name: item.type,
    value: Number(item.value),
  }))

  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie
          data={chartData}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={95}
        >
          {chartData.map((_entry, index) => (
            <Cell key={index} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          formatter={(v) => {
            const n = typeof v === 'number' ? v : Number(v)
            return `R ${n.toLocaleString('en-ZA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
          }}
        />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  )
}
