import test from "node:test";
import assert from "node:assert/strict";
import { can, canAccessRoute } from "./permissions.js";

test("F2-01: effective capabilities restrict project access without exceeding role limits", () => {
  assert.equal(can({ role: "L2", permissions: [] }, "projects", "view"), false);
  assert.equal(can({ role: "L2", permissions: ["projects.view"] }, "projects", "create"), false);
  assert.equal(can({ role: "L3", permissions: ["projects.view", "projects.create"] }, "projects", "create"), false);
  assert.equal(can(null, "projects", "view"), false);
  assert.equal(can(null, "projects", "create"), false);
  assert.equal(canAccessRoute(null, "/proyectos"), false);
});
