import { describe, it, expect, vi, beforeEach } from 'vitest'
import { triggerDownload } from './download'

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:mock')
  URL.revokeObjectURL = vi.fn()
})

describe('triggerDownload', () => {
  it('creates an object URL, clicks an anchor with the filename, and revokes', () => {
    const clickSpy = vi.fn()
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = realCreate(tag) as HTMLElement
      if (tag === 'a') el.click = clickSpy
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return el as any
    })
    const blob = new Blob(['x'], { type: 'application/pdf' })
    triggerDownload(blob, 'report.pdf')
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob)
    expect(clickSpy).toHaveBeenCalledOnce()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock')
  })
})
