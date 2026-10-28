from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from api.schemas.safe_input import SafeInputModel


class ProjectCreate(SafeInputModel):
    client_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    objective: Optional[str] = None
    scope: Optional[str] = None
    status: Optional[Literal[
        'Planificado', 'En ejecución', 'En validación técnica',
        'Listo para entrega', 'Entregado',
    ]] = None


class ProjectResponse(BaseModel):
    id: int
    client_id: int
    client_name: str
    name: str
    objective: Optional[str]
    scope: Optional[str]
    status: Literal[
        'Planificado', 'En ejecución', 'En validación técnica',
        'Listo para entrega', 'Entregado',
    ]
    events: list['ProjectEventResponse'] = Field(default_factory=list)


class ProjectEventResponse(BaseModel):
    event_type: str
    actor_id: int
    actor_name: str
    previous_status: str
    new_status: str
    reason: str
    evidence: str
    occurred_at: datetime
    commercial_authorization_id: int | None = None
    technical_evaluation_id: int | None = None
    delivery_authorization_id: int | None = None
    delivery_record_ids: list[int] = Field(default_factory=list)


class ProjectListItem(ProjectResponse):
    pass


class ProjectValidationReadiness(SafeInputModel):
    scope_within_current_commitment: bool
    criteria_identifiable: bool
    results_and_evidence_available: bool
    validation_conditions_ready: bool
    responsible_parties_identified: bool
    dependencies_ready: bool
    pending_obligations_assessed: bool
    evidence: str = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator('*')
    @classmethod
    def reject_blank_readiness_evidence(cls, value):
        if isinstance(value, str) and not value.strip():
            raise ValueError('La evidencia de preparación no puede estar vacía')
        return value


class ProjectExecutionReturn(SafeInputModel):
    additional_execution_required: bool
    materially_affects_validation: bool
    within_current_commitment: bool
    evidence: str = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator('evidence', 'reason')
    @classmethod
    def reject_blank_return_details(cls, value):
        if not value.strip():
            raise ValueError('La evidencia y el motivo no pueden estar vacíos')
        return value


class ProjectTaskClassificationInput(SafeInputModel):
    is_mandatory: bool
    reason: str = Field(min_length=1)

    @field_validator('reason')
    @classmethod
    def reject_blank_classification_reason(cls, value):
        if not value.strip():
            raise ValueError('La justificación no puede estar vacía')
        return value


class OptionalTaskAssessment(SafeInputModel):
    task_id: int = Field(gt=0)
    impact_assessment: str = Field(min_length=1)
    evidence: str = Field(min_length=1)

    @field_validator('impact_assessment', 'evidence')
    @classmethod
    def reject_blank_optional_assessment(cls, value):
        if not value.strip():
            raise ValueError('La evaluación y evidencia de tarea opcional no pueden estar vacías')
        return value


class ProjectTechnicalEvaluationInput(SafeInputModel):
    satisfactory: bool
    technical_enablement_status: Literal['Vigente', 'En revisión', 'No vigente']
    ordinary_close_valid: bool
    obligations_compatible: bool
    result_summary: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    ordinary_close_evidence: str = Field(min_length=1)
    obligations_assessment: str = Field(min_length=1)
    optional_task_assessments: list[OptionalTaskAssessment] = Field(default_factory=list)
    validated_versions: list[str] = Field(default_factory=list)

    @field_validator('result_summary', 'evidence', 'ordinary_close_evidence', 'obligations_assessment')
    @classmethod
    def reject_blank_evaluation_details(cls, value):
        if not value.strip():
            raise ValueError('Los detalles de evaluación no pueden estar vacíos')
        return value

    @model_validator(mode='after')
    def reject_duplicate_optional_tasks(self):
        task_ids = [item.task_id for item in self.optional_task_assessments]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError('Una tarea opcional no puede evaluarse más de una vez')
        return self

    @field_validator('validated_versions')
    @classmethod
    def normalize_validated_versions(cls, values):
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError('Cada versión técnica debe identificarse expresamente')
        if len({value.casefold() for value in normalized}) != len(normalized):
            raise ValueError('Una versión técnica no puede repetirse')
        return normalized

    @model_validator(mode='after')
    def enforce_consistent_technical_close(self):
        if self.ordinary_close_valid and (not self.satisfactory or not self.obligations_compatible):
            raise ValueError('El cierre ordinario no puede ser válido con resultado insatisfactorio u obligaciones incompatibles')
        return self


class ProjectDeliveryAuthorizationCreate(SafeInputModel):
    authorized_scope: str = Field(min_length=1)
    effectivity_conditions: str = Field(min_length=1)
    conditions_accredited: bool
    evidence_reference: str = Field(min_length=1, max_length=300)
    effective_at: datetime
    expires_at: datetime | None = None
    replaces_authorization_id: int | None = Field(default=None, gt=0)
    replacement_reason: str | None = None

    @field_validator('authorized_scope', 'effectivity_conditions', 'evidence_reference')
    @classmethod
    def reject_blank_delivery_authorization_details(cls, value):
        if not value.strip():
            raise ValueError('Los datos de habilitación de entrega no pueden estar vacíos')
        return value

    @field_validator('effective_at', 'expires_at')
    @classmethod
    def require_aware_delivery_dates(cls, value):
        if value is not None and value.utcoffset() is None:
            raise ValueError('La fecha debe incluir zona horaria')
        return value

    @field_validator('replacement_reason')
    @classmethod
    def reject_blank_delivery_replacement_reason(cls, value):
        if value is not None and not value.strip():
            raise ValueError('El motivo de sustitución no puede estar vacío')
        return value


class ProjectReadyForDeliveryInput(SafeInputModel):
    delivery_authorization_id: int = Field(gt=0)
    reason: str = Field(min_length=1)

    @field_validator('reason')
    @classmethod
    def reject_blank_ready_reason(cls, value):
        if not value.strip():
            raise ValueError('El motivo no puede estar vacío')
        return value


class ProjectDeliveryCreate(SafeInputModel):
    delivery_type: Literal['parcial', 'integral']
    preparation_authorization_id: int = Field(gt=0)
    scope: str = Field(min_length=1)
    scope_within_authorization: bool
    covers_project_scope: bool
    version_reference: str = Field(min_length=1, max_length=200)
    recipient: str = Field(min_length=1, max_length=200)
    delivery_method: str = Field(min_length=1)
    performed_by: str = Field(min_length=1, max_length=200)
    evidence_reference: str = Field(min_length=1, max_length=300)
    occurred_at: datetime

    @field_validator('scope', 'version_reference', 'recipient', 'delivery_method', 'performed_by', 'evidence_reference')
    @classmethod
    def reject_blank_delivery_fields(cls, value):
        if not value.strip():
            raise ValueError('La constancia de entrega no puede contener campos vacíos')
        return value.strip()

    @field_validator('occurred_at')
    @classmethod
    def require_aware_delivery_time(cls, value):
        if value.utcoffset() is None:
            raise ValueError('La fecha efectiva de entrega debe incluir zona horaria')
        return value

    @model_validator(mode='after')
    def validate_delivery_scope_kind(self):
        if not self.scope_within_authorization:
            raise ValueError('L2 debe confirmar que la entrega está dentro del alcance autorizado')
        if (self.delivery_type == 'integral') != self.covers_project_scope:
            raise ValueError('La cobertura integral debe corresponder al tipo de entrega')
        return self


class ProjectDeliveryTechnicalReviewInput(SafeInputModel):
    version_reference: str = Field(min_length=1, max_length=200)
    satisfactory: bool
    technical_enablement_status: Literal['Vigente', 'En revisión', 'No vigente']
    result_summary: str = Field(min_length=1)
    evidence: str = Field(min_length=1)

    @field_validator('version_reference', 'result_summary', 'evidence')
    @classmethod
    def reject_blank_delivery_review(cls, value):
        if not value.strip():
            raise ValueError('La revisión técnica requiere resultado y evidencia')
        return value.strip()


class ProjectDeliveryFormalizeInput(SafeInputModel):
    delivery_ids: list[int] = Field(min_length=1)
    integral_coverage_confirmed: bool
    coverage_evidence: str = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator('coverage_evidence', 'reason')
    @classmethod
    def reject_blank_formalization_details(cls, value):
        if not value.strip():
            raise ValueError('La formalización requiere fundamento y evidencia de cobertura')
        return value.strip()

    @model_validator(mode='after')
    def reject_duplicate_deliveries(self):
        if len(self.delivery_ids) != len(set(self.delivery_ids)):
            raise ValueError('Una entrega no puede seleccionarse más de una vez')
        if not self.integral_coverage_confirmed:
            raise ValueError('L2 debe acreditar que las entregas cubren integralmente el alcance')
        return self


class ProjectCommercialAuthorizationCreate(SafeInputModel):
    authorized_scope: str = Field(min_length=1)
    commitment_reference: str = Field(min_length=1, max_length=200)
    start_conditions: str = Field(min_length=1)
    start_conditions_accredited: bool
    evidence_reference: str = Field(min_length=1, max_length=300)
    effective_at: datetime
    expires_at: datetime | None = None
    replaces_authorization_id: int | None = Field(default=None, gt=0)
    replacement_reason: str | None = None

    @field_validator('authorized_scope', 'commitment_reference', 'start_conditions', 'evidence_reference')
    @classmethod
    def reject_blank_authorization_details(cls, value):
        if not value.strip():
            raise ValueError('El dato de habilitación comercial no puede estar vacío')
        return value

    @field_validator('effective_at', 'expires_at')
    @classmethod
    def require_timezone_aware_dates(cls, value):
        if value is not None and value.utcoffset() is None:
            raise ValueError('La fecha debe incluir zona horaria')
        return value

    @field_validator('replacement_reason')
    @classmethod
    def reject_blank_replacement_reason(cls, value):
        if value is not None and not value.strip():
            raise ValueError('El motivo de sustitución no puede estar vacío')
        return value


class ProjectCommercialAuthorizationWithdrawal(SafeInputModel):
    reason: str = Field(min_length=1)


class ProjectStartReadiness(SafeInputModel):
    commercial_authorization_id: int = Field(gt=0)
    initial_activities: str = Field(min_length=1)
    initial_scope_within_authorization: bool
    responsible_parties_identified: bool
    resources_ready: bool
    dependencies_ready: bool
    restrictions_assessed: bool
    reason: str = Field(min_length=1)
    evidence: str = Field(min_length=1)

    @field_validator('initial_activities', 'reason', 'evidence')
    @classmethod
    def reject_blank_start_details(cls, value):
        if not value.strip():
            raise ValueError('El dato de preparación técnica no puede estar vacío')
        return value


class ProjectCancellationCreate(SafeInputModel):
    cancelled_scope: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    evidence: str = Field(min_length=1)

    @field_validator('cancelled_scope', 'reason', 'evidence')
    @classmethod
    def reject_blank_cancellation_details(cls, value):
        if not value.strip():
            raise ValueError('La solicitud de cancelación requiere alcance, motivo y evidencia')
        return value.strip()


class ProjectCancellationTechnicalEvaluation(SafeInputModel):
    affected_tasks_assessment: str = Field(min_length=1)
    obligations_assessment: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    l1_intervention_required: bool
    l1_exception_reason: str | None = None

    @field_validator('affected_tasks_assessment', 'obligations_assessment', 'evidence')
    @classmethod
    def reject_blank_technical_cancellation_details(cls, value):
        if not value.strip():
            raise ValueError('La evaluación técnica debe documentar tareas, obligaciones y evidencia')
        return value.strip()

    @field_validator('l1_exception_reason')
    @classmethod
    def normalize_l1_exception_reason(cls, value):
        if value is not None and not value.strip():
            raise ValueError('La excepción técnica requiere una explicación no vacía')
        return value.strip() if value is not None else value

    @model_validator(mode='after')
    def validate_l1_exception(self):
        if self.l1_intervention_required and not self.l1_exception_reason:
            raise ValueError('Una intervención L1 requerida debe documentar la circunstancia técnica')
        if not self.l1_intervention_required and self.l1_exception_reason:
            raise ValueError('No se puede registrar una excepción técnica si no requiere L1')
        return self


class ProjectCancellationCommercialEvaluation(SafeInputModel):
    within_l2_competence: bool
    commercial_consequences: str = Field(min_length=1)
    effectivity_conditions: str = Field(min_length=1)
    evidence: str = Field(min_length=1)

    @field_validator('commercial_consequences', 'effectivity_conditions', 'evidence')
    @classmethod
    def reject_blank_commercial_evaluation(cls, value):
        if not value.strip():
            raise ValueError('La evaluación comercial requiere consecuencias, condiciones y evidencia')
        return value.strip()


class ProjectCancellationL1Escalation(SafeInputModel):
    is_urgent: Literal[True]
    reason: str = Field(min_length=1)
    source_origin: str = Field(min_length=1, max_length=200)
    source_reference: str = Field(min_length=1, max_length=200)
    received_at: datetime
    evidence: str = Field(min_length=1)

    @field_validator('reason', 'source_origin', 'source_reference', 'evidence')
    @classmethod
    def reject_blank_escalation_details(cls, value):
        if not value.strip():
            raise ValueError('El escalamiento requiere procedencia, referencia, motivo y evidencia verificables')
        return value.strip()

    @field_validator('received_at')
    @classmethod
    def require_aware_escalation_date(cls, value):
        if value.utcoffset() is None:
            raise ValueError('La fecha de recepción debe incluir zona horaria')
        return value


class ProjectCancellationDecision(SafeInputModel):
    authorized: bool
    reason: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    commercial_consequences: str | None = None
    effectivity_conditions: str | None = None
    planned_effective_at: datetime | None = None

    @field_validator('reason', 'evidence')
    @classmethod
    def reject_blank_cancellation_decision_details(cls, value):
        if not value.strip():
            raise ValueError('La decisión debe incluir motivo y evidencia')
        return value.strip()

    @field_validator('commercial_consequences', 'effectivity_conditions')
    @classmethod
    def normalize_optional_cancellation_details(cls, value):
        if value is not None and not value.strip():
            raise ValueError('El dato no puede estar vacío')
        return value.strip() if value is not None else value

    @field_validator('planned_effective_at')
    @classmethod
    def require_aware_cancellation_date(cls, value):
        if value is not None and value.utcoffset() is None:
            raise ValueError('La fecha efectiva debe incluir zona horaria')
        return value

    @model_validator(mode='after')
    def validate_cancellation_decision(self):
        if self.authorized and not all((
            self.commercial_consequences, self.effectivity_conditions, self.planned_effective_at,
        )):
            raise ValueError('Autorizar requiere evaluación comercial, condiciones y fecha prevista de efectividad')
        if not self.authorized and (self.commercial_consequences or self.effectivity_conditions or self.planned_effective_at):
            raise ValueError('Una denegación no puede registrar autorización ni condiciones de efectividad')
        return self


class ProjectCancellationEffectivity(SafeInputModel):
    conditions_satisfied: bool
    reason: str = Field(min_length=1)
    evidence: str = Field(min_length=1)

    @field_validator('reason', 'evidence')
    @classmethod
    def reject_blank_effectivity_details(cls, value):
        if not value.strip():
            raise ValueError('La efectividad requiere motivo y evidencia')
        return value.strip()

    @model_validator(mode='after')
    def require_satisfied_conditions(self):
        if not self.conditions_satisfied:
            raise ValueError('La cancelación no puede hacerse efectiva con condiciones pendientes')
        return self
