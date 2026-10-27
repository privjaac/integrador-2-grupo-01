from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

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
