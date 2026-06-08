import { useAuth } from '@/lib/auth'

export default function DashboardPage() {
  const { user, role } = useAuth()

  return (
    <div>
      <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Signed in as {user?.email} ({role})
      </p>
    </div>
  )
}
