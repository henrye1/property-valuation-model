import { PageHeader } from '@/components/layout/PageHeader'
import { DataState } from '@/components/layout/DataState'
import { EmptyState } from '@/components/layout/EmptyState'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { useUsers } from '@/hooks/useUsers'
import { formatDateTime } from '@/lib/format'
import type { Role } from '@/schemas/user'

function roleVariant(role: Role): 'default' | 'secondary' {
  return role === 'valuer' ? 'default' : 'secondary'
}

export default function UsersPage() {
  const { isPending, error, data } = useUsers()

  return (
    <div className="space-y-6">
      <PageHeader title="Users" />
      <p className="text-sm text-muted-foreground">
        Roles are managed in the Supabase dashboard.
      </p>
      <DataState isPending={isPending} error={error}>
        {data && data.length === 0 ? (
          <EmptyState title="No users" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Last seen</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="text-muted-foreground">
                    {user.email ?? '—'}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {user.display_name ?? '—'}
                  </TableCell>
                  <TableCell>
                    <Badge variant={roleVariant(user.role)}>{user.role}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDateTime(user.last_seen_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DataState>
    </div>
  )
}
