import { useRef, useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

const XLSX_ACCEPT = '.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

function isXlsx(file: File): boolean {
  return (
    file.name.toLowerCase().endsWith('.xlsx') ||
    file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  )
}

interface UploadDropzoneProps {
  onFiles: (files: File[]) => void
  disabled?: boolean
}

export function UploadDropzone({ onFiles, disabled = false }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFiles = useCallback(
    (raw: FileList | null) => {
      if (!raw) return
      const filtered = Array.from(raw).filter(isXlsx)
      if (filtered.length > 0) {
        onFiles(filtered)
      }
    },
    [onFiles],
  )

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled) setDragOver(true)
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
    if (disabled) return
    handleFiles(e.dataTransfer.files)
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    handleFiles(e.target.files)
    // Reset value so the same file can be re-selected
    e.target.value = ''
  }

  return (
    <div
      role="region"
      aria-label="File upload dropzone"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed py-12 text-center transition-colors',
        dragOver && !disabled
          ? 'border-primary bg-primary/5'
          : 'border-border bg-muted/30',
        disabled && 'cursor-not-allowed opacity-50',
      )}
    >
      <p className="text-sm font-medium text-muted-foreground">
        Drag and drop <span className="font-semibold">.xlsx</span> files here
      </p>
      <p className="text-xs text-muted-foreground/70">or</p>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
      >
        Choose files
      </Button>
      <input
        ref={inputRef}
        type="file"
        accept={XLSX_ACCEPT}
        multiple
        className="sr-only"
        tabIndex={-1}
        disabled={disabled}
        onChange={handleInputChange}
      />
    </div>
  )
}
