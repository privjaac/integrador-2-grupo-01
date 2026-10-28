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
    routes: ["/dashboard", "/clientes", "/usuarios", "/roles", "/catalogo", "/proyectos", "/tareas"],
  },

  L2: {
    level: 2,
    label: "Scrum Master",
    // Scrum Master ve todo excepto gestión de roles
    routes: ["/dashboard", "/clientes", "/proyectos", "/usuarios", "/roles", "/catalogo", "/tareas"],
  },

  L3: {
    level: 3,
    label: "Tech Lead",
    // Tech Lead gestiona clientes, usuarios y catálogo
    routes: ["/dashboard", "/clientes", "/proyectos", "/usuarios", "/roles", "/catalogo", "/tareas"],
  },

  L4: {
    level: 4,
    label: "Líder",
    // Líder gestiona clientes y usuarios
    routes: ["/usuarios", "/roles", "/tareas"],
  },

  L5: {
    level: 5,
    label: "Developer",
    // Developer solo accede a clientes
    routes: ["/roles", "/tareas"],
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
  notifications: {
    configure: ["L1", "L2"],
  },
  // ── MÓDULO CLIENTES ──────────────────────────────────────────────────────
  clients: {
    // CRM-002/003/008/009: lectura L1/L2/L3.
    view: ["L1", "L2", "L3"],
    // CRM-001: creación L1/L2.
    create: ["L1", "L2"],
    // CRM-004 solicita; no aplica cambios directos.
    edit: ["L1", "L2", "L3"],
    // CRM-007 solicita la baja; L1 resuelve y la interfaz limita la cola.
    delete: ["L1", "L2", "L3"],
    resolveChange: ["L1", "L2"],
    resolveDeactivation: ["L1"],
  },

  // ── MÓDULO PROYECTOS (F2-01) ─────────────────────────────────────────────
  // L2 crea; L2 y L3 consultan. La autorización no se hereda por jerarquía.
  projects: {
    view: ["L2", "L3"],
    create: ["L2"],
    enterTechnicalValidation: ["L3"],
    returnProjectToExecution: ["L3"],
    classifyProjectTasks: ["L3"],
    evaluateProjectClosure: ["L3"],
    markProjectReadyForDelivery: ["L3"],
    authorizeProjectDelivery: ["L2"],
    recordProjectDelivery: ["L2"],
    formalizeProjectDelivery: ["L2"],
    reviewProjectDeliveryVersion: ["L3"],
    authorizeProjectStart: ["L2"],
    startProject: ["L3"],
    associateContractedServices: ["L3"],
    requestProjectCancellation: ["L2"],
    evaluateProjectCancellation: ["L3"],
    resolveProjectCancellation: ["L2"],
    edit: [],
    delete: [],
  },
  tasks: {
    view: ["L3", "L4", "L5"],
    create: ["L3", "L4"],
    assign: ["L4"],
    start: ["L5"],
    submitReview: ["L5"],
    review: ["L4"],
    reassign: ["L3", "L4"],
    removeExecutor: ["L3", "L4"],
    blockTask: ["L3", "L4"],
    unblockTask: ["L3", "L4"],
    reportIncident: ["L5"],
    reopen: ["L3"],
    proposeCancellation: ["L4"],
    evaluateCancellation: ["L3"],
    reviewCancellationCommercial: ["L2"],
    applyCancellation: ["L3"],
    designate: ["L2"],
    withdrawCoordination: ["L2"],
    delegate: ["L3"],
    withdrawLeadership: ["L3"],
    manageTeam: ["L4"],
    withdrawTeam: ["L4"],
  },

  // ── MÓDULO USUARIOS (COLABORADORES) ─────────────────────────────────────
  users: {
    // PB-COL-002/006: listado y detalle para L1 a L4.
    view: ["L1", "L2", "L3", "L4"],
    // PB-COL-005/R-B3-01-A: la matriz final por nivel se valida también en backend.
    create: ["L1", "L2", "L3", "L4"],
    // PB-COL-003/004: competencia SA/SM, sujeta al nivel y al objetivo.
    edit: ["L1", "L2"],
    activate: ["L1", "L2"],
    deactivate: ["L1", "L2"],
    delete: [],
  },

  collaboratorPayments: {
    view: ["L1", "L2"],
    record: ["L1", "L2"],
  },

  // ── MÓDULO ROLES ─────────────────────────────────────────────────────────
  roles: {
    // PB-ROL-001/003: cualquier colaborador autenticado puede consultar roles.
    view: ["L1", "L2", "L3", "L4", "L5"],
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

  // PB-REP-003/006/009: dashboard por rol; finanzas se filtran en backend.
  dashboard: {
    view: ["L1", "L2", "L3"],
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
  if (Array.isArray(user.permissions)) {
    return user.permissions.includes(`${module}.${action}`);
  }
  return allowedRoles.includes(user.role);
}

// Verifica alcance ordinario de administración de colaboradores. La capacidad
// del actor nunca permite gestionar su propia cuenta ni una cuenta L1.
export function canManageCollaborator(user, collaborator) {
  if (!user?.role || !collaborator || String(user.id) === String(collaborator.id)) {
    return false;
  }
  const actorLevel = Number(user.role.slice(1));
  if (![1, 2].includes(actorLevel)) return false;
  if (user.role === "L1" && collaborator.role_level === "L1") return false;
  const targetRole = collaborator.role_level || collaborator.role;
  const targetLevel = typeof targetRole === "string"
    ? Number(targetRole.slice(1))
    : Number(targetRole);
  return Number.isInteger(actorLevel) && Number.isInteger(targetLevel)
    && targetLevel > 1;
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

  const routePermission = {
    "/notificaciones/configuracion": ["notifications", "configure"],
    "/dashboard": ["dashboard", "view"],
    "/clientes": ["clients", "view"],
    "/proyectos": ["projects", "view"],
    "/tareas": ["tasks", "view"],
    "/usuarios": ["users", "view"],
    "/colaboradores/pagos": ["collaboratorPayments", "view"],
    "/roles": ["roles", "view"],
    "/catalogo": ["catalog", "view"],
  };
  const matchingPath = Object.keys(routePermission).find(
    (path) => route === path || route.startsWith(`${path}/`),
  );
  if (matchingPath) {
    const [module, action] = routePermission[matchingPath];
    // L2 enters the task workspace for coordination operations even though
    // the task read/list capability itself remains limited to L3–L5.
    if (matchingPath === "/tareas") {
      return can(user, "tasks", "view")
        || can(user, "tasks", "designate")
        || can(user, "tasks", "reviewCancellationCommercial");
    }
    return can(user, module, action);
  }

  // Busca el rol en la definición de roles para clientes antiguos/sin permisos serializados.
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

  return roleDef.routes.filter((route) => canAccessRoute(user, route));
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

export function getCreatableRoles(user, availableRoles = null) {
  if (!user || !user.role) return [];

  const currentLevel = getRoleLevel(user);

  if (Array.isArray(availableRoles)) {
    return availableRoles
      .filter((role) => role.is_active !== false && (Number(role.hierarchy) > currentLevel || (user.role === "L1" && Number(role.hierarchy) === 1)))
      .map((role) => ({ value: String(role.id), label: `L${role.hierarchy} — ${role.name}` }));
  }

  // La excepción L1→L1 aplica únicamente a la creación; en los demás casos
  // se conserva la matriz de HU-24 por nivel funcional.
  return Object.entries(ROLES)
    .filter(([, roleDef]) => roleDef.level > currentLevel || (user.role === "L1" && roleDef.level === 1))
    .map(([roleKey, roleDef]) => ({
      value: roleKey,
      label: roleDef.label,
    }));
}
