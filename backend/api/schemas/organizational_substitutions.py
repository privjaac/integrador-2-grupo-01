from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from api.schemas.safe_input import SafeInputModel


class OrganizationalSubstitutionCreate(SafeInputModel):
    coordination_id: int
    leadership_id: int | None = None
    absent_level: Literal['L3', 'L4']
    absent_person_id: int
    substitute_id: int | None = None
    reason: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    faculties: list[str] = Field(default_factory=list)
    valid_from: datetime
    valid_until: datetime

    @field_validator('reason', 'evidence', 'scope')
    @classmethod
    def require_substitution_details(cls, value):
        if not value.strip():
            raise ValueError('La sustitución requiere motivo, evidencia y ámbito')
        return value.strip()

    @field_validator('valid_from', 'valid_until')
    @classmethod
    def require_substitution_timezone(cls, value):
        if value.utcoffset() is None:
            raise ValueError('La vigencia debe incluir zona horaria')
        return value

    @model_validator(mode='after')
    def validate_period_and_faculties(self):
        if self.valid_until <= self.valid_from:
            raise ValueError('La vigencia final debe ser posterior a la inicial')
        if len(self.faculties) != len(set(self.faculties)):
            raise ValueError('No se admiten facultades duplicadas')
        return self
