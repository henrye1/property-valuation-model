import { Routes, Route } from 'react-router-dom'
import { RequireAuth } from '@/components/layout/RequireAuth'
import { RequireValuer } from '@/components/layout/RequireValuer'
import { AppShell } from '@/components/layout/AppShell'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import EntitiesPage from '@/pages/EntitiesPage'
import EntityDetailPage from '@/pages/EntityDetailPage'
import EntityFormPage from '@/pages/EntityFormPage'
import PropertiesPage from '@/pages/PropertiesPage'
import PropertyDetailPage from '@/pages/PropertyDetailPage'
import PropertyFormPage from '@/pages/PropertyFormPage'
import NotFoundPage from '@/pages/NotFoundPage'
import SnapshotViewerPage from '@/pages/SnapshotViewerPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/entities" element={<EntitiesPage />} />
          <Route path="/entities/:id" element={<EntityDetailPage />} />
          <Route path="/properties" element={<PropertiesPage />} />
          <Route path="/properties/:id" element={<PropertyDetailPage />} />
          <Route path="/properties/:id/valuations/:sid" element={<SnapshotViewerPage />} />
          {/* Valuer-only create/edit routes */}
          <Route element={<RequireValuer />}>
            <Route path="/entities/new" element={<EntityFormPage />} />
            <Route path="/entities/:id/edit" element={<EntityFormPage />} />
            <Route path="/properties/new" element={<PropertyFormPage />} />
            <Route path="/properties/:id/edit" element={<PropertyFormPage />} />
          </Route>
          {/* Later slices add /imports, /audit, /settings/users */}
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
