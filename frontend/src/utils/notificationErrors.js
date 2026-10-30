import { canAccessRoute } from "./permissions.js";

export function isNotificationInboxOutOfScope(error) {
  return error?.response?.status === 403
    && error?.response?.data?.detail === "El rol no tiene un ámbito propio de notificaciones";
}

export function notificationDestination(item, user) {
  if (item?.task_id && canAccessRoute(user, "/tareas")) return `/tareas/detalle/${item.task_id}`;
  if (item?.event_type === "commercial_payment_reminder" && canAccessRoute(user, "/notificaciones-alertas")) {
    return "/notificaciones-alertas";
  }
  return null;
}
