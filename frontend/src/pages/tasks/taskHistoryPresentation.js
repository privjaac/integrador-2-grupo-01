const EXECUTOR_CHANGE_EVENTS = new Set([
  "creada", "asignada", "ejecutor_reasignado", "ejecutor_retirado",
]);

export function taskExecutorChange(event) {
  if (!EXECUTOR_CHANGE_EVENTS.has(event?.event_type)) return null;
  if (event.previous_assignee_id === event.assignee_id) return null;
  return {
    previousName: event.previous_assignee_name || "Sin asignar",
    nextName: event.assignee_name || "Sin asignar",
  };
}
