const MODULE_LABELS = {
  notifications: "Notificaciones",
  clients: "Clientes y CRM",
  projects: "Proyectos",
  tasks: "Tareas",
  users: "Colaboradores",
  collaboratorPayments: "Pagos a colaboradores",
  roles: "Roles y permisos",
  catalog: "Catálogo de servicios",
  dashboard: "Indicadores",
  platforms: "Plataformas",
  admin: "Administración",
};

const ACTION_LABELS = {
  view: "Consultar",
  create: "Crear",
  edit: "Modificar",
  delete: "Dar de baja o eliminar",
  resolveChange: "Resolver solicitudes de cambio",
  resolveDeactivation: "Resolver bajas",
  enterTechnicalValidation: "Iniciar validación técnica",
  returnProjectToExecution: "Devolver a ejecución",
  classifyProjectTasks: "Clasificar tareas del proyecto",
  evaluateProjectClosure: "Evaluar cierre técnico",
  markProjectReadyForDelivery: "Marcar listo para entrega",
  authorizeProjectDelivery: "Autorizar preparación de entrega",
  recordProjectDelivery: "Registrar constancia de entrega",
  formalizeProjectDelivery: "Formalizar entrega",
  reviewProjectDeliveryVersion: "Revisar versión de entrega",
  authorizeProjectStart: "Autorizar inicio de ejecución",
  startProject: "Iniciar ejecución",
  associateContractedServices: "Asociar servicios contratados",
  requestProjectCancellation: "Solicitar cancelación",
  evaluateProjectCancellation: "Evaluar cancelación",
  resolveProjectCancellation: "Resolver cancelación ordinaria",
  resolveExceptionalCancellation: "Resolver cancelación excepcional",
  evaluateProjectResumption: "Evaluar reanudación",
  resolveProjectResumption: "Resolver reanudación ordinaria",
  resolveExceptionalResumption: "Resolver reanudación excepcional",
  manageSubstitutions: "Gestionar suplencias",
  viewSubstitutions: "Consultar suplencias",
  assign: "Asignar",
  start: "Iniciar ejecución de tarea",
  submitReview: "Enviar a revisión",
  review: "Revisar resultado",
  reassign: "Reasignar",
  removeExecutor: "Retirar ejecutor",
  blockTask: "Bloquear tarea",
  unblockTask: "Desbloquear tarea",
  reportIncident: "Reportar incidencia",
  reopen: "Reabrir tarea",
  proposeCancellation: "Proponer cancelación",
  evaluateCancellation: "Evaluar cancelación de tarea",
  reviewCancellationCommercial: "Evaluar impacto comercial",
  applyCancellation: "Aplicar cancelación autorizada",
  designate: "Designar coordinación",
  withdrawCoordination: "Retirar coordinación",
  delegate: "Delegar liderazgo técnico",
  withdrawLeadership: "Retirar liderazgo técnico",
  manageTeam: "Gestionar equipo",
  withdrawTeam: "Retirar miembro del equipo",
  activate: "Activar",
  deactivate: "Desactivar",
  record: "Registrar",
  configure: "Configurar",
  manage: "Gestionar",
};

export function permissionModuleLabel(key) {
  const module = key.split(".")[0];
  return MODULE_LABELS[module] || module;
}

export function permissionActionLabel(key) {
  const action = key.slice(key.indexOf(".") + 1);
  if (ACTION_LABELS[action]) return ACTION_LABELS[action];
  return action.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/^./, (letter) => letter.toUpperCase());
}

export function groupPermissionsByModule(permissions) {
  return permissions.reduce((groups, permission) => {
    const label = permissionModuleLabel(permission);
    groups[label] ||= [];
    groups[label].push(permission);
    return groups;
  }, {});
}
