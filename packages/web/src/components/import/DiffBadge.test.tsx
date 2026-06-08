import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DiffBadge } from './DiffBadge'

describe('DiffBadge', () => {
  it('renders an em dash for null', () => {
    render(<DiffBadge diffPct={null} />)
    expect(screen.getByText('—')).toBeTruthy()
  })
  it('treats |diff| <= 0.001 as ok', () => {
    const { container } = render(<DiffBadge diffPct="0.0005" />)
    // ok variant — assert via a data attribute or class your component sets
    expect(container.querySelector('[data-diff="ok"]')).not.toBeNull()
  })
  it('treats |diff| > 0.001 as mismatch', () => {
    const { container } = render(<DiffBadge diffPct="0.02" />)
    expect(container.querySelector('[data-diff="mismatch"]')).not.toBeNull()
  })
  it('treats negative diff by magnitude', () => {
    const { container } = render(<DiffBadge diffPct="-0.02" />)
    expect(container.querySelector('[data-diff="mismatch"]')).not.toBeNull()
  })
})
