import { can } from "../../utils/permissions.js";

// A role capability is necessary but is not enough: creation needs at least
// one project in the actor's ordinary creation scope from the task context.
export function canCreateTaskInContext(user, projects = []) {
  return can(user, "tasks", "create") && projects.length > 0;
}
