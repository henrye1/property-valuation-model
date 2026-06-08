import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { ResultPanel } from './ResultPanel'
import type { ValuationResult } from '@/schemas/valuation'

const minimalResult: ValuationResult = {
  engine_version: '0.2.0',
  valuation_date: '2025-06-01',
  tenants_resolved: [
    {
      description: 'Shop 1',
      rentable_area_m2: '100',
      effective_rent_per_m2_pm: '150',
      monthly_rent: '15000',
      escalation_cycles_applied: 1,
    },
  ],
  gross_monthly_rent_tenants: '15000',
  gross_monthly_rent_parking: '0',
  gross_monthly_income: '15000',
  gross_annual_income: '180000',
  annual_operating_expenses: '60000',
  opex_per_m2_pm: '50',
  opex_pct_of_gai: '0.3333',
  vacancy_allowance_amount: '9000',
  annual_net_income: '111000',
  capitalised_value: '965217',
  market_value: '960000',
  warnings: [],
}

const resultWithWarnings: ValuationResult = {
  ...minimalResult,
  warnings: [
    { code: 'SHORT_LEASE', message: 'Lease expires within 12 months', field_path: 'tenants[0]' },
  ],
}

describe('ResultPanel', () => {
  it('renders the market value', () => {
    render(<ResultPanel result={minimalResult} />)
    expect(screen.getByText('Market value')).toBeInTheDocument()
    // The formatted value R 960 000.00 should appear somewhere
    expect(screen.getByText(/960/)).toBeInTheDocument()
  })

  it('renders resolved tenants table', () => {
    render(<ResultPanel result={minimalResult} />)
    expect(screen.getByText('Shop 1')).toBeInTheDocument()
    expect(screen.getByText('Resolved tenants')).toBeInTheDocument()
  })

  it('omits warnings section when no warnings', () => {
    render(<ResultPanel result={minimalResult} />)
    expect(screen.queryByText('Warnings')).not.toBeInTheDocument()
  })

  it('renders warning chips when warnings are present', () => {
    render(<ResultPanel result={resultWithWarnings} />)
    expect(screen.getByText('Warnings')).toBeInTheDocument()
    expect(screen.getByText('SHORT_LEASE')).toBeInTheDocument()
  })
})
