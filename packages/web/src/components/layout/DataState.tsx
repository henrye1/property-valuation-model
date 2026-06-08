import type { ReactNode } from 'react'
import { ApiError } from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'

interface DataStateProps {
  isPending: boolean
  error: unknown
  children: ReactNode
  skeleton?: ReactNode
}

const defaultSkeleton = (
  <div className="space-y-2">
    <Skeleton className="h-6 w-full" />
    <Skeleton className="h-6 w-5/6" />
    <Skeleton className="h-6 w-4/6" />
    <Skeleton className="h-6 w-full" />
    <Skeleton className="h-6 w-3/6" />
  </div>
)

export function DataState({ isPending, error, children, skeleton }: DataStateProps) {
  if (isPending) {
    return <>{skeleton ?? defaultSkeleton}</>
  }

  if (error) {
    const message = error instanceof ApiError ? error.message : 'Something went wrong.'
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
        {message}
      </div>
    )
  }

  return <>{children}</>
}
