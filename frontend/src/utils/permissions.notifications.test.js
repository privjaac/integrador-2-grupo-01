import test from "node:test";
import assert from "node:assert/strict";
import { can, canAccessRoute } from "./permissions.js";

test("task deadline settings are available only to L1 and L2 with the capability", () => {
  for (const role of ["L1", "L2"]) {
    const user = { role };
    assert.equal(can(user, "notifications", "configure"), true);
    assert.equal(canAccessRoute(user, "/notificaciones/configuracion"), true);
  }
  for (const role of ["L3", "L4", "L5"]) {
    const user = { role };
    assert.equal(can(user, "notifications", "configure"), false);
    assert.equal(canAccessRoute(user, "/notificaciones/configuracion"), false);
  }
  assert.equal(canAccessRoute({ role: "L2", permissions: [] }, "/notificaciones/configuracion"), false);
  assert.equal(canAccessRoute({ role: "L2", permissions: ["notifications.configure"] }, "/notificaciones/configuracion"), true);
});
