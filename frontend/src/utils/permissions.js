// ==============================================================================
// PERMISSIONS.JS — Sistema de permisos basado en roles (RBAC)
//
// Responsabilidad: centraliza TODA la lógica de permisos del frontend.
//   Define qué puede hacer cada rol en cada módulo del sistema.
//   Es la única fuente de verdad para control de acceso en la UI.
//
// Patrón: Role-Based Access Control (RBAC)
//   Cada rol tiene un nivel jerárquico y un conjunto de permisos.
//   Los permisos se verifican antes de renderizar botones, secciones
//   y rutas completas.
//
// IMPORTANTE — Seguridad en capas:
//   Este archivo controla la UI (qué ve el usuario).
//   El backend FastAPI tiene su propia validación de permisos.
//   Ambas capas son necesarias:
//     - Frontend: oculta botones y rutas para buena UX
//     - Backend:  rechaza peticiones no autorizadas para seguridad real
//   Nunca confiar solo en el frontend para seguridad.
//
// Roles del sistema ELISA:
//   L1 → Superadmin    → acceso total
//   L2 → Scrum Master  → casi todo, sin gestión de roles
//   L3 → Tech Lead     → clientes + usuarios + catálogo
//   L4 → Líder         → clientes + usuarios
//   L5 → Developer     → solo clientes (lectura + registro)
//
// Uso en componentes:
//   import { can, canAccessRoute } from '../../utils/permissions'
//
//   const { user } = useAuth()
//
//   {can(user, 'clients', 'create') && <Button>Nuevo Cliente</Button>}
//   {can(user, 'users',   'delete') && <Button variant="danger">Eliminar</Button>}
// ==============================================================================

// ==============================================================================
// SECCIÓN 1 — DEFINICIÓN DE ROLES Y JERARQUÍAS
//
// Cada rol tiene:
//   level   → número de jerarquía (menor = más poder)
//   label   → nombre legible
//   routes  → rutas a las que puede acceder
// ==============================================================================

export const ROLES = {
  L1: {
    level: 1,
    label: "Superadmin",
    // Superadmin accede a todas las rutas del sistema
    routes: ["/dashboard", "/clientes", "/usuarios", "/roles", "/catalogo"],
  },

  L2: {
    level: 2,
    label: "Scrum Master",
    // Scrum Master ve todo excepto gestión de roles
    routes: ["/clientes", "/usuarios", "/catalogo"],
  },

  L3: {
    level: 3,
    label: "Tech Lead",
    // Tech Lead gestiona clientes, usuarios y catálogo
    routes: ["/clientes", "/usuarios", "/catalogo"],
  },

  L4: {
    level: 4,
    label: "Líder",
    // Líder gestiona clientes y usuarios
    routes: ["/clientes", "/usuarios"],
  },

  L5: {
    level: 5,
    label: "Developer",
    // Developer solo accede a clientes
    routes: ["/clientes"],
  },
};

// ==============================================================================
// SECCIÓN 2 — MATRIZ DE PERMISOS POR MÓDULO
//
// Define qué acciones puede hacer cada rol en cada módulo.
// Estructura: PERMISSIONS[módulo][acción] = [roles permitidos]
//
// Acciones disponibles:
//   view   → ver la lista y el detalle
//   create → crear registros nuevos
//   edit   → editar registros existentes
//   delete → desactivar/eliminar registros
//   export → exportar datos (futuro)
// ==============================================================================

const PERMISSIONS = {
  // ── MÓDULO CLIENTES ──────────────────────────────────────────────────────
  clients: {
    // Todos los roles pueden ver clientes
    view: ["L1", "L2", "L3", "L4", "L5"],
    // L1 a L4 pueden crear clientes — L5 (Developer) no
    create: ["L1", "L2", "L3", "L4"],
    // L1 a L4 pueden editar clientes
    edit: ["L1", "L2", "L3", "L4"],
    // Solo L1 y L2 pueden desactivar clientes
    delete: ["L1", "L2"],
  },

  // ── MÓDULO USUARIOS (COLABORADORES) ─────────────────────────────────────
  users: {
    // L1 a L4 pueden ver usuarios
    view: ["L1", "L2", "L3", "L4"],
    // L1 a L4 pueden crear usuarios (respetando jerarquía — validado en backend)
    create: ["L1", "L2", "L3", "L4"],
    // L1 a L3 pueden editar usuarios
    edit: ["L1", "L2", "L3"],
    // Solo L1 puede desactivar usuarios
    delete: ["L1"],
  },

  // ── MÓDULO ROLES ─────────────────────────────────────────────────────────
  roles: {
    // Solo L1 y L2 pueden ver la sección de roles
    view: ["L1", "L2"],
    // Solo L1 puede crear roles
    create: ["L1"],
    // Solo L1 puede editar roles
    edit: ["L1"],
    // Solo L1 puede eliminar roles
    delete: ["L1"],
  },

  // ── MÓDULO CATÁLOGO ──────────────────────────────────────────────────────
  catalog: {
    // L1 a L3 pueden ver el catálogo
    view: ["L1", "L2", "L3"],
    // Solo L1 puede crear tipos de web y características
    create: ["L1"],
    // Solo L1 puede editar el catálogo
    edit: ["L1"],
    // Solo L1 puede desactivar ítems del catálogo
    delete: ["L1"],
  },

  //MODULO DASHBOARD — SOLO EL SUPERADMIN PUEDE VER EL DASHBOARD
  dashboard: {
    view: ["L1"], // solo el superadmin puede ver el dashboard
    create: [],
    edit: [],
    delete: [],
  },

  // ── MÓDULO DE ADMINISTRACIÓN DEL SISTEMA ─────────────────────────────────
  // Para funciones futuras como configuración global, reportes, etc.
  admin: {
    view: ["L1"],
    create: ["L1"],
    edit: ["L1"],
    delete: ["L1"],
  },
};

// ==============================================================================
// SECCIÓN 3 — FUNCIONES PÚBLICAS DE VERIFICACIÓN
// ==============================================================================

// ------------------------------------------------------------------------------
// can — Verifica si un usuario tiene permiso para una acción en un módulo
//
// Es la función principal del sistema de permisos.
// Se usa para mostrar u ocultar botones y acciones en la UI.
//
// Parámetros:
//   user   (object) → el objeto user del AuthContext
//                     debe tener la propiedad 'role' (ej: 'L1', 'L5')
//   module (string) → nombre del módulo: 'clients' | 'users' | 'roles' | 'catalog'
//   action (string) → acción: 'view' | 'create' | 'edit' | 'delete'
//
// Retorna:
//   boolean → true si el usuario tiene permiso, false si no
//
// Ejemplos:
//   can(user, 'clients', 'create') → true si L1-L4, false si L5
//   can(user, 'roles',   'view')   → true si L1-L2, false si L3-L5
//   can(user, 'catalog', 'delete') → true solo si L1
//
// Seguridad:
//   Si user es null o no tiene role, retorna false (principio de mínimo acceso).
//   Si el módulo o acción no existe, retorna false.
// ------------------------------------------------------------------------------

export function can(user, module, action) {
  // Si no hay usuario autenticado, no hay permisos
  if (!user || !user.role) return false;

  // Si el módulo no existe en la matriz, no hay permisos
  const modulePerms = PERMISSIONS[module];
  if (!modulePerms) return false;

  // Si la acción no existe en el módulo, no hay permisos
  const allowedRoles = modulePerms[action];
  if (!allowedRoles) return false;

  // Verifica si el rol del usuario está en la lista de roles permitidos
  return allowedRoles.includes(user.role);
}

// ------------------------------------------------------------------------------
// canAccessRoute — Verifica si un usuario puede acceder a una ruta
//
// Se usa en el Sidebar para mostrar u ocultar ítems del menú,
// y en el ProtectedRoute extendido para redirigir si no tiene acceso.
//
// Parámetros:
//   user  (object) → el objeto user del AuthContext
//   route (string) → la ruta a verificar (ej: '/clientes', '/roles')
//
// Retorna:
//   boolean → true si el usuario puede acceder a la ruta
//
// Ejemplos:
//   canAccessRoute(user, '/roles')    → true solo para L1 y L2
//   canAccessRoute(user, '/catalogo') → true para L1, L2, L3
//   canAccessRoute(user, '/clientes') → true para todos los roles
// ------------------------------------------------------------------------------

export function canAccessRoute(user, route) {
  // Si no hay usuario, no hay acceso
  if (!user || !user.role) return false;

  // Busca el rol en la definición de roles
  const roleDef = ROLES[user.role];

  // Si el rol no existe en la definición, no hay acceso
  if (!roleDef) return false;

  // Verifica si la ruta está en las rutas permitidas del rol
  // También verifica sub-rutas (ej: /clientes/nuevo → pertenece a /clientes)
  return roleDef.routes.some(
    (allowedRoute) =>
      route === allowedRoute || route.startsWith(allowedRoute + "/"),
  );
}

// ------------------------------------------------------------------------------
// getAccessibleRoutes — Retorna todas las rutas accesibles para un usuario
//
// Se usa en el Sidebar para construir dinámicamente el menú de navegación
// mostrando solo las secciones a las que el usuario tiene acceso.
//
// Parámetros:
//   user (object) → el objeto user del AuthContext
//
// Retorna:
//   string[] → array de rutas accesibles
//              Ej: ['L3'] → ['/clientes', '/usuarios', '/catalogo']
// ------------------------------------------------------------------------------

export function getAccessibleRoutes(user) {
  // Sin usuario, no hay rutas accesibles
  if (!user || !user.role) return [];

  const roleDef = ROLES[user.role];

  if (!roleDef) return [];

  return roleDef.routes;
}

// ------------------------------------------------------------------------------
// getRoleLevel — Retorna el nivel numérico del rol de un usuario
//
// Útil para comparar jerarquías entre usuarios.
// Un número menor = mayor jerarquía (L1 > L2 > L3 > L4 > L5).
//
// Parámetros:
//   user (object) → el objeto user del AuthContext
//
// Retorna:
//   number → nivel del rol (1-5), o 999 si el rol es inválido
//
// Ejemplos:
//   getRoleLevel({ role: 'L1' }) → 1
//   getRoleLevel({ role: 'L5' }) → 5
//   getRoleLevel(null)           → 999
// ------------------------------------------------------------------------------

export function getRoleLevel(user) {
  if (!user || !user.role) return 999;

  const roleDef = ROLES[user.role];

  return roleDef ? roleDef.level : 999;
}

// ------------------------------------------------------------------------------
// canManageUser — Verifica si un usuario puede gestionar a otro usuario
//
// Un colaborador solo puede crear/editar usuarios de MENOR jerarquía.
// Ej: L2 puede crear L3, L4, L5 — pero NO puede crear otro L2 o L1.
//
// Parámetros:
//   currentUser (object) → el usuario logueado (quien realiza la acción)
//   targetRole  (string) → el rol del usuario que se quiere gestionar
//
// Retorna:
//   boolean → true si puede gestionar al usuario target
//
// Ejemplos:
//   canManageUser(L2_user, 'L3') → true  (L2 puede gestionar L3)
//   canManageUser(L2_user, 'L2') → false (L2 no puede gestionar otro L2)
//   canManageUser(L2_user, 'L1') → false (L2 no puede gestionar L1)
//   canManageUser(L1_user, 'L1') → false (ni Superadmin se gestiona a sí mismo con esto)
// ------------------------------------------------------------------------------

export function canManageUser(currentUser, targetRole) {
  if (!currentUser || !targetRole) return false;

  const currentLevel = getRoleLevel(currentUser);
  const targetDef = ROLES[targetRole];

  if (!targetDef) return false;

  // Solo puede gestionar usuarios de MENOR jerarquía (nivel numérico mayor)
  return currentLevel < targetDef.level;
}

// ------------------------------------------------------------------------------
// getCreatableRoles — Retorna los roles que un usuario puede asignar al crear
//
// Se usa en el formulario de creación de usuarios para poblar
// el select de roles con solo las opciones válidas para el usuario actual.
//
// Parámetros:
//   user (object) → el usuario logueado
//
// Retorna:
//   array → lista de roles que puede asignar
//           Ej: [{ value: 'L3', label: 'Tech Lead' }, ...]
// ------------------------------------------------------------------------------

export function getCreatableRoles(user) {
  if (!user || !user.role) return [];

  const currentLevel = getRoleLevel(user);

  // Filtra los roles que tienen nivel mayor al del usuario actual
  // (solo puede crear usuarios de menor jerarquía)
  return Object.entries(ROLES)
    .filter(([, roleDef]) => roleDef.level > currentLevel)
    .map(([roleKey, roleDef]) => ({
      value: roleKey,
      label: roleDef.label,
    }));
}
