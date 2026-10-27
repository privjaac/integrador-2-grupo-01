import test from "node:test";
import assert from "node:assert/strict";
import { can, canAccessRoute, canManageCollaborator, getCreatableRoles } from "./permissions.js";

const user = (role, id = 100) => ({ role, id });

test("PB-COL list and detail access is explicit for L1 through L4", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    const expected = ["L1", "L2", "L3", "L4"].includes(role);
    assert.equal(can(user(role), "users", "view"), expected);
    assert.equal(canAccessRoute(user(role), "/usuarios"), expected);
  }
});

test("PB-COL editing and status actions are separate SA/SM competencies", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    const expected = ["L1", "L2"].includes(role);
    assert.equal(can(user(role), "users", "edit"), expected);
    assert.equal(can(user(role), "users", "activate"), expected);
    assert.equal(can(user(role), "users", "deactivate"), expected);
  }
});

test("creation remains separately limited to roles permitted by each level", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(can(user(role), "users", "create"), role !== "L5");
  }
  assert.deepEqual(getCreatableRoles(user("L1")).map((role) => role.value), ["L1", "L2", "L3", "L4", "L5"]);
  assert.deepEqual(getCreatableRoles(user("L2")).map((role) => role.value), ["L3", "L4", "L5"]);
  assert.deepEqual(getCreatableRoles(user("L3")).map((role) => role.value), ["L4", "L5"]);
  assert.deepEqual(getCreatableRoles(user("L4")).map((role) => role.value), ["L5"]);
});

test("administrative controls require a distinct non-L1 target and SA/SM actor", () => {
  assert.equal(canManageCollaborator(user("L1", 1), { id: 2, role_level: "L1" }), false);
  assert.equal(canManageCollaborator(user("L1", 1), { id: 3, role_level: "L3" }), true);
  assert.equal(canManageCollaborator(user("L2", 2), { id: 8, role_level: "L2" }), true);
  assert.equal(canManageCollaborator(user("L2", 2), { id: 4, role: "L3" }), true);
  assert.equal(canManageCollaborator(user("L2", 2), { id: 5, role_level: "L2" }), true);
  assert.equal(canManageCollaborator(user("L2", 2), { id: 2, role_level: "L5" }), false);
  assert.equal(canManageCollaborator(user("L3", 3), { id: 6, role_level: "L5" }), false);
  assert.equal(canManageCollaborator(user("L4", 4), { id: 7, role_level: "L5" }), false);
});
