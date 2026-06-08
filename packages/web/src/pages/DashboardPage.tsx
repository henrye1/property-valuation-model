import { Link } from 'react-router-dom'
import { usePortfolioSummary, usePortfolioTimeseries } from '@/hooks/usePortfolio'
import { PageHeader } from '@/components/layout/PageHeader'
import { DataState } from '@/components/layout/DataState'
import { EmptyState } from '@/components/layout/EmptyState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { KpiCard } from '@/components/dashboard/KpiCard'
import { ValueByTypeChart } from '@/components/dashboard/ValueByTypeChart'
import { ValueByEntityChart } from '@/components/dashboard/ValueByEntityChart'
import { ValueOverTimeChart } from '@/components/dashboard/ValueOverTimeChart'
import { formatZar, formatDate } from '@/lib/format'

export default function DashboardPage() {
  const summaryQuery = usePortfolioSummary()
  const timeseriesQuery = usePortfolioTimeseries()

  return (
    <div className="space-y-6">
      <PageHeader title="Portfolio" />

      <DataState isPending={summaryQuery.isPending} error={summaryQuery.error}>
        {summaryQuery.data && summaryQuery.data.property_count === 0 ? (
          <EmptyState
            title="No valuations yet"
            description="Add properties and run a valuation snapshot to see your portfolio dashboard."
          />
        ) : summaryQuery.data ? (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <KpiCard
                label="Total value"
                value={formatZar(summaryQuery.data.total_market_value)}
              />
              <KpiCard
                label="Properties"
                value={String(summaryQuery.data.property_count)}
              />
              <KpiCard
                label="Entities"
                value={String(summaryQuery.data.entity_count)}
              />
              <KpiCard
                label="Last snapshot"
                value={formatDate(summaryQuery.data.last_snapshot_date)}
              />
            </div>

            {/* Charts grid */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Value by type</CardTitle>
                </CardHeader>
                <CardContent>
                  <ValueByTypeChart data={summaryQuery.data.value_by_type} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Value by entity</CardTitle>
                </CardHeader>
                <CardContent>
                  <ValueByEntityChart data={summaryQuery.data.value_by_entity} />
                </CardContent>
              </Card>
            </div>

            {/* Timeseries — full width */}
            <Card>
              <CardHeader>
                <CardTitle>Portfolio value over time</CardTitle>
              </CardHeader>
              <CardContent>
                <DataState
                  isPending={timeseriesQuery.isPending}
                  error={timeseriesQuery.error}
                >
                  <ValueOverTimeChart data={timeseriesQuery.data?.points ?? []} />
                </DataState>
              </CardContent>
            </Card>

            {/* Top properties table */}
            <Card>
              <CardHeader>
                <CardTitle>Top properties</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead className="text-right">Market value</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {summaryQuery.data.top_properties.map((prop) => (
                      <TableRow key={prop.property_id}>
                        <TableCell>
                          <Link
                            to={`/properties/${prop.property_id}`}
                            className="text-primary hover:underline"
                          >
                            {prop.name}
                          </Link>
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatZar(prop.value)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </>
        ) : null}
      </DataState>
    </div>
  )
}
