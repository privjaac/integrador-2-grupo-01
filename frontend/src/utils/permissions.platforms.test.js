import test from "node:test";
import assert from "node:assert/strict";
import { can } from "./permissions.js";

const user = (role, permissions) => ({ role, ...(permissions ? { permissions } : {}) });

test("PB-REP-008 grants management to L1/L2 and read-only access to L3", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(can(user(role), "platforms", "view"), ["L1", "L2", "L3"].includes(role));
    assert.equal(can(user(role), "platforms", "manage"), ["L1", "L2"].includes(role));
  }
});

test("organizational permission subsets are respected", () => {
  assert.equal(can(user("L2", ["platforms.view"]), "platforms", "manage"), false);
  assert.equal(can(user("L3", ["dashboard.view"]), "platforms", "view"), false);
});
