import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/lib/auth'
import { supabase } from '@/lib/supabase'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

type Provider = 'google' | 'azure'

export default function LoginPage() {
  const { session, loading } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<null | Provider | 'password'>(null)

  if (loading) return <div className="p-8 text-muted-foreground">Loading…</div>
  if (session) return <Navigate to="/" replace />

  async function oauthSignIn(provider: Provider) {
    setPending(provider)
    setError(null)
    const { error: err } = await supabase.auth.signInWithOAuth({
      provider,
      options: { redirectTo: window.location.origin },
    })
    // On success the browser redirects to the provider; if we're still here, it failed.
    if (err) {
      setError(err.message)
      setPending(null)
    }
  }

  async function devSignIn(e: React.FormEvent) {
    e.preventDefault()
    setPending('password')
    setError(null)
    const { error: err } = await supabase.auth.signInWithPassword({ email, password })
    if (err) {
      setError(err.message)
      setPending(null)
    }
  }

  const busy = pending !== null

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-center text-xl">Property Valuations</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Button
            variant="outline"
            className="w-full"
            disabled={busy}
            onClick={() => void oauthSignIn('google')}
          >
            {pending === 'google' ? 'Redirecting to Google…' : 'Continue with Google'}
          </Button>
          <Button
            variant="outline"
            className="w-full"
            disabled={busy}
            onClick={() => void oauthSignIn('azure')}
          >
            {pending === 'azure' ? 'Redirecting to Microsoft…' : 'Continue with Microsoft'}
          </Button>

          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-center text-sm text-destructive">
              {error}
            </p>
          )}

          {import.meta.env.DEV && (
            <form onSubmit={devSignIn} className="mt-2 flex flex-col gap-2 border-t pt-4">
              <p className="text-center text-xs text-muted-foreground">
                Dev login (local only)
              </p>
              <div className="flex flex-col gap-1">
                <Label htmlFor="dev-email">Email</Label>
                <Input
                  id="dev-email"
                  type="email"
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor="dev-password">Password</Label>
                <Input
                  id="dev-password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={busy}>
                {pending === 'password' ? 'Signing in…' : 'Sign in'}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
