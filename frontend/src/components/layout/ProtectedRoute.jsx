// ==============================================================================
// PROTECTEDROUTE.JSX — Guardia de rutas con control de acceso por rol (v2)
//
// Responsabilidad: protege las rutas verificando DOS condiciones:
//   1. ¿El usuario está autenticado? (tiene JWT)
//   2. ¿El usuario tiene el rol correcto para acceder a esta ruta?
//
// Patrón: Route Guard Pattern + RBAC
//   Primera capa: verifica autenticación (JWT en memoria)
//   Segunda capa: verifica permisos de ruta (rol del usuario)
//
// Flujo de verificación:
//   1. isLoading     → spinner (verificando sesión)
//   2. !isAuthenticated → redirige a /login
//   3. !canAccessRoute  → redirige a la primera ruta autorizada o informa 403
//   4. Todo OK          → renderiza el contenido
//
// Seguridad:
//   - Doble verificación: autenticación + autorización.
//   - El backend también valida — esta es solo la capa de UI.
//   - Nunca redirige a una ruta que el usuario no puede abrir.
// ==============================================================================

// ------------------------------------------------------------------------------
// SECCIÓN 1 — IMPORTS
// ------------------------------------------------------------------------------

import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { canAccessRoute, getInitialRoute } from "../../utils/permissions";
import LoadingSpinner from "../ui/LoadingSpinner";

// ==============================================================================
// COMPONENTE — ProtectedRoute
//
// Props:
//   children (node) → el componente a renderizar si pasa las verificaciones
// ==============================================================================

export default function ProtectedRoute({ children }) {
  // --------------------------------------------------------------------------
  // SECCIÓN 2 — ESTADO DE AUTENTICACIÓN Y UBICACIÓN
  // --------------------------------------------------------------------------

  const {
    isAuthenticated,
    isLoading,
    sessionRestoreError,
    retrySessionRestore,
    user,
  } = useAuth();
  const location = useLocation();

  // --------------------------------------------------------------------------
  // SECCIÓN 3 — VERIFICACIÓN 0: CARGA INICIAL
  // --------------------------------------------------------------------------

  if (isLoading) {
    return <LoadingSpinner fullPage label="Verificando sesión..." />;
  }

  if (sessionRestoreError) {
    return (
      <main role="alert" style={{ padding: 32, color: "#e2e8f0" }}>
        <h1>No se pudo verificar la sesión</h1>
        <p>La conexión no permitió confirmar tu acceso. La sesión guardada se conserva para reintentar.</p>
        <button type="button" onClick={retrySessionRestore}>Reintentar</button>
      </main>
    );
  }

  // --------------------------------------------------------------------------
  // SECCIÓN 4 — VERIFICACIÓN 1: AUTENTICACIÓN
  //
  // Si no hay JWT en memoria → redirige al login guardando la URL actual.
  // --------------------------------------------------------------------------

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  // --------------------------------------------------------------------------
  // SECCIÓN 5 — VERIFICACIÓN 2: PERMISOS DE RUTA POR ROL
  //
  // Si el usuario está autenticado pero carece de acceso a esta ruta, se
  // redirige a un destino permitido. Si no existe, se presenta un aviso.
  //
  // Verifica la ruta completa para respetar capacidades específicas de
  // subrutas, además de las rutas principales y sus subrutas existentes.
  // --------------------------------------------------------------------------

  if (!canAccessRoute(user, location.pathname)) {
    const safeRoute = getInitialRoute(user);
    if (safeRoute && safeRoute !== location.pathname) {
      return <Navigate to={safeRoute} replace />;
    }
    return (
      <main role="alert" style={{ padding: 32, color: "#e2e8f0" }}>
        <h1>Acceso no disponible</h1>
        <p>Tu cuenta no tiene una pantalla autorizada para esta dirección.</p>
      </main>
    );
  }

  // --------------------------------------------------------------------------
  // SECCIÓN 6 — RENDERIZADO DEL CONTENIDO PROTEGIDO
  // --------------------------------------------------------------------------

  return children;
}
