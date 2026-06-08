import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { PageHeader } from '@/components/layout/PageHeader'
import { DataState } from '@/components/layout/DataState'
import { RoleGate } from '@/components/layout/RoleGate'
import { ResultPanel } from '@/components/valuation/ResultPanel'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useSnapshot } from '@/hooks/useSnapshots'
import { useAuth } from '@/lib/auth'
import { downloadOrToast } from '@/lib/download'
import { formatZar, formatPct, formatDate } from '@/lib/format'

export default function SnapshotViewerPage() {
  const { id = '', sid = '' } = useParams()
  const { api } = useAuth()
  const { isPending, error, data: snapshot } = useSnapshot(sid)

  return (
    <div className="space-y-8">
      <DataState isPending={isPending} error={error}>
        {snapshot && (
          <>
            <PageHeader
              title={`Valuation — ${formatDate(snapshot.valuation_date)}`}
              action={
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      void downloadOrToast(api, `/snapshots/${sid}/export.pdf`, (msg) =>
                        toast.error(msg),
                      )
                    }
                  >
                    Export PDF
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      void downloadOrToast(api, `/snapshots/${sid}/export.xlsx`, (msg) =>
                        toast.error(msg),
                      )
                    }
                  >
                    Export XLSX
                  </Button>
                  <RoleGate>
                    <Button
                      variant="secondary"
                      size="sm"
                      render={
                        <Link
                          to={`/properties/${id}/valuations/new`}
                          state={{ prefill: snapshot.inputs_json }}
                        />
                      }
                    >
                      New valuation from this
                    </Button>
                  </RoleGate>
                </div>
              }
            />

            {/* Snapshot metadata */}
            <Card>
              <CardHeader>
                <CardTitle>Snapshot details</CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3 lg:grid-cols-4">
                  <MetaField label="Status">
                    <Badge variant={snapshot.status === 'active' ? 'default' : 'secondary'}>
                      {snapshot.status}
                    </Badge>
                  </MetaField>
                  <MetaField label="Source">
                    <Badge variant="outline">{snapshot.source}</Badge>
                  </MetaField>
                  <MetaField label="Engine version">
                    <span className="font-mono text-xs">{snapshot.engine_version}</span>
                  </MetaField>
                  <MetaField label="Author">
                    <span>{snapshot.created_by}</span>
                  </MetaField>
                  <MetaField label="Created">
                    <span>{formatDate(snapshot.created_at)}</span>
                  </MetaField>
                  {snapshot.source_file && (
                    <MetaField label="Source file">
                      <span className="font-mono text-xs break-all">{snapshot.source_file}</span>
                    </MetaField>
                  )}
                </dl>
              </CardContent>
            </Card>

            {/* Inputs summary */}
            <Card>
              <CardHeader>
                <CardTitle>Inputs</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
                  <MetaField label="Valuation date">
                    <span>{formatDate(snapshot.inputs_json.valuation_date)}</span>
                  </MetaField>
                  <MetaField label="Cap rate">
                    <span className="tabular-nums">{formatPct(snapshot.inputs_json.cap_rate)}</span>
                  </MetaField>
                  <MetaField label="Vacancy allowance">
                    <span className="tabular-nums">
                      {formatPct(snapshot.inputs_json.vacancy_allowance_pct)}
                    </span>
                  </MetaField>
                  <MetaField label="Monthly opex">
                    <span className="tabular-nums">
                      {formatZar(snapshot.inputs_json.monthly_operating_expenses)}
                    </span>
                  </MetaField>
                  <MetaField label="Rounding">
                    <span>{snapshot.inputs_json.rounding}</span>
                  </MetaField>
                  <MetaField label="Tenants">
                    <span>{snapshot.inputs_json.tenants.length}</span>
                  </MetaField>
                  <MetaField label="Parking bays">
                    <span>
                      {snapshot.inputs_json.parking.reduce((s, p) => s + p.bays, 0)}
                    </span>
                  </MetaField>
                </dl>

                {snapshot.inputs_json.tenants.length > 0 && (
                  <div>
                    <h3 className="mb-2 text-sm font-medium">Tenant lines</h3>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Description</TableHead>
                          <TableHead className="text-right">Area (m²)</TableHead>
                          <TableHead className="text-right">Rent (R/m²/pm)</TableHead>
                          <TableHead className="text-right">Escalation</TableHead>
                          <TableHead>Next esc. date</TableHead>
                          <TableHead>Expiry</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {snapshot.inputs_json.tenants.map((t, i) => (
                          <TableRow key={i}>
                            <TableCell>
                              {t.tenant_name ? `${t.description} (${t.tenant_name})` : t.description}
                            </TableCell>
                            <TableCell className="text-right tabular-nums">
                              {t.rentable_area_m2}
                            </TableCell>
                            <TableCell className="text-right tabular-nums">
                              {formatZar(t.rent_per_m2_pm)}
                            </TableCell>
                            <TableCell className="text-right tabular-nums">
                              {formatPct(t.annual_escalation_pct)}
                            </TableCell>
                            <TableCell>{t.next_escalation_date ?? '—'}</TableCell>
                            <TableCell>{t.lease_expiry_date ?? '—'}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}

                {snapshot.inputs_json.parking.length > 0 && (
                  <div>
                    <h3 className="mb-2 text-sm font-medium">Parking lines</h3>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Bay type</TableHead>
                          <TableHead className="text-right">Bays</TableHead>
                          <TableHead className="text-right">Rate (R/bay/pm)</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {snapshot.inputs_json.parking.map((p, i) => (
                          <TableRow key={i}>
                            <TableCell>{p.bay_type}</TableCell>
                            <TableCell className="text-right tabular-nums">{p.bays}</TableCell>
                            <TableCell className="text-right tabular-nums">
                              {formatZar(p.rate_per_bay_pm)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Result waterfall */}
            <ResultPanel result={snapshot.result_json} />
          </>
        )}
      </DataState>
    </div>
  )
}

function MetaField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </dt>
      <dd>{children}</dd>
    </div>
  )
}
