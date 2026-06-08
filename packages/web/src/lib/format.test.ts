import { describe, it, expect } from 'vitest'
import { formatZar, formatPct, formatDate, formatDateTime } from './format'
describe('format', () => {
  it('formats a decimal string as ZAR', () => expect(formatZar('1234567.5')).toBe('R 1 234 567.50'))
  it('handles null', () => expect(formatZar(null)).toBe('—'))
  it('formats a fraction as percent', () => expect(formatPct('0.115')).toBe('11.50%'))
  it('formats an ISO date', () => expect(formatDate('2025-06-01')).toBe('01 Jun 2025'))
  it('formatDateTime: formats a valid ISO datetime in UTC', () =>
    expect(formatDateTime('2025-06-01T10:30:00.000Z')).toBe('01 Jun 2025 10:30'))
  it('formatDateTime: returns — for null', () => expect(formatDateTime(null)).toBe('—'))
  it('formatDateTime: returns — for undefined', () => expect(formatDateTime(undefined)).toBe('—'))
})
