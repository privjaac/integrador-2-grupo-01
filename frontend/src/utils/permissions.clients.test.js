import test from "node:test";
import assert from "node:assert/strict";
import { can, canAccessRoute } from "./permissions.js";

const user = (role) => ({ role });

test("B4-12 restricts CRM read and create to approved roles", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(can(user(role), "clients", "view"), ["L1", "L2", "L3"].includes(role));
    assert.equal(can(user(role), "clients", "create"), ["L1", "L2"].includes(role));
    assert.equal(canAccessRoute(user(role), "/clientes"), ["L1", "L2", "L3"].includes(role));
  }
});

test("CRM changes can be requested by L1/L2/L3; review stays with L1/L2", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(can(user(role), "clients", "edit"), ["L1", "L2", "L3"].includes(role));
    assert.equal(can(user(role), "clients", "delete"), ["L1", "L2", "L3"].includes(role));
    assert.equal(can(user(role), "clients", "resolveChange"), ["L1", "L2"].includes(role));
    assert.equal(can(user(role), "clients", "resolveDeactivation"), role === "L1");
  }
});
