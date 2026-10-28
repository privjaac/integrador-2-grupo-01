import test from "node:test";
import assert from "node:assert/strict";
import { canAccessRoute, getAccessibleRoutes, getCreatableRoles } from "./permissions.js";

test("organizational permissions restrict routes while preserving task coordination entry", () => {
  const restricted = { role: "L3", permissions: ["clients.view"] };
  assert.equal(canAccessRoute(restricted, "/proyectos"), false);
  assert.equal(canAccessRoute(restricted, "/clientes"), true);
  assert.deepEqual(getAccessibleRoutes(restricted), ["/clientes"]);
  assert.equal(canAccessRoute({ role: "L3", permissions: ["roles.view"] }, "/roles"), true);

  const coordinator = { role: "L2", permissions: ["tasks.designate"] };
  assert.equal(canAccessRoute(coordinator, "/tareas"), true);
  assert.equal(canAccessRoute(coordinator, "/proyectos"), false);
});

test("legacy level matrix stays scoped and role creation choices use active role IDs", () => {
  assert.equal(canAccessRoute({ role: "L4" }, "/proyectos"), false);
  const choices = getCreatableRoles({ role: "L2" }, [
    { id: 1, hierarchy: 2, is_active: true, name: "Otra L2" },
    { id: 2, hierarchy: 3, is_active: true, name: "L3 operativo" },
    { id: 3, hierarchy: 4, is_active: false, name: "L4 inactivo" },
  ]);
  assert.deepEqual(choices, [{ value: "2", label: "L3 — L3 operativo" }]);
});
