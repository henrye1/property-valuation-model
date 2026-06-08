import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { ValuationInput } from '@/schemas/valuation'

// ---------------------------------------------------------------------------
// Mock @/lib/auth so we don't need a real AuthProvider / Supabase in tests.
// We expose a mutable fakeApi object so individual tests can customise the spy.
// ---------------------------------------------------------------------------

const fakeApi = {
  post: vi.fn().mockResolvedValue({
    engine_version: '0.2.0',
    valuation_date: '2025-06-01',
    tenants_resolved: [],
    gross_monthly_rent_tenants: '0',
    gross_monthly_rent_parking: '0',
    gross_monthly_income: '0',
    gross_annual_income: '0',
    annual_operating_expenses: '0',
    opex_per_m2_pm: '0',
    opex_pct_of_gai: '0',
    vacancy_allowance_amount: '0',
    annual_net_income: '0',
    capitalised_value: '0',
    market_value: '0',
    warnings: [],
  }),
}

vi.mock('@/lib/auth', () => ({
  useAuth: () => ({ api: fakeApi }),
}))

// Also mock supabase to prevent module-level init errors
vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn().mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } }),
    },
  },
}))

// Import AFTER mocks are registered
import { useCalculate } from './useCalculate'

// ---------------------------------------------------------------------------
// A valid ValuationInput that passes ValuationInputSchema.safeParse
// ---------------------------------------------------------------------------
const validInput: ValuationInput = {
  valuation_date: '2025-06-01',
  tenants: [
    {
      description: 'Shop 1',
      tenant_name: 'ACME',
      rentable_area_m2: '100',
      rent_per_m2_pm: '150',
      annual_escalation_pct: '0.08',
      next_escalation_date: '2025-01-01',
      lease_period_text: null,
      lease_expiry_date: null,
    },
  ],
  parking: [],
  monthly_operating_expenses: '5000',
  vacancy_allowance_pct: '0.05',
  cap_rate: '0.115',
  rounding: 'nearest_10000',
}

// ---------------------------------------------------------------------------
// Wrapper: fresh QueryClient per test (no shared cache bleed)
// ---------------------------------------------------------------------------
function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        // Disable stale-time so queries always re-run in tests
        staleTime: 0,
        gcTime: 0,
      },
    },
  })
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  Wrapper.displayName = 'TestQueryProvider'
  return Wrapper
}

// ---------------------------------------------------------------------------
describe('useCalculate', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    fakeApi.post.mockClear()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  // -------------------------------------------------------------------------
  it('calls /calculate exactly once after 300ms debounce for valid input', async () => {
    const { result } = renderHook(() => useCalculate(validInput), {
      wrapper: makeWrapper(),
    })

    // Not called yet — debounce pending
    expect(fakeApi.post).not.toHaveBeenCalled()
    expect(result.current.isCalculating).toBe(false)

    // Advance past the debounce window
    await act(async () => {
      await vi.runAllTimersAsync()
    })

    // Flush all pending promise microtasks
    await act(async () => {
      await Promise.resolve()
    })

    expect(fakeApi.post).toHaveBeenCalledTimes(1)
    expect(fakeApi.post).toHaveBeenCalledWith('/calculate', validInput)
  })

  // -------------------------------------------------------------------------
  it('collapses rapid input changes into a single /calculate call', async () => {
    const input1 = { ...validInput, cap_rate: '0.10' }
    const input2 = { ...validInput, cap_rate: '0.11' }
    const input3 = { ...validInput, cap_rate: '0.12' }

    const { rerender } = renderHook(
      ({ inp }: { inp: ValuationInput }) => useCalculate(inp),
      { initialProps: { inp: input1 }, wrapper: makeWrapper() },
    )

    // Rapid changes within the debounce window
    act(() => { vi.advanceTimersByTime(100) })
    rerender({ inp: input2 })
    act(() => { vi.advanceTimersByTime(100) })
    rerender({ inp: input3 })
    act(() => { vi.advanceTimersByTime(100) })

    // Still no call — all within 300ms window
    expect(fakeApi.post).not.toHaveBeenCalled()

    // Now let the debounce fire
    await act(async () => {
      await vi.runAllTimersAsync()
    })
    await act(async () => {
      await Promise.resolve()
    })

    // Only one call with the final input
    expect(fakeApi.post).toHaveBeenCalledTimes(1)
    expect(fakeApi.post).toHaveBeenCalledWith('/calculate', input3)
  })

  // -------------------------------------------------------------------------
  it('does NOT call /calculate when input is invalid (empty tenants)', async () => {
    const invalidInput = { ...validInput, tenants: [] } // fails min(1) validation

    renderHook(() => useCalculate(invalidInput as unknown as Partial<ValuationInput>), {
      wrapper: makeWrapper(),
    })

    await act(async () => {
      await vi.runAllTimersAsync()
    })
    await act(async () => {
      await Promise.resolve()
    })

    expect(fakeApi.post).not.toHaveBeenCalled()
  })
})
