import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

// Control variable shared by all tests - set before each test case
let mockRole: 'valuer' | 'viewer' | null = null

vi.mock('@/lib/auth', () => ({
  useAuth: () => ({ role: mockRole }),
  canWrite: (r: string | null) => r === 'valuer',
}))

// Import after mock is hoisted
import { RoleGate } from './RoleGate'

afterEach(cleanup)

describe('RoleGate', () => {
  beforeEach(() => {
    mockRole = null
  })

  it('renders children for valuer', () => {
    mockRole = 'valuer'
    render(<RoleGate><button>Edit</button></RoleGate>)
    expect(screen.queryByText('Edit')).not.toBeNull()
  })

  it('renders nothing for viewer', () => {
    mockRole = 'viewer'
    render(<RoleGate><button>Edit</button></RoleGate>)
    expect(screen.queryByText('Edit')).toBeNull()
  })

  it('renders nothing for null role', () => {
    mockRole = null
    render(<RoleGate><button>Edit</button></RoleGate>)
    expect(screen.queryByText('Edit')).toBeNull()
  })

  it('renders fallback for viewer when provided', () => {
    mockRole = 'viewer'
    render(<RoleGate fallback={<span>No access</span>}><button>Edit</button></RoleGate>)
    expect(screen.queryByText('Edit')).toBeNull()
    expect(screen.queryByText('No access')).not.toBeNull()
  })
})
