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
