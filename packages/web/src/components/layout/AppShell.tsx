import { Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { Sidebar } from './Sidebar'
import { ErrorBoundary } from './ErrorBoundary'

export function AppShell() {
  const { user, signOut } = useAuth()
  const location = useLocation()

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-12 items-center justify-between border-b border-border bg-card px-4">
          <span className="text-sm font-medium text-foreground">
            Property Valuations
          </span>
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">
              {user?.display_name ?? user?.email ?? ''}
            </span>
            <Button variant="outline" size="sm" onClick={() => void signOut()}>
              Sign out
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-6">
          <ErrorBoundary key={location.pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
