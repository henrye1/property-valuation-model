/**
 * formToValuationInput — pure helper
 *
 * Converts the RHF Valuation Editor form values into the ValuationInput wire
 * format accepted by /calculate and POST /snapshots.
 *
 * Rules:
 *  - String fields that are "" (or whitespace-only) become null for nullable
 *    optional fields (tenant_name, next_escalation_date, lease_period_text,
 *    lease_expiry_date).
 *  - Decimal fields (rentable_area_m2, rent_per_m2_pm, etc.) stay as strings —
 *    the ValuationInputSchema expects string-encoded decimals.
 *  - parking.bays is already a number (registered with valueAsNumber: true).
 *
 * Returns `unknown` so the caller can run ValuationInputSchema.safeParse /
 * .parse on the result; narrowing happens at call sites.
 */
import type { ValuationFormValues, TenantFormLine, ParkingFormLine } from '@/components/valuation/valuation-form-types'

const emptyToNull = (s: string): string | null => (s.trim() === '' ? null : s)

export function formToValuationInput(values: ValuationFormValues): unknown {
  const tenants = values.tenants.map((t: TenantFormLine) => ({
    description: t.description,
    tenant_name: emptyToNull(t.tenant_name),
    rentable_area_m2: t.rentable_area_m2,
    rent_per_m2_pm: t.rent_per_m2_pm,
    annual_escalation_pct: t.annual_escalation_pct,
    next_escalation_date: emptyToNull(t.next_escalation_date),
    lease_period_text: emptyToNull(t.lease_period_text),
    lease_expiry_date: emptyToNull(t.lease_expiry_date),
  }))

  const parking = values.parking.map((p: ParkingFormLine) => ({
    bay_type: p.bay_type,
    bays: p.bays,
    rate_per_bay_pm: p.rate_per_bay_pm,
  }))

  return {
    valuation_date: values.valuation_date,
    tenants,
    parking,
    monthly_operating_expenses: values.monthly_operating_expenses,
    vacancy_allowance_pct: values.vacancy_allowance_pct,
    cap_rate: values.cap_rate,
    rounding: values.rounding,
  }
}
