import { describe, it, expect } from 'vitest'
import { formToValuationInput } from './formToValuationInput'
import { ValuationInputSchema } from '@/schemas/valuation'
import type { ValuationFormValues } from '@/components/valuation/valuation-form-types'

const BASE: ValuationFormValues = {
  valuation_date: '2025-06-01',
  tenants: [
    {
      description: 'Shop 1',
      tenant_name: 'ACME',
      rentable_area_m2: '100',
      rent_per_m2_pm: '150',
      annual_escalation_pct: '0.08',
      next_escalation_date: '2026-01-01',
      lease_period_text: '3 years',
      lease_expiry_date: '2028-01-01',
    },
  ],
  parking: [
    {
      bay_type: 'open',
      bays: 10,
      rate_per_bay_pm: '800',
    },
  ],
  monthly_operating_expenses: '50000',
  vacancy_allowance_pct: '0.05',
  cap_rate: '0.115',
  rounding: 'nearest_10000',
}

describe('formToValuationInput', () => {
  it('passes through strings for decimal fields unchanged', () => {
    const result = formToValuationInput(BASE) as Record<string, unknown>
    expect(result['cap_rate']).toBe('0.115')
    expect(result['vacancy_allowance_pct']).toBe('0.05')
    expect(result['monthly_operating_expenses']).toBe('50000')
  })

  it('converts empty string tenant_name to null', () => {
    const values: ValuationFormValues = {
      ...BASE,
      tenants: [{ ...BASE.tenants[0], tenant_name: '' }],
    }
    const result = formToValuationInput(values) as { tenants: Array<Record<string, unknown>> }
    expect(result.tenants[0]['tenant_name']).toBeNull()
  })

  it('converts whitespace-only tenant_name to null', () => {
    const values: ValuationFormValues = {
      ...BASE,
      tenants: [{ ...BASE.tenants[0], tenant_name: '   ' }],
    }
    const result = formToValuationInput(values) as { tenants: Array<Record<string, unknown>> }
    expect(result.tenants[0]['tenant_name']).toBeNull()
  })

  it('converts empty string next_escalation_date to null', () => {
    const values: ValuationFormValues = {
      ...BASE,
      tenants: [{ ...BASE.tenants[0], next_escalation_date: '' }],
    }
    const result = formToValuationInput(values) as { tenants: Array<Record<string, unknown>> }
    expect(result.tenants[0]['next_escalation_date']).toBeNull()
  })

  it('converts empty string lease_period_text to null', () => {
    const values: ValuationFormValues = {
      ...BASE,
      tenants: [{ ...BASE.tenants[0], lease_period_text: '' }],
    }
    const result = formToValuationInput(values) as { tenants: Array<Record<string, unknown>> }
    expect(result.tenants[0]['lease_period_text']).toBeNull()
  })

  it('converts empty string lease_expiry_date to null', () => {
    const values: ValuationFormValues = {
      ...BASE,
      tenants: [{ ...BASE.tenants[0], lease_expiry_date: '' }],
    }
    const result = formToValuationInput(values) as { tenants: Array<Record<string, unknown>> }
    expect(result.tenants[0]['lease_expiry_date']).toBeNull()
  })

  it('preserves non-empty optional strings as strings', () => {
    const result = formToValuationInput(BASE) as { tenants: Array<Record<string, unknown>> }
    expect(result.tenants[0]['tenant_name']).toBe('ACME')
    expect(result.tenants[0]['lease_period_text']).toBe('3 years')
  })

  it('keeps parking bays as a number', () => {
    const result = formToValuationInput(BASE) as { parking: Array<Record<string, unknown>> }
    expect(result.parking[0]['bays']).toBe(10)
    expect(typeof result.parking[0]['bays']).toBe('number')
  })

  it('keeps parking rate_per_bay_pm as string', () => {
    const result = formToValuationInput(BASE) as { parking: Array<Record<string, unknown>> }
    expect(result.parking[0]['rate_per_bay_pm']).toBe('800')
  })

  it('handles empty parking array', () => {
    const values: ValuationFormValues = { ...BASE, parking: [] }
    const result = formToValuationInput(values) as { parking: unknown[] }
    expect(result.parking).toEqual([])
  })

  it('produces an object that passes ValuationInputSchema', () => {
    const result = formToValuationInput(BASE)
    expect(() => ValuationInputSchema.parse(result)).not.toThrow()
  })
})
