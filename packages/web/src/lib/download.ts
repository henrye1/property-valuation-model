import { ApiError } from './api'
import type { ApiClient } from './api'

export function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export async function downloadFromApi(api: ApiClient, path: string): Promise<void> {
  const { blob, filename } = await api.getBlob(path)
  triggerDownload(blob, filename)
}

/**
 * Wrapper around downloadFromApi that shows a toast on failure.
 * Requires the caller to pass `toast.error` (from 'sonner') to avoid a hard
 * dependency on sonner inside this lib module.
 */
export async function downloadOrToast(
  api: ApiClient,
  path: string,
  onError: (message: string) => void,
): Promise<void> {
  try {
    await downloadFromApi(api, path)
  } catch (e) {
    onError(e instanceof ApiError ? e.message : 'Download failed.')
  }
}
