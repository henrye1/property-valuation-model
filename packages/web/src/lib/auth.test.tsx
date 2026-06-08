import { describe, it, expect, vi } from 'vitest'

// Mock supabase.ts so the module-level createClient() call doesn't fail
// in the test environment (no VITE_* env vars present during vitest).
vi.mock('./supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn().mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } }),
      signInWithOAuth: vi.fn(),
      signOut: vi.fn(),
    },
  },
}))

import { canWrite } from './auth'

describe('canWrite', () => {
  it('is true for valuer', () => expect(canWrite('valuer')).toBe(true))
  it('is false for viewer', () => expect(canWrite('viewer')).toBe(false))
  it('is false for null', () => expect(canWrite(null)).toBe(false))
})
