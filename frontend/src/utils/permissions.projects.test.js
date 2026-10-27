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

test("B4-09 grants only the technical validation transition to L3", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(can(user(role), "projects", "enterTechnicalValidation"), role === "L3");
  }
});

test("B4-09 commercial habilitation belongs to L2 and project start to L3", () => {
  for (const role of ["L1", "L2", "L3", "L4", "L5"]) {
    assert.equal(can(user(role), "projects", "authorizeProjectStart"), role === "L2");
    assert.equal(can(user(role), "projects", "startProject"), role === "L3");
  }
});
