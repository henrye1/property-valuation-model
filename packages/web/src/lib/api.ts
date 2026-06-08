export class ApiError extends Error {
  code: string
  status: number
  details: unknown

  constructor(code: string, message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

interface ApiConfig {
  baseUrl: string
  getToken: () => Promise<string | null>
  fetchImpl?: typeof fetch
  onUnauthorized?: () => void
}

export interface ApiClient {
  get: <T = unknown>(path: string) => Promise<T>
  post: <T = unknown>(path: string, body?: unknown) => Promise<T>
  patch: <T = unknown>(path: string, body?: unknown) => Promise<T>
  del: <T = unknown>(path: string) => Promise<T>
  postForm: <T = unknown>(path: string, form: FormData) => Promise<T>
  getBlob: (path: string) => Promise<{ blob: Blob; filename: string }>
}

export function createApiClient(cfg: ApiConfig): ApiClient {
  const doFetch = cfg.fetchImpl ?? fetch

  async function request(path: string, init: RequestInit = {}): Promise<Response> {
    const token = await cfg.getToken()

    // Build headers as a plain object so tests can access .Authorization directly
    const baseHeaders: Record<string, string> = {}
    if (!(init.body instanceof FormData)) {
      baseHeaders['content-type'] = 'application/json'
    }
    if (token) {
      baseHeaders['Authorization'] = `Bearer ${token}`
    }

    // Merge any existing headers from init (also as plain object)
    const existingHeaders: Record<string, string> =
      init.headers instanceof Headers
        ? Object.fromEntries((init.headers as Headers).entries())
        : (init.headers as Record<string, string>) ?? {}

    const headers: Record<string, string> = { ...existingHeaders, ...baseHeaders }

    const res = await doFetch(`${cfg.baseUrl}${path}`, { ...init, headers })

    if (!res.ok) {
      if (res.status === 401) {
        cfg.onUnauthorized?.()
      }

      let code = 'error'
      let message = res.statusText
      let details: unknown = undefined

      try {
        const payload = await res.json() as { error?: { code?: string; message?: string; details?: unknown } }
        if (payload?.error) {
          code = payload.error.code ?? code
          message = payload.error.message ?? message
          details = payload.error.details
        }
      } catch {
        // leave defaults
      }

      throw new ApiError(code, message, res.status, details)
    }

    return res
  }

  async function json<T>(path: string, init: RequestInit = {}): Promise<T> {
    const res = await request(path, init)
    if (res.status === 204) return undefined as T
    return res.json() as Promise<T>
  }

  return {
    get<T = unknown>(path: string): Promise<T> {
      return json<T>(path, { method: 'GET' })
    },

    post<T = unknown>(path: string, body?: unknown): Promise<T> {
      return json<T>(path, {
        method: 'POST',
        body: body !== undefined ? JSON.stringify(body) : undefined,
      })
    },

    patch<T = unknown>(path: string, body?: unknown): Promise<T> {
      return json<T>(path, {
        method: 'PATCH',
        body: body !== undefined ? JSON.stringify(body) : undefined,
      })
    },

    del<T = unknown>(path: string): Promise<T> {
      return json<T>(path, { method: 'DELETE' })
    },

    async postForm<T = unknown>(path: string, form: FormData): Promise<T> {
      // Do NOT set content-type manually — browser must set multipart boundary
      return json<T>(path, { method: 'POST', body: form })
    },

    async getBlob(path: string): Promise<{ blob: Blob; filename: string }> {
      const res = await request(path, { method: 'GET' })
      const disposition = res.headers.get('content-disposition') ?? ''
      const match = disposition.match(/filename="?([^"]+)"?/)
      const filename = match?.[1] ?? 'download'
      const blob = await res.blob()
      return { blob, filename }
    },
  }
}
