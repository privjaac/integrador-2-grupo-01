export const fieldLabels = {
  affected_tasks_assessment: "Impacto en tareas",
  authority: "Autoridad registrada",
  automatic_task_or_financial_effects: "Efectos automáticos en tareas o finanzas",
  cancelled_scope: "Alcance de cancelación",
  cancellation_effectivity_event_id: "Evento de efectividad asociado",
  commercial_consequences: "Consecuencias comerciales",
  conditions: "Condiciones",
  conditions_satisfied: "Condiciones acreditadas",
  decision_event_id: "Evento de decisión asociado",
  effectivity_conditions: "Condiciones de efectividad",
  feasibility: "Viabilidad de reanudación",
  is_urgent: "Urgente",
  l1_escalation_required: "Requiere escalamiento a L1",
  l1_exception_reason: "Circunstancia excepcional L1",
  l1_intervention_required: "Requiere intervención excepcional L1",
  obligations_assessment: "Obligaciones y actividades residuales",
  pending_work: "Trabajo pendiente",
  planned_effective_at: "Fecha prevista de efectividad",
  project_status_preserved: "Estado del proyecto conservado",
  received_at: "Fecha de recepción",
  requests_l1_intervention: "Solicita intervención L1",
  scope_type: "Tipo de alcance",
  source: "Origen del registro",
  source_origin: "Origen de la solicitud",
  source_reference: "Referencia de origen",
  task_snapshot: "Tareas consideradas en la evaluación",
  within_l2_competence: "Dentro de la competencia ordinaria L2",
};

export const valueLabels = {
  authority: {
    "L1 exceptional cancellation": "Cancelación excepcional L1",
    "L1 exceptional resumption": "Reanudación excepcional L1",
    "L2 ordinary cancellation": "Cancelación ordinaria L2",
  },
  scope_type: { project_full: "Proyecto completo" },
  source: { evaluacion_comercial_l2: "Evaluación comercial L2" },
};

export const cancellationEventLabels = {
  solicitada: "Solicitud registrada",
  evaluacion_tecnica: "Evaluación técnica L3",
  autorizada: "Autorización ordinaria L2",
  denegada: "Denegación L2",
  decision_l1_autorizada: "Autorización excepcional L1",
  decision_l1_denegada: "Denegación excepcional L1",
  escalamiento_l1: "Escalamiento a L1",
  evaluacion_comercial: "Evaluación comercial L2",
  efectiva: "Cancelación efectiva",
};

export const resumptionEventLabels = {
  evaluacion_tecnica: "Evaluación de viabilidad L3",
  decision_comercial_aprobada: "Decisión comercial L2 aprobada",
  decision_comercial_denegada: "Decisión comercial L2 denegada",
  decision_l1_aprobada: "Decisión excepcional L1 aprobada",
  decision_l1_denegada: "Decisión excepcional L1 denegada",
  reanudacion_registrada: "Reanudación registrada",
};
