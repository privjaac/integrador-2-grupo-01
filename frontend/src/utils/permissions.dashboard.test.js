import test from "node:test";
import assert from "node:assert/strict";
import { can, canAccessRoute } from "./permissions.js";

const user = (role) => ({ role });

test("B4-15 dashboard access follows report roles and excludes L4/L5", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    const allowed = ["L1", "L2", "L3"].includes(role);
    assert.equal(can(user(role), "dashboard", "view"), allowed);
    assert.equal(canAccessRoute(user(role), "/dashboard"), allowed);
  }
});
