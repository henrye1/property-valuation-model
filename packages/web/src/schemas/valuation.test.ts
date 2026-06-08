import { describe, it, expect } from 'vitest'
import { ValuationInputSchema, ValuationResultSchema } from './valuation'

const input = {
  valuation_date: '2025-06-01',
  tenants: [{ description: 'Shop 1', tenant_name: 'ACME', rentable_area_m2: '100', rent_per_m2_pm: '150',
    annual_escalation_pct: '0.08', next_escalation_date: '2025-01-01', lease_period_text: null, lease_expiry_date: null }],
  parking: [], monthly_operating_expenses: '5000', vacancy_allowance_pct: '0.05',
  cap_rate: '0.115', rounding: 'nearest_10000',
}

describe('valuation schemas', () => {
  it('accepts a valid ValuationInput with decimals as strings', () => {
    expect(() => ValuationInputSchema.parse(input)).not.toThrow()
  })
  it('rejects missing tenants', () => {
    expect(() => ValuationInputSchema.parse({ ...input, tenants: undefined })).toThrow()
  })
  it('parses a ValuationResult', () => {
    const r = { engine_version: '0.2.0', valuation_date: '2025-06-01', tenants_resolved: [],
      gross_monthly_rent_tenants: '0', gross_monthly_rent_parking: '0', gross_monthly_income: '0',
      gross_annual_income: '0', annual_operating_expenses: '0', opex_per_m2_pm: '0', opex_pct_of_gai: '0',
      vacancy_allowance_amount: '0', annual_net_income: '0', capitalised_value: '0', market_value: '0', warnings: [] }
    expect(() => ValuationResultSchema.parse(r)).not.toThrow()
  })
})
