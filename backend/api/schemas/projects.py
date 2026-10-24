from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from api.schemas.safe_input import SafeInputModel


class ProjectCreate(SafeInputModel):
    client_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    objective: Optional[str] = None
    scope: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    client_id: int
    client_name: str
    name: str
    objective: Optional[str]
    scope: Optional[str]
    status: Literal['Planificado', 'En progreso', 'En pausa', 'Completado', 'Cancelado']


class ProjectListItem(ProjectResponse):
    pass
