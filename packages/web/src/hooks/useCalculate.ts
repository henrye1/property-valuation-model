import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/lib/auth'
import { ValuationInputSchema, ValuationResultSchema, type ValuationInput, type ValuationResult } from '@/schemas/valuation'

const DEBOUNCE_MS = 300

export interface UseCalculateResult {
  result: ValuationResult | undefined
  isCalculating: boolean
  error: unknown
}

/**
 * Debounced /calculate preview hook.
 *
 * Accepts a (possibly incomplete) ValuationInput, debounces 300ms, then POSTs
 * to /calculate if — and only if — the input passes ValuationInputSchema.safeParse.
 * Rapid changes within the 300ms window collapse to a single call.
 *
 * Implemented via useEffect + setTimeout for debounce, and useQuery for the
 * actual request (gives isFetching / caching / error handling for free).
 */
export function useCalculate(
  input: Partial<ValuationInput> | ValuationInput | null,
): UseCalculateResult {
  const { api } = useAuth()

  // Serialise input to detect changes by value
  const serialised = JSON.stringify(input ?? null)

  // Debounced serialised value — only updates 300ms after the last change
  const [debouncedSerialised, setDebouncedSerialised] = useState<string | null>(null)

  useEffect(() => {
    const id = setTimeout(() => {
      setDebouncedSerialised(serialised)
    }, DEBOUNCE_MS)
    return () => clearTimeout(id)
  }, [serialised])

  // Determine whether the debounced value is a valid, complete ValuationInput
  const parsed =
    debouncedSerialised !== null
      ? ValuationInputSchema.safeParse(JSON.parse(debouncedSerialised))
      : { success: false as const, error: null }

  const isEnabled = parsed.success

  const { data, isFetching, error } = useQuery({
    queryKey: ['calculate', debouncedSerialised],
    queryFn: async (): Promise<ValuationResult> => {
      const parsed = ValuationInputSchema.parse(JSON.parse(debouncedSerialised as string))
      return ValuationResultSchema.parse(await api.post('/calculate', parsed))
    },
    enabled: isEnabled,
    // No stale caching for preview — always re-fetch when the key changes
    staleTime: 0,
    // Don't auto-retry preview calls
    retry: false,
  })

  return {
    result: data,
    isCalculating: isFetching,
    error,
  }
}
