import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/lib/auth'

export function RequireAuth() {
  const { session, loading } = useAuth()
  if (loading) return <div className="p-8 text-muted-foreground">Loading…</div>
  if (!session) return <Navigate to="/login" replace />
  return <Outlet />
}
