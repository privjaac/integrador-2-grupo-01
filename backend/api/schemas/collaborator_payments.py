from decimal import Decimal
from datetime import date
from typing import Annotated

from pydantic import ConfigDict, Field, field_validator

from api.schemas.safe_input import SafeInputModel


class CollaboratorPaymentWrite(SafeInputModel):
    model_config = ConfigDict(extra='forbid')

    collaborator_id: int = Field(gt=0)
    payment_date: date
    amount: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    concept: str = Field(min_length=1, max_length=150)
    observation: str = Field(default='', max_length=300)

    @field_validator('concept')
    @classmethod
    def normalize_concept(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('El concepto es obligatorio')
        return value

    @field_validator('observation')
    @classmethod
    def normalize_observation(cls, value):
        return value.strip()
