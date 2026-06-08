import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface PageHeaderProps {
  title: string
  action?: ReactNode
  className?: string
}

export function PageHeader({ title, action, className }: PageHeaderProps) {
  return (
    <div className={cn('flex items-center justify-between', className)}>
      <h1 className="text-2xl font-semibold">{title}</h1>
      {action}
    </div>
  )
}
