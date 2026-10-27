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
