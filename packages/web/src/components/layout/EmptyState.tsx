import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-3 py-12 text-center', className)}>
      <p className="text-base font-medium text-muted-foreground">{title}</p>
      {description && (
        <p className="text-sm text-muted-foreground/70">{description}</p>
      )}
      {action}
    </div>
  )
}
