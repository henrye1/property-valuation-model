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
import ValuationEditorPage from '@/pages/ValuationEditorPage'
import ImportsPage from '@/pages/ImportsPage'
import ImportNewPage from '@/pages/ImportNewPage'
import ImportReviewPage from '@/pages/ImportReviewPage'
import AuditPage from '@/pages/AuditPage'
import UsersPage from '@/pages/UsersPage'

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
          {/* Imports list — readable by all authenticated users */}
          <Route path="/imports" element={<ImportsPage />} />
          {/* Audit log + users — readable by all authenticated users */}
          <Route path="/audit" element={<AuditPage />} />
          <Route path="/settings/users" element={<UsersPage />} />
          {/* Valuer-only create/edit routes */}
          <Route element={<RequireValuer />}>
            <Route path="/entities/new" element={<EntityFormPage />} />
            <Route path="/entities/:id/edit" element={<EntityFormPage />} />
            <Route path="/properties/new" element={<PropertyFormPage />} />
            <Route path="/properties/:id/edit" element={<PropertyFormPage />} />
            <Route path="/properties/:id/valuations/new" element={<ValuationEditorPage />} />
            {/* Static /imports/new must be declared before the /imports/:id param route */}
            <Route path="/imports/new" element={<ImportNewPage />} />
            <Route path="/imports/:id" element={<ImportReviewPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
