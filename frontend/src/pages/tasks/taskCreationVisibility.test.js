import assert from "node:assert/strict";
import test from "node:test";
import { canCreateTaskInContext } from "./taskCreationVisibility.js";

test("an L4 role without an ordinary leadership scope does not see task creation", () => {
  assert.equal(canCreateTaskInContext({ role: "L4" }, []), false);
});

test("an L4 role can create only when the task context includes an ordinary project scope", () => {
  assert.equal(canCreateTaskInContext({ role: "L4" }, [{ id: 10, leadership_id: 3 }]), true);
});

test("temporary view and review faculties alone do not grant task creation", () => {
  assert.equal(canCreateTaskInContext({
    role: "L4",
    permissions: ["tasks.view", "tasks.review", "tasks.create"],
    temporary_faculties: ["tasks.view", "tasks.review"],
  }, []), false);
  assert.equal(canCreateTaskInContext({ role: "L5" }, [{ id: 10 }]), false);
});
