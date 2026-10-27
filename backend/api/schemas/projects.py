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
