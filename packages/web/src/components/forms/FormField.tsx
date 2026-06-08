import type { ReactNode } from 'react'
import { Label } from '@/components/ui/label'

interface FormFieldProps {
  label: string
  htmlFor?: string
  error?: string
  children: ReactNode
  required?: boolean
}

export function FormField({ label, htmlFor, error, children, required }: FormFieldProps) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor}>
        {label}
        {required && <span className="ml-0.5 text-destructive">*</span>}
      </Label>
      {children}
      {error && <p className="text-destructive text-sm">{error}</p>}
    </div>
  )
}
