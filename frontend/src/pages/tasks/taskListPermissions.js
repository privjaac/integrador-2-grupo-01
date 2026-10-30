import { can } from "../../utils/permissions.js";

// A temporary L4 substitute can see a task and review it, but only a current
// project leader may assign it. The API remains the final authorization gate.
export function canAssignTaskInList(user, task, projects = []) {
  return can(user, "tasks", "assign")
    && task?.status === "Pendiente"
    && projects.some((project) => (
      Number(project.id) === Number(task.project_id)
      && Number(project.leadership_id) > 0
    ));
}
