import test from "node:test";
import assert from "node:assert/strict";
import { canAccessRoute, getAccessibleRoutes, getCreatableRoles, getInitialRoute } from "./permissions.js";

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

test("login chooses a route allowed by each role and falls back from a denied requested URL", () => {
  const users = {
    L1: { role: "L1", permissions: ["clients.view"] },
    L2: { role: "L2", permissions: ["clients.view"] },
    L3: { role: "L3", permissions: ["clients.view"] },
    L4: { role: "L4", permissions: ["tasks.view", "users.view", "roles.view"] },
    L5: { role: "L5", permissions: ["tasks.view", "roles.view"] },
  };
  for (const role of ["L1", "L2", "L3"]) {
    assert.equal(getInitialRoute(users[role]), "/clientes");
  }
  for (const role of ["L4", "L5"]) {
    assert.equal(canAccessRoute(users[role], "/clientes"), false);
    assert.equal(getInitialRoute(users[role]), "/tareas");
    assert.equal(getInitialRoute(users[role], "/clientes/DEMO"), "/tareas");
  }
  assert.equal(getInitialRoute({ role: "L5", permissions: [] }), null);
});
