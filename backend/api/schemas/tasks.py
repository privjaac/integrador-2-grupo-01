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


class TaskReopen(SafeInputModel):
    reason: str = Field(min_length=1)
    result_text: str = Field(min_length=1)


class TaskCancellationProposal(SafeInputModel):
    reason: str = Field(min_length=1)
    effects: str = Field(min_length=1)
    evidence: str | None = None


class TaskCancellationEvaluation(SafeInputModel):
    decision: Literal['pendiente', 'autorizar', 'denegar']
    reason: str = Field(min_length=1)
    work_assessment: str = Field(min_length=1)
    evidence_assessment: str = Field(min_length=1)
    dependency_assessment: str = Field(min_length=1)
    obligation_disposition: Literal['none', 'follow_up', 'resolved', 'unresolved']
    obligation_assessment: str = Field(min_length=1)
    obligation_follow_up: str | None = None
    commercial_impact: Literal['none', 'existing_authorization', 'new_or_uncertain']
    commercial_assessment: str = Field(min_length=1)
    evidence: str | None = None


class TaskCancellationCommercialReview(SafeInputModel):
    decision: Literal['pendiente', 'resuelta']
    reason: str = Field(min_length=1)
    evidence: str = Field(min_length=1)


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
