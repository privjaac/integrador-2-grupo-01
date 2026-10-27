import test from "node:test";
import assert from "node:assert/strict";
import { can, canAccessRoute } from "./permissions.js";

const user = (role) => ({ role });

test("task navigation gives L2 coordination access without granting task or project permissions", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(canAccessRoute(user(role), "/tareas"), ["L2", "L3", "L4", "L5"].includes(role));
    assert.equal(can(user(role), "tasks", "view"), ["L3", "L4", "L5"].includes(role));
    assert.equal(canAccessRoute(user(role), "/proyectos"), ["L2", "L3"].includes(role));
  }
});

test("task controls follow the explicit designation and work permissions", () => {
  const expected = {
    view: ["L3", "L4", "L5"],
    create: ["L3", "L4"],
    assign: ["L4"],
    start: ["L5"],
    submitReview: ["L5"],
    review: ["L4"],
    reassign: ["L3", "L4"],
    removeExecutor: ["L3", "L4"],
    blockTask: ["L3", "L4"],
    unblockTask: ["L3", "L4"],
    reportIncident: ["L5"],
    designate: ["L2"],
    withdrawCoordination: ["L2"],
    delegate: ["L3"],
    withdrawLeadership: ["L3"],
    manageTeam: ["L4"],
    withdrawTeam: ["L4"],
  };
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    for (const [action, roles] of Object.entries(expected)) {
      assert.equal(can(user(role), "tasks", action), roles.includes(role), `${role} ${action}`);
    }
  }
});
