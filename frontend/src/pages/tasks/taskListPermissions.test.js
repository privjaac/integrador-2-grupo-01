import test from "node:test";
import assert from "node:assert/strict";
import { canAssignTaskInList } from "./taskListPermissions.js";

const pendingTask = { id: 7, project_id: 12, status: "Pendiente" };

test("assignment is shown to an L4 leader for a pending task in their project", () => {
  assert.equal(
    canAssignTaskInList({ role: "L4" }, pendingTask, [{ id: 12, leadership_id: 3 }]),
    true,
  );
});

test("assignment is hidden from a substitute without a project leadership", () => {
  assert.equal(canAssignTaskInList({ role: "L4" }, pendingTask, []), false);
});

test("assignment is hidden outside the leader's project or task state", () => {
  assert.equal(
    canAssignTaskInList({ role: "L4" }, pendingTask, [{ id: 13, leadership_id: 3 }]),
    false,
  );
  assert.equal(
    canAssignTaskInList(
      { role: "L4" },
      { ...pendingTask, status: "En proceso" },
      [{ id: 12, leadership_id: 3 }],
    ),
    false,
  );
  assert.equal(
    canAssignTaskInList({ role: "L3" }, pendingTask, [{ id: 12, leadership_id: 3 }]),
    false,
  );
});
