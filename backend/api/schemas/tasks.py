from typing import Literal

from pydantic import Field

from api.schemas.safe_input import SafeInputModel


class TaskCreate(SafeInputModel):
    project_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: Literal['Pendiente', 'Asignada'] = 'Pendiente'
    assignee_id: int | None = Field(default=None, gt=0)


class TaskAssign(SafeInputModel):
    assignee_id: int = Field(gt=0)


class TaskSubmission(SafeInputModel):
    result_text: str = Field(min_length=1)


class TaskReview(SafeInputModel):
    resolution: Literal['Observada', 'Finalizada']
    reason: str | None = None


class TaskReassignment(SafeInputModel):
    assignee_id: int = Field(gt=0)
    responsible_id: int | None = Field(default=None, gt=0)
    reason: str = Field(min_length=1)


class TaskExecutorRemoval(SafeInputModel):
    reason: str = Field(min_length=1)


class TaskBlockInput(SafeInputModel):
    reason: str = Field(min_length=1)
    evidence: str | None = None


class TaskIncidentInput(SafeInputModel):
    reason: str = Field(min_length=1)
    evidence: str | None = None


class Designation(SafeInputModel):
    collaborator_id: int = Field(gt=0)
