import type { ReactNode } from 'react'
import { useAuth, canWrite } from '@/lib/auth'

export function RoleGate({ children, fallback = null }: { children: ReactNode; fallback?: ReactNode }) {
  const { role } = useAuth()
  return canWrite(role) ? <>{children}</> : <>{fallback}</>
}
