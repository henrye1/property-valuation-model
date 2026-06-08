/**
 * ValuationEditorPage — Task 20
 *
 * Three editable sections (Tenants / Parking / Assumptions) with:
 *  - Live /calculate preview (debounced, via useCalculate)
 *  - Inline WarningChips on matched fields (field_path format: tenants[i].field)
 *  - Save snapshot (validates with ValuationInputSchema, then useCreateSnapshot)
 *  - Prefill from location.state?.prefill (from "New valuation from this" button)
 *
 * ALL sub-components (TenantRow, ParkingRow, AssumptionsForm) are imported from
 * separate module-top-level files — they do NOT live as nested closures here.
 * This prevents remounting on every watch() re-render and preserves input focus.
 */
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom'
import { useForm, useFieldArray, useWatch } from 'react-hook-form'
import { toast } from 'sonner'
import { PageHeader } from '@/components/layout/PageHeader'
import { DataState } from '@/components/layout/DataState'
import { ResultPanel } from '@/components/valuation/ResultPanel'
import { TenantRow } from '@/components/valuation/TenantRow'
import { ParkingRow } from '@/components/valuation/ParkingRow'
import { AssumptionsForm } from '@/components/valuation/AssumptionsForm'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useProperty } from '@/hooks/useProperties'
import { useCalculate } from '@/hooks/useCalculate'
import { useCreateSnapshot } from '@/hooks/useSnapshotMutations'
import { ValuationInputSchema, type ValuationInput, type Warning } from '@/schemas/valuation'
import {
  EMPTY_TENANT,
  EMPTY_PARKING,
  type ValuationFormValues,
} from '@/components/valuation/valuation-form-types'
import { formToValuationInput } from '@/lib/formToValuationInput'

// ---------------------------------------------------------------------------
// prefillToFormValues — map a ValuationInput (from location.state) → form defaults
// ---------------------------------------------------------------------------

function prefillToFormValues(prefill: ValuationInput): ValuationFormValues {
  const nullToEmpty = (s: string | null | undefined): string =>
    s == null ? '' : s

  return {
    valuation_date: prefill.valuation_date,
    tenants: prefill.tenants.map((t) => ({
      description: t.description,
      tenant_name: nullToEmpty(t.tenant_name),
      rentable_area_m2: t.rentable_area_m2,
      rent_per_m2_pm: t.rent_per_m2_pm,
      annual_escalation_pct: t.annual_escalation_pct,
      next_escalation_date: nullToEmpty(t.next_escalation_date),
      lease_period_text: nullToEmpty(t.lease_period_text),
      lease_expiry_date: nullToEmpty(t.lease_expiry_date),
    })),
    parking: prefill.parking.map((p) => ({
      bay_type: p.bay_type,
      bays: p.bays,
      rate_per_bay_pm: p.rate_per_bay_pm,
    })),
    monthly_operating_expenses: prefill.monthly_operating_expenses,
    vacancy_allowance_pct: prefill.vacancy_allowance_pct,
    cap_rate: prefill.cap_rate,
    rounding: prefill.rounding,
  }
}

// ---------------------------------------------------------------------------
// Helpers for inline warning mapping
// ---------------------------------------------------------------------------

/**
 * Filter warnings whose field_path begins with `tenants[{index}]`.
 * Engine format: `tenants[0].rent_per_m2_pm` (confirmed from warnings.py).
 */
function tenantRowWarnings(warnings: Warning[], index: number): Warning[] {
  const prefix = `tenants[${index}]`
  return warnings.filter((w) => w.field_path?.startsWith(prefix) ?? false)
}

// ---------------------------------------------------------------------------
// Empty defaults for a fresh form
// ---------------------------------------------------------------------------

const FRESH_DEFAULTS: ValuationFormValues = {
  valuation_date: '',
  tenants: [{ ...EMPTY_TENANT }],
  parking: [],
  monthly_operating_expenses: '',
  vacancy_allowance_pct: '',
  cap_rate: '',
  rounding: 'nearest_10000',
}

// ---------------------------------------------------------------------------
// ValuationEditorPage — the page component
// ---------------------------------------------------------------------------

export default function ValuationEditorPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const location = useLocation()

  // Prefill: if navigated from SnapshotViewerPage "New valuation from this"
  const prefill = (location.state as { prefill?: ValuationInput } | null)?.prefill

  const defaultValues: ValuationFormValues = prefill
    ? prefillToFormValues(prefill)
    : FRESH_DEFAULTS

  // Property query — for the page header
  const propertyQuery = useProperty(id)

  // RHF setup
  const {
    register,
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ValuationFormValues>({ defaultValues })

  // Field arrays
  const {
    fields: tenantFields,
    append: appendTenant,
    remove: removeTenant,
  } = useFieldArray({ control, name: 'tenants' })

  const {
    fields: parkingFields,
    append: appendParking,
    remove: removeParking,
  } = useFieldArray({ control, name: 'parking' })

  // Live preview: watch form values → build ValuationInput → pass to useCalculate
  const watchedValues = useWatch({ control })

  // Build the live input from watched values (may be partial during typing)
  const liveInput = formToValuationInput(watchedValues as ValuationFormValues)

  const { result, isCalculating } = useCalculate(
    liveInput as Partial<ValuationInput>,
  )

  // All warnings from the live result (for inline mapping and ResultPanel)
  const liveWarnings: Warning[] = result?.warnings ?? []

  // Save snapshot mutation
  const createSnapshot = useCreateSnapshot(id)

  async function onSubmit(values: ValuationFormValues) {
    const raw = formToValuationInput(values)
    let input: ValuationInput
    try {
      input = ValuationInputSchema.parse(raw)
    } catch {
      toast.error('Please fix validation errors before saving.')
      return
    }

    try {
      const snapshot = await createSnapshot.mutateAsync(input)
      void navigate(`/properties/${id}/valuations/${snapshot.id}`)
    } catch {
      // useCreateSnapshot already toasts the error
    }
  }

  const isSaveDisabled = isSubmitting || createSnapshot.isPending

  return (
    <div className="space-y-6">
      {/* Page header — uses property name once loaded */}
      <DataState
        isPending={propertyQuery.isPending}
        error={propertyQuery.error}
        skeleton={<div className="h-9 w-64 rounded bg-muted animate-pulse" />}
      >
        <PageHeader
          title={
            propertyQuery.data
              ? `New valuation — ${propertyQuery.data.name}`
              : 'New valuation'
          }
          action={
            <Button
              variant="outline"
              size="sm"
              render={<Link to={`/properties/${id}`} />}
            >
              Cancel
            </Button>
          }
        />
      </DataState>

      {/* Two-column layout: form (left) + live result (right) */}
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_420px]">
          {/* ----------------------------------------------------------------
              LEFT: form sections
          ---------------------------------------------------------------- */}
          <div className="space-y-6">
            {/* Assumptions section */}
            <AssumptionsForm
              register={register}
              control={control}
              errors={errors}
              warnings={liveWarnings}
            />

            {/* Tenants section */}
            <Card>
              <CardHeader>
                <CardTitle>Tenants</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {tenantFields.map((field, index) => (
                  <TenantRow
                    key={field.id}
                    index={index}
                    register={register}
                    errors={errors}
                    remove={removeTenant}
                    rowWarnings={tenantRowWarnings(liveWarnings, index)}
                    canRemove={tenantFields.length > 1}
                  />
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => appendTenant({ ...EMPTY_TENANT })}
                >
                  + Add tenant
                </Button>
              </CardContent>
            </Card>

            {/* Parking section */}
            <Card>
              <CardHeader>
                <CardTitle>Parking</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {parkingFields.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No parking rows added.</p>
                ) : (
                  parkingFields.map((field, index) => (
                    <ParkingRow
                      key={field.id}
                      index={index}
                      register={register}
                      control={control}
                      errors={errors}
                      remove={removeParking}
                    />
                  ))
                )}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => appendParking({ ...EMPTY_PARKING })}
                >
                  + Add parking
                </Button>
              </CardContent>
            </Card>

            {/* Save button */}
            <div className="flex justify-end">
              <Button type="submit" disabled={isSaveDisabled}>
                {isSubmitting || createSnapshot.isPending ? 'Saving…' : 'Save snapshot'}
              </Button>
            </div>
          </div>

          {/* ----------------------------------------------------------------
              RIGHT: live result rail
          ---------------------------------------------------------------- */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Live preview</h2>
            {isCalculating && (
              <p className="text-sm text-muted-foreground animate-pulse">Calculating…</p>
            )}
            {result ? (
              <ResultPanel result={result} />
            ) : (
              !isCalculating && (
                <p className="text-sm text-muted-foreground">
                  Fill in the form to see a live valuation.
                </p>
              )
            )}
          </div>
        </div>
      </form>
    </div>
  )
}
