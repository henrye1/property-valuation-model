/**
 * Shared form shape for the Valuation Editor.
 *
 * All decimal fields are stored as strings inside the form (matching the API's
 * wire format). Nullable text fields use empty string "" in the form and are
 * converted to null when building the ValuationInput for /calculate or save.
 *
 * parking.bays is an integer number (the only numeric field).
 */
import type { BayType, Rounding } from '@/schemas/valuation'

export interface TenantFormLine {
  description: string
  tenant_name: string          // "" → null on output
  rentable_area_m2: string
  rent_per_m2_pm: string
  annual_escalation_pct: string
  next_escalation_date: string // "" → null on output; date input stores ISO string
  lease_period_text: string    // "" → null on output
  lease_expiry_date: string    // "" → null on output; date input stores ISO string
}

export interface ParkingFormLine {
  bay_type: BayType
  bays: number        // integer — the only genuine number field
  rate_per_bay_pm: string
}

export interface ValuationFormValues {
  valuation_date: string
  tenants: TenantFormLine[]
  parking: ParkingFormLine[]
  monthly_operating_expenses: string
  vacancy_allowance_pct: string
  cap_rate: string
  rounding: Rounding
}

export const EMPTY_TENANT: TenantFormLine = {
  description: '',
  tenant_name: '',
  rentable_area_m2: '',
  rent_per_m2_pm: '',
  annual_escalation_pct: '0',
  next_escalation_date: '',
  lease_period_text: '',
  lease_expiry_date: '',
}

export const EMPTY_PARKING: ParkingFormLine = {
  bay_type: 'open',
  bays: 1,
  rate_per_bay_pm: '',
}
