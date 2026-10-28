from typing import Annotated

from pydantic import Field, field_validator

from api.schemas.safe_input import SafeInputModel


PositiveDay = Annotated[int, Field(ge=1, le=32767)]


class CommercialNoticeConfigUpdate(SafeInputModel):
    anticipation_days: list[PositiveDay] = Field(min_length=1)
    is_active: bool

    @field_validator('anticipation_days')
    @classmethod
    def days_must_be_unique(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('No se permiten días de anticipación duplicados')
        return sorted(value, reverse=True)
