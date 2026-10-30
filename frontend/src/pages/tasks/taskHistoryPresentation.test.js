import assert from "node:assert/strict";
import test from "node:test";
import { taskExecutorChange } from "./taskHistoryPresentation.js";

test("status events carrying the current executor as context are not shown as assignment changes", () => {
  for (const event_type of ["resultado_presentado", "observada", "correccion_iniciada", "aprobada_revision"]) {
    assert.equal(taskExecutorChange({ event_type, assignee_id: 7, assignee_name: "Demo L5 B5" }), null);
  }
});

test("assignment, reassignment and removal events show only recorded executor transitions", () => {
  assert.deepEqual(taskExecutorChange({ event_type: "asignada", assignee_id: 7, assignee_name: "Demo L5 B5" }), {
    previousName: "Sin asignar", nextName: "Demo L5 B5",
  });
  assert.deepEqual(taskExecutorChange({
    event_type: "ejecutor_reasignado", previous_assignee_id: 7, previous_assignee_name: "Demo L5 B5",
    assignee_id: 9, assignee_name: "Otro L5",
  }), { previousName: "Demo L5 B5", nextName: "Otro L5" });
  assert.deepEqual(taskExecutorChange({
    event_type: "ejecutor_retirado", previous_assignee_id: 7, previous_assignee_name: "Demo L5 B5",
  }), { previousName: "Demo L5 B5", nextName: "Sin asignar" });
});
