import { describe, it, expect, vi } from 'vitest'
import { createApiClient, ApiError } from './api'

const mkClient = (fetchImpl: typeof fetch) =>
  createApiClient({ baseUrl: 'http://api.test', getToken: async () => 'tok', fetchImpl })

describe('api client', () => {
  it('attaches the bearer token and parses JSON', async () => {
    const fetchImpl = vi.fn(async (_url, init) => {
      expect((init!.headers as Record<string,string>).Authorization).toBe('Bearer tok')
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } })
    }) as unknown as typeof fetch
    const api = mkClient(fetchImpl)
    await expect(api.get('/me')).resolves.toEqual({ ok: true })
  })

  it('unwraps the error envelope into ApiError', async () => {
    const body = { error: { code: 'forbidden', message: 'Not permitted', details: {} } }
    const fetchImpl = (async () => new Response(JSON.stringify(body), { status: 403, headers: { 'content-type': 'application/json' } })) as unknown as typeof fetch
    const api = mkClient(fetchImpl)
    await expect(api.get('/entities')).rejects.toMatchObject({ code: 'forbidden', status: 403, message: 'Not permitted' })
  })

  it('calls onUnauthorized on 401', async () => {
    const onUnauthorized = vi.fn()
    const fetchImpl = (async () => new Response('{}', { status: 401, headers: { 'content-type': 'application/json' } })) as unknown as typeof fetch
    const api = createApiClient({ baseUrl: 'http://api.test', getToken: async () => null, fetchImpl, onUnauthorized })
    await expect(api.get('/me')).rejects.toBeInstanceOf(ApiError)
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })
})
