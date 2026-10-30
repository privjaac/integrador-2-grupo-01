import assert from "node:assert/strict";
import test from "node:test";
import { groupPermissionsByModule, permissionActionLabel, permissionModuleLabel } from "./rolePermissionLabels.js";

test("translates permission keys without changing their technical identifiers", () => {
  assert.equal(permissionModuleLabel("projects.startProject"), "Proyectos");
  assert.equal(permissionActionLabel("projects.startProject"), "Iniciar ejecución");
  assert.equal(permissionActionLabel("clients.resolveChange"), "Resolver solicitudes de cambio");
});

test("groups visible capabilities by module", () => {
  assert.deepEqual(groupPermissionsByModule([
    "projects.view", "projects.startProject", "tasks.view",
  ]), {
    Proyectos: ["projects.view", "projects.startProject"],
    Tareas: ["tasks.view"],
  });
});
