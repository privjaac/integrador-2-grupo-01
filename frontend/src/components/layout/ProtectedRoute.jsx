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
//   3. !canAccessRoute  → redirige a /clientes (ruta segura por defecto)
//   4. Todo OK          → renderiza el contenido
//
// Seguridad:
//   - Doble verificación: autenticación + autorización.
//   - El backend también valida — esta es solo la capa de UI.
//   - Redirige a /clientes en lugar de mostrar un 403 explícito
//     para no revelar qué rutas existen en el sistema.
// ==============================================================================

// ------------------------------------------------------------------------------
// SECCIÓN 1 — IMPORTS
// ------------------------------------------------------------------------------

import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { canAccessRoute } from "../../utils/permissions";
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

  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  // --------------------------------------------------------------------------
  // SECCIÓN 3 — VERIFICACIÓN 0: CARGA INICIAL
  // --------------------------------------------------------------------------

  if (isLoading) {
    return <LoadingSpinner fullPage label="Verificando sesión..." />;
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
  // Si el usuario está autenticado pero su rol no tiene acceso a esta ruta,
  // lo redirige a /clientes (la ruta más básica accesible para todos).
  //
  // Ejemplo: un Developer (L5) intenta acceder a /roles directamente
  // escribiendo la URL → lo redirige a /clientes silenciosamente.
  //
  // Solo verifica rutas principales (primer segmento de la URL).
  // Las sub-rutas (ej: /clientes/5/editar) se verifican en el componente
  // con can() de permissions.js.
  // --------------------------------------------------------------------------

  const basePath = "/" + location.pathname.split("/")[1];

  if (!canAccessRoute(user, basePath)) {
    return <Navigate to="/clientes" replace />;
  }

  // --------------------------------------------------------------------------
  // SECCIÓN 6 — RENDERIZADO DEL CONTENIDO PROTEGIDO
  // --------------------------------------------------------------------------

  return children;
}
