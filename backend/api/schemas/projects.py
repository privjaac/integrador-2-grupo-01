from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

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


class ProjectListItem(ProjectResponse):
    pass
