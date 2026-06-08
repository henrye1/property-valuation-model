import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatZar, formatPct } from '@/lib/format'
import type { ValuationResult } from '@/schemas/valuation'
import { WarningChip } from './WarningChip'

interface ResultPanelProps {
  result: ValuationResult
}

// A purely presentational income-waterfall + tenant breakdown component.
// No hooks, no data fetching.
export function ResultPanel({ result }: ResultPanelProps) {
  return (
    <div className="space-y-6">
      {/* Income waterfall */}
      <Card>
        <CardHeader>
          <CardTitle>Valuation waterfall</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="divide-y divide-border text-sm">
            <WaterfallRow
              label="Gross monthly rent — tenants"
              value={formatZar(result.gross_monthly_rent_tenants)}
            />
            <WaterfallRow
              label="Gross monthly rent — parking"
              value={formatZar(result.gross_monthly_rent_parking)}
            />
            <WaterfallRow
              label="Gross monthly income"
              value={formatZar(result.gross_monthly_income)}
              bold
            />
            <WaterfallRow
              label="Gross annual income"
              value={formatZar(result.gross_annual_income)}
              bold
            />
            <WaterfallRow
              label={
                <>
                  Annual operating expenses
                  <span className="ml-2 font-normal text-muted-foreground">
                    ({formatZar(result.opex_per_m2_pm)}/m²/pm ·{' '}
                    {formatPct(result.opex_pct_of_gai)} of GAI)
                  </span>
                </>
              }
              value={formatZar(result.annual_operating_expenses)}
            />
            <WaterfallRow
              label="Vacancy allowance"
              value={formatZar(result.vacancy_allowance_amount)}
            />
            <WaterfallRow
              label="Annual net income"
              value={formatZar(result.annual_net_income)}
              bold
            />
            <WaterfallRow
              label="Capitalised value"
              value={formatZar(result.capitalised_value)}
            />
            {/* Market value — emphasised */}
            <div className="flex items-baseline justify-between py-3">
              <dt className="font-semibold text-base">Market value</dt>
              <dd className="tabular-nums font-bold text-lg text-primary">
                {formatZar(result.market_value)}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* Resolved tenants */}
      {result.tenants_resolved.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Resolved tenants</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Description</TableHead>
                  <TableHead className="text-right">Area (m²)</TableHead>
                  <TableHead className="text-right">Effective rent (R/m²/pm)</TableHead>
                  <TableHead className="text-right">Monthly rent</TableHead>
                  <TableHead className="text-right">Esc. cycles</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.tenants_resolved.map((tenant, i) => (
                  <TableRow key={i}>
                    <TableCell>{tenant.description}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {tenant.rentable_area_m2}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatZar(tenant.effective_rent_per_m2_pm)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatZar(tenant.monthly_rent)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {tenant.escalation_cycles_applied}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Warnings */}
      {result.warnings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Warnings</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-wrap gap-2">
              {result.warnings.map((w, i) => (
                <li key={i}>
                  <WarningChip warning={w} />
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// Internal helper — keeps the waterfall DL rows tidy.
function WaterfallRow({
  label,
  value,
  bold,
}: {
  label: React.ReactNode
  value: string
  bold?: boolean
}) {
  return (
    <div className="flex items-baseline justify-between py-2">
      <dt className={bold ? 'font-medium' : 'text-muted-foreground'}>{label}</dt>
      <dd className={`tabular-nums${bold ? ' font-semibold' : ''}`}>{value}</dd>
    </div>
  )
}
