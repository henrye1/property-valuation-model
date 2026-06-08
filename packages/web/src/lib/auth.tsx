/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'
import { supabase } from './supabase'
import { createApiClient, type ApiClient } from './api'
import { AppUserSchema, type AppUser, type Role } from '@/schemas/user'

export function canWrite(role: Role | null): boolean {
  return role === 'valuer'
}

interface AuthState {
  session: Session | null
  user: AppUser | null
  role: Role | null
  loading: boolean
  api: ApiClient
  signInWith: (provider: 'google' | 'azure') => Promise<void>
  signOut: () => Promise<void>
}

const Ctx = createContext<AuthState | null>(null)

export const useAuth = () => {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAuth outside provider')
  return v
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [user, setUser] = useState<AppUser | null>(null)
  const [loading, setLoading] = useState(true)

  const api = useMemo(
    () =>
      createApiClient({
        baseUrl: import.meta.env.VITE_API_BASE_URL,
        getToken: async () =>
          (await supabase.auth.getSession()).data.session?.access_token ?? null,
        onUnauthorized: () => {
          void supabase.auth.signOut()
        },
      }),
    [],
  )

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s))
    return () => sub.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    const p = session
      ? api.get('/me').then((d) => setUser(AppUserSchema.parse(d)))
      : Promise.resolve().then(() => setUser(null))
    p.catch(() => setUser(null))
  }, [session, api])

  const value: AuthState = {
    session,
    user,
    role: user?.role ?? null,
    loading,
    api,
    signInWith: async (provider) => {
      await supabase.auth.signInWithOAuth({
        provider,
        options: { redirectTo: window.location.origin },
      })
    },
    signOut: async () => {
      await supabase.auth.signOut()
    },
  }

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
