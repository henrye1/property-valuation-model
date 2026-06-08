/**
 * TenantRow — a single row in the tenants useFieldArray.
 *
 * Defined at module top-level (NOT as a nested closure) so it never remounts
 * during parent re-renders triggered by watch(), which would cause input-focus loss.
 *
 * All decimal fields are plain text inputs (inputMode="decimal"). The form stores
 * them as strings; the page's formToValuationInput() handles conversion.
 */
import type { UseFormRegister, FieldErrors } from 'react-hook-form'
import { Trash2 } from 'lucide-react'
import { FormField } from '@/components/forms/FormField'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import type { Warning } from '@/schemas/valuation'
import { WarningChip } from './WarningChip'
import type { ValuationFormValues } from './valuation-form-types'

interface TenantRowProps {
  index: number
  register: UseFormRegister<ValuationFormValues>
  errors: FieldErrors<ValuationFormValues>
  remove: (index: number) => void
  /** Warnings from the live /calculate result whose field_path matches this tenant row */
  rowWarnings: Warning[]
  canRemove: boolean
}

/** Filter warnings whose field_path ends with `.{suffix}` */
function fieldWarnings(rowWarnings: Warning[], suffix: string): Warning[] {
  return rowWarnings.filter((w) => w.field_path?.endsWith(`.${suffix}`) ?? false)
}

export function TenantRow({
  index,
  register,
  errors,
  remove,
  rowWarnings,
  canRemove,
}: TenantRowProps) {
  const prefix = `tenants.${index}` as const
  const tenantErrors = errors.tenants?.[index]

  const escalationWarnings = fieldWarnings(rowWarnings, 'next_escalation_date')
  const rentWarnings = fieldWarnings(rowWarnings, 'rent_per_m2_pm')
  const expiryWarnings = fieldWarnings(rowWarnings, 'lease_expiry_date')

  return (
    <div className="rounded-lg border border-border p-4 space-y-4">
      {/* Row header */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-muted-foreground">Tenant {index + 1}</span>
        {canRemove && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => remove(index)}
            aria-label={`Remove tenant ${index + 1}`}
          >
            <Trash2 className="size-4" />
          </Button>
        )}
      </div>

      {/* Row 1: description + tenant_name */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <FormField
          label="Description"
          htmlFor={`${prefix}-description`}
          error={tenantErrors?.description?.message}
          required
        >
          <Input
            id={`${prefix}-description`}
            placeholder="e.g. Shop 1"
            {...register(`${prefix}.description`)}
            aria-invalid={!!tenantErrors?.description}
          />
        </FormField>

        <FormField
          label="Tenant name"
          htmlFor={`${prefix}-tenant_name`}
          error={tenantErrors?.tenant_name?.message}
        >
          <Input
            id={`${prefix}-tenant_name`}
            placeholder="Optional"
            {...register(`${prefix}.tenant_name`)}
          />
        </FormField>
      </div>

      {/* Row 2: area + rent */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <FormField
          label="Rentable area (m²)"
          htmlFor={`${prefix}-rentable_area_m2`}
          error={tenantErrors?.rentable_area_m2?.message}
          required
        >
          <Input
            id={`${prefix}-rentable_area_m2`}
            inputMode="decimal"
            placeholder="e.g. 500"
            {...register(`${prefix}.rentable_area_m2`)}
            aria-invalid={!!tenantErrors?.rentable_area_m2}
          />
        </FormField>

        <FormField
          label="Rent (R/m²/pm)"
          htmlFor={`${prefix}-rent_per_m2_pm`}
          error={tenantErrors?.rent_per_m2_pm?.message}
          required
        >
          <div>
            <Input
              id={`${prefix}-rent_per_m2_pm`}
              inputMode="decimal"
              placeholder="e.g. 150"
              {...register(`${prefix}.rent_per_m2_pm`)}
              aria-invalid={!!tenantErrors?.rent_per_m2_pm}
            />
            {rentWarnings.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {rentWarnings.map((w, i) => <WarningChip key={i} warning={w} />)}
              </div>
            )}
          </div>
        </FormField>
      </div>

      {/* Row 3: escalation % + next escalation date */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <FormField
          label="Annual escalation (as decimal, e.g. 0.08)"
          htmlFor={`${prefix}-annual_escalation_pct`}
          error={tenantErrors?.annual_escalation_pct?.message}
          required
        >
          <Input
            id={`${prefix}-annual_escalation_pct`}
            inputMode="decimal"
            placeholder="e.g. 0.08"
            {...register(`${prefix}.annual_escalation_pct`)}
            aria-invalid={!!tenantErrors?.annual_escalation_pct}
          />
        </FormField>

        <FormField
          label="Next escalation date"
          htmlFor={`${prefix}-next_escalation_date`}
          error={tenantErrors?.next_escalation_date?.message}
        >
          <div>
            <Input
              id={`${prefix}-next_escalation_date`}
              type="date"
              {...register(`${prefix}.next_escalation_date`)}
            />
            {escalationWarnings.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {escalationWarnings.map((w, i) => <WarningChip key={i} warning={w} />)}
              </div>
            )}
          </div>
        </FormField>
      </div>

      {/* Row 4: lease period text + lease expiry date */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <FormField
          label="Lease period"
          htmlFor={`${prefix}-lease_period_text`}
          error={tenantErrors?.lease_period_text?.message}
        >
          <Input
            id={`${prefix}-lease_period_text`}
            placeholder="e.g. 3 years"
            {...register(`${prefix}.lease_period_text`)}
          />
        </FormField>

        <FormField
          label="Lease expiry date"
          htmlFor={`${prefix}-lease_expiry_date`}
          error={tenantErrors?.lease_expiry_date?.message}
        >
          <div>
            <Input
              id={`${prefix}-lease_expiry_date`}
              type="date"
              {...register(`${prefix}.lease_expiry_date`)}
            />
            {expiryWarnings.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {expiryWarnings.map((w, i) => <WarningChip key={i} warning={w} />)}
              </div>
            )}
          </div>
        </FormField>
      </div>
    </div>
  )
}
