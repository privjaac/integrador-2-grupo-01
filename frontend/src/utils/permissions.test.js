import test from "node:test";
import assert from "node:assert/strict";
import { can, canAccessRoute } from "./permissions.js";

test("F2-01: L2 puede consultar y crear proyectos", () => {
  const user = { role: "L2" };
  assert.equal(can(user, "projects", "view"), true);
  assert.equal(can(user, "projects", "create"), true);
  assert.equal(canAccessRoute(user, "/proyectos"), true);
});

test("F2-01: L3 solo puede consultar proyectos", () => {
  const user = { role: "L3" };
  assert.equal(can(user, "projects", "view"), true);
  assert.equal(can(user, "projects", "create"), false);
  assert.equal(canAccessRoute(user, "/proyectos"), true);
});

test("F2-01: L1, L4 y L5 no obtienen permisos de proyectos", () => {
  for (const role of ["L1", "L4", "L5"]) {
    assert.equal(can({ role }, "projects", "view"), false, role);
    assert.equal(can({ role }, "projects", "create"), false, role);
    assert.equal(canAccessRoute({ role }, "/proyectos"), false, role);
  }
});

test("F2-01: invitado no accede a proyectos", () => {
  assert.equal(can(null, "projects", "view"), false);
  assert.equal(can(null, "projects", "create"), false);
  assert.equal(canAccessRoute(null, "/proyectos"), false);
});
