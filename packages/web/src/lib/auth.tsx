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
  // loading stays true until BOTH the session check AND (if a session exists)
  // the /me fetch have settled — prevents RequireValuer from seeing a transient
  // loading=false, role=null window on hard refresh of valuer-only routes.
  const [loading, setLoading] = useState(true)
  // Track whether the initial getSession() call has completed so we know
  // whether subsequent session changes come from onAuthStateChange.
  const [sessionChecked, setSessionChecked] = useState(false)

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
      setSessionChecked(true)
      // If there is no session we can mark loading done immediately; if there
      // is a session, we must wait for the /me effect below to settle first.
      if (!data.session) setLoading(false)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => {
      setSession(s)
      // When signing out the session becomes null; we know role immediately.
      if (!s) {
        setUser(null)
        setLoading(false)
      }
    })
    return () => sub.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    // Only run once sessionChecked is true (i.e. after getSession() resolved).
    // This avoids kicking off a /me fetch with the initial null session before
    // we know the real session state.
    if (!sessionChecked) return

    const p = session
      ? api
          .get('/me')
          .then((d) => setUser(AppUserSchema.parse(d)))
          .catch(() => setUser(null))
      : Promise.resolve().then(() => setUser(null))
    p.finally(() => setLoading(false))
  }, [session, api, sessionChecked])

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
