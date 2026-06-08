export function formatZar(value: string | null | undefined): string {
  if (value == null) return '—'
  const num = parseFloat(value)
  // Format with en-ZA to get grouping, then normalise separators.
  // en-ZA may produce a non-breaking space (U+00A0) or comma as the thousands
  // separator depending on the ICU build.  We replace anything that is not a
  // digit, a period, or the leading minus sign with a plain ASCII space, then
  // fix up the decimal marker if it came out as a comma.
  const raw = new Intl.NumberFormat('en-ZA', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num)
  // Step 1: replace non-breaking space (U+00A0) with plain space.
  // Use the Unicode escape in the regex to avoid literal irregular-whitespace.
  const step1 = raw.replace(new RegExp('\u00a0', 'g'), ' ')
  // Step 2: comma-as-thousands-sep (lookahead: followed by exactly 3 digits).
  const step2 = step1.replace(/,(?=\d{3})/g, ' ')
  // Step 3: if decimal is still a comma (e.g. "1 234 567,50"), swap to ".".
  const normalised = step2.replace(/,(\d{2})$/, '.$1')
  return `R ${normalised}`
}

export function formatPct(value: string | null | undefined): string {
  if (value == null) return '—'
  const num = parseFloat(value) * 100
  return `${num.toFixed(2)}%`
}

export function formatDate(value: string | null | undefined): string {
  if (value == null) return '—'
  const [y, m, d] = value.split('-').map(Number)
  const date = new Date(Date.UTC(y, m - 1, d))
  const formatted = new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date)
  // en-GB may produce "01 Jun 2025" already; strip any commas just in case.
  return formatted.replace(/,/g, '')
}
