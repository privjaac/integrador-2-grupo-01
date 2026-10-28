import test from "node:test";
import assert from "node:assert/strict";

import { can, canAccessRoute } from "./permissions.js";

test("collaborator payments are limited to SA and SM and require explicit role capabilities", () => {
  for (const role of ["L1", "L2"]) {
    assert.equal(can({ role }, "collaboratorPayments", "view"), true);
    assert.equal(can({ role }, "collaboratorPayments", "record"), true);
    assert.equal(canAccessRoute({ role }, "/colaboradores/pagos"), true);
  }
  for (const role of ["L3", "L4", "L5"]) {
    assert.equal(can({ role }, "collaboratorPayments", "view"), false);
    assert.equal(can({ role }, "collaboratorPayments", "record"), false);
    assert.equal(canAccessRoute({ role }, "/colaboradores/pagos"), false);
  }
  assert.equal(can({ role: "L2", permissions: [] }, "collaboratorPayments", "view"), false);
  assert.equal(can({ role: "L2", permissions: ["collaboratorPayments.view"] }, "collaboratorPayments", "record"), false);
});
