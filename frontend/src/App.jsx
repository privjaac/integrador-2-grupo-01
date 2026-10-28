// ==============================================================================
// APP.JSX v2 — Rutas del sistema ELISA con SessionWatcher
//
// Agrega SessionWatcher que:
//   - Sincroniza el token con window.__elisa_token__ para axios
//   - Escucha eventos de sesión (warning + expired)
//   - Muestra toasts y redirige al login cuando la sesión vence
// ==============================================================================

import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import SessionWatcher from "./components/layout/SessionWatcher";
import ProtectedRoute from "./components/layout/ProtectedRoute";
import MainLayout from "./components/layout/MainLayout";
import LoadingSpinner from "./components/ui/LoadingSpinner";

import LoginPage from "./pages/auth/LoginPage";
import { ForgotPasswordPage, ResetPasswordPage } from "./pages/auth/RecoveryPages";
const ClientsPage = lazy(() => import("./pages/clients/ClientsPage"));
const ClientDetail = lazy(() => import("./pages/clients/ClientDetail"));
const ClientForm = lazy(() => import("./pages/clients/ClientForm"));
const UsersPage = lazy(() => import("./pages/users/UsersPage"));
const CollaboratorPaymentsPage = lazy(() => import("./pages/users/CollaboratorPaymentsPage"));
const CollaboratorDetail = lazy(() => import("./pages/users/CollaboratorDetail"));
const UserForm = lazy(() => import("./pages/users/UserForm"));
const RolesPage = lazy(() => import("./pages/roles/RolesPage"));
const DashboardPage = lazy(() => import("./pages/dashboard/DashboardPage"));
const CatalogPage = lazy(() => import("./pages/catalog/CatalogPage"));
const ProjectsPage = lazy(() => import("./pages/projects/ProjectsPage"));
const TasksPage = lazy(() => import("./pages/tasks/TasksPage"));

export default function App() {
  return (
    <>
      <SessionWatcher />

      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password/:token" element={<ResetPasswordPage />} />

          <Route
            element={
              <ProtectedRoute>
                <MainLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/clientes" element={<ClientsPage />} />
            <Route path="/proyectos" element={<ProjectsPage />} />
            <Route path="/tareas" element={<TasksPage />} />
            <Route path="/tareas/detalle/:taskId" element={<TasksPage />} />
            <Route path="/clientes/nuevo" element={<ClientForm />} />
            <Route path="/clientes/:id" element={<ClientDetail />} />
            <Route path="/clientes/:id/editar" element={<ClientForm />} />
            <Route path="/usuarios" element={<UsersPage />} />
            <Route path="/colaboradores/pagos" element={<CollaboratorPaymentsPage />} />
            <Route path="/usuarios/nuevo" element={<UserForm />} />
            <Route path="/usuarios/:id" element={<CollaboratorDetail />} />
            <Route path="/usuarios/:id/editar" element={<UserForm />} />
            <Route path="/roles" element={<RolesPage />} />
            <Route path="/catalogo" element={<CatalogPage />} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Suspense>
    </>
  );
}
