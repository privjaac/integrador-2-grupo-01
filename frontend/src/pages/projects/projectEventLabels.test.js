import assert from "node:assert/strict";
import test from "node:test";
import {
  cancellationEventLabels, fieldLabels, resumptionEventLabels, valueLabels,
} from "./projectEventLabels.js";

test("los antecedentes de cancelación muestran nombres de actuación comprensibles", () => {
  assert.equal(cancellationEventLabels.evaluacion_tecnica, "Evaluación técnica L3");
  assert.equal(cancellationEventLabels.decision_l1_autorizada, "Autorización excepcional L1");
  assert.equal(cancellationEventLabels.efectiva, "Cancelación efectiva");
});

test("los antecedentes de reanudación distinguen evaluaciones y decisiones", () => {
  assert.equal(resumptionEventLabels.evaluacion_tecnica, "Evaluación de viabilidad L3");
  assert.equal(resumptionEventLabels.decision_comercial_aprobada, "Decisión comercial L2 aprobada");
  assert.equal(resumptionEventLabels.reanudacion_registrada, "Reanudación registrada");
});

test("los datos de auditoría conservan valores y presentan sus campos con etiquetas", () => {
  assert.equal(fieldLabels.l1_intervention_required, "Requiere intervención excepcional L1");
  assert.equal(fieldLabels.effectivity_conditions, "Condiciones de efectividad");
  assert.equal(valueLabels.authority["L2 ordinary cancellation"], "Cancelación ordinaria L2");
  assert.equal(valueLabels.scope_type.project_full, "Proyecto completo");
});
