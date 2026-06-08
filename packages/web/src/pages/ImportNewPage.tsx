import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { UploadDropzone } from '@/components/import/UploadDropzone'
import { Button } from '@/components/ui/button'
import { useUploadImport } from '@/hooks/useImports'

export default function ImportNewPage() {
  const navigate = useNavigate()
  const { mutateAsync, isPending: isUploading } = useUploadImport()
  const [files, setFiles] = useState<File[]>([])

  function addFiles(incoming: File[]) {
    setFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name))
      const deduped = incoming.filter((f) => !existingNames.has(f.name))
      return [...prev, ...deduped]
    })
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleUpload() {
    if (files.length === 0 || isUploading) return
    const result = await mutateAsync(files)
    void navigate(`/imports/${result.batch_id}`)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="New import"
        action={
          <Button variant="outline" size="sm" render={<Link to="/imports" />}>
            Cancel
          </Button>
        }
      />

      <UploadDropzone onFiles={addFiles} disabled={isUploading} />

      {files.length > 0 && (
        <ul className="space-y-1 text-sm">
          {files.map((file, i) => (
            <li
              key={`${file.name}-${i}`}
              className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2"
            >
              <span className="truncate text-muted-foreground">{file.name}</span>
              <button
                type="button"
                disabled={isUploading}
                onClick={() => removeFile(i)}
                className="ml-4 shrink-0 text-xs text-destructive hover:underline disabled:opacity-50"
                aria-label={`Remove ${file.name}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex gap-3">
        <Button
          type="button"
          disabled={files.length === 0 || isUploading}
          onClick={() => void handleUpload()}
        >
          {isUploading
            ? 'Uploading…'
            : files.length === 0
              ? 'Upload files'
              : `Upload ${files.length} file${files.length === 1 ? '' : 's'}`}
        </Button>
        <Button variant="outline" render={<Link to="/imports" />} disabled={isUploading}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
