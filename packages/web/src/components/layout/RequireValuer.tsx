import { Navigate, Outlet } from 'react-router-dom'
import { useAuth, canWrite } from '@/lib/auth'

export function RequireValuer() {
  const { role, loading } = useAuth()
  if (loading) return <div className="p-8 text-muted-foreground">Loading…</div>
  if (!canWrite(role)) return <Navigate to="/" replace />
  return <Outlet />
}
