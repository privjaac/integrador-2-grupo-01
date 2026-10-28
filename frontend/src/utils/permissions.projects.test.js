import test from "node:test";
import assert from "node:assert/strict";
import { can, canAccessRoute } from "./permissions.js";

const user = (role) => ({ role });

test("F2-01 grants project navigation only to L2 and L3", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(canAccessRoute(user(role), "/proyectos"), ["L2", "L3"].includes(role));
    assert.equal(can(user(role), "projects", "view"), ["L2", "L3"].includes(role));
  }
});

test("F2-01 shows create permission only to L2", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(can(user(role), "projects", "create"), role === "L2");
  }
});

test("B4-09 and B4-10 grant technical validation transitions only to L3", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(can(user(role), "projects", "enterTechnicalValidation"), role === "L3");
    assert.equal(can(user(role), "projects", "returnProjectToExecution"), role === "L3");
  }
});

test("B4-09 commercial habilitation belongs to L2 and project start to L3", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(can(user(role), "projects", "authorizeProjectStart"), role === "L2");
    assert.equal(can(user(role), "projects", "startProject"), role === "L3");
    assert.equal(can(user(role), "projects", "associateContractedServices"), role === "L3");
  }
});

test("B4-10 task classification, technical evaluation and delivery authorization stay within approved levels", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(can(user(role), "projects", "classifyProjectTasks"), role === "L3");
    assert.equal(can(user(role), "projects", "evaluateProjectClosure"), role === "L3");
    assert.equal(can(user(role), "projects", "markProjectReadyForDelivery"), role === "L3");
    assert.equal(can(user(role), "projects", "authorizeProjectDelivery"), role === "L2");
  }
});

test("B4-23 ordinary project cancellation is limited to its approved capabilities", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(can(user(role), "projects", "requestProjectCancellation"), role === "L2");
    assert.equal(can(user(role), "projects", "evaluateProjectCancellation"), role === "L3");
    assert.equal(can(user(role), "projects", "resolveProjectCancellation"), role === "L2");
  }
  assert.equal(can({ role: "L2", permissions: ["projects.view"] }, "projects", "requestProjectCancellation"), false);
  assert.equal(can({ role: "L3", permissions: ["projects.view"] }, "projects", "evaluateProjectCancellation"), false);
});

test("B4-28 and B4-29 expose substitution and exceptional work only to their approved levels", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(can(user(role), "projects", "manageSubstitutions"), ["L1", "L3"].includes(role));
    assert.equal(can(user(role), "projects", "viewSubstitutions"), ["L1", "L2", "L3"].includes(role));
    assert.equal(can(user(role), "projects", "resolveExceptionalCancellation"), role === "L1");
    assert.equal(can(user(role), "projects", "resolveExceptionalResumption"), role === "L1");
  }
  assert.equal(canAccessRoute(user("L1"), "/proyectos/excepcionales"), true);
  assert.equal(canAccessRoute(user("L2"), "/proyectos/excepcionales"), false);
  assert.equal(canAccessRoute(user("L3"), "/proyectos/excepcionales"), false);
  assert.equal(canAccessRoute(user("L1"), "/proyectos"), false);
});
