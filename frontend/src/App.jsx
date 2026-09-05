// ==============================================================================
// APP.JSX v2 — Rutas del sistema ELISA con SessionWatcher
//
// Agrega SessionWatcher que:
//   - Sincroniza el token con window.__elisa_token__ para axios
//   - Escucha eventos de sesión (warning + expired)
//   - Muestra toasts y redirige al login cuando la sesión vence
// ==============================================================================

import { Routes, Route, Navigate } from "react-router-dom";

import SessionWatcher from "./components/layout/SessionWatcher";
import ProtectedRoute from "./components/layout/ProtectedRoute";
import MainLayout from "./components/layout/MainLayout";

import LoginPage from "./pages/auth/LoginPage";
import ClientsPage from "./pages/clients/ClientsPage";
import ClientDetail from "./pages/clients/ClientDetail";
import ClientForm from "./pages/clients/ClientForm";
import UsersPage from "./pages/users/UsersPage";
import CollaboratorDetail from "./pages/users/CollaboratorDetail";
import UserForm from "./pages/users/UserForm";
import RolesPage from "./pages/roles/RolesPage";
import DashboardPage from "./pages/dashboard/DashboardPage";
import CatalogPage from "./pages/catalog/CatalogPage";

export default function App() {
  return (
    <>
      {/* SessionWatcher — escucha eventos de sesión y sincroniza el token */}
      <SessionWatcher />

      <Routes>
        {/* Ruta pública */}
        <Route path="/login" element={<LoginPage />} />

        {/* Rutas privadas */}
        <Route
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/clientes" element={<ClientsPage />} />
          <Route path="/clientes/nuevo" element={<ClientForm />} />
          <Route path="/clientes/:id" element={<ClientDetail />} />
          <Route path="/clientes/:id/editar" element={<ClientForm />} />
          <Route path="/usuarios" element={<UsersPage />} />
          <Route path="/usuarios/nuevo" element={<UserForm />} />
          <Route path="/usuarios/:id" element={<CollaboratorDetail />} />
          <Route path="/usuarios/:id/editar" element={<UserForm />} />
          <Route path="/roles" element={<RolesPage />} />
          <Route path="/catalogo" element={<CatalogPage />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </>
  );
}
