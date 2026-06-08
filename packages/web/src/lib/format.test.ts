import { describe, it, expect } from 'vitest'
import { formatZar, formatPct, formatDate } from './format'
describe('format', () => {
  it('formats a decimal string as ZAR', () => expect(formatZar('1234567.5')).toBe('R 1 234 567.50'))
  it('handles null', () => expect(formatZar(null)).toBe('—'))
  it('formats a fraction as percent', () => expect(formatPct('0.115')).toBe('11.50%'))
  it('formats an ISO date', () => expect(formatDate('2025-06-01')).toBe('01 Jun 2025'))
})
