import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

const navItems = [
  { label: 'Dashboard', to: '/' },
  { label: 'Entities', to: '/entities' },
  { label: 'Properties', to: '/properties' },
  { label: 'Imports', to: '/imports' },
  { label: 'Audit', to: '/audit' },
  { label: 'Users', to: '/settings/users' },
]

export function Sidebar() {
  return (
    <aside className="flex w-56 flex-col gap-1 border-r border-border bg-card px-3 py-4">
      <div className="mb-4 px-2 text-sm font-semibold text-muted-foreground uppercase tracking-wider">
        Navigation
      </div>
      <nav className="flex flex-col gap-0.5">
        {navItems.map(({ label, to }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              cn(
                'rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-foreground hover:bg-muted hover:text-foreground',
              )
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
