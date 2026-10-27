from django.db import IntegrityError, transaction
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone
from fastapi import Depends, HTTPException, status
import json

from api.dependencies import get_current_user
from api.router import APIRouter
from api.schemas.tasks import (
    Designation, TaskAssign, TaskBlockInput, TaskCancellationCommercialReview,
    TaskCancellationEvaluation, TaskCancellationProposal, TaskCreate, TaskExecutorRemoval,
    TaskIncidentInput, TaskReassignment, TaskReview, TaskReopen, TaskSubmission,
)
from clients.models import (
    Collaborator, Project, ProjectCoordination, ProjectLeadership, Task,
    TaskEvent, TeamMembership,
)

CANCELABLE_TASK_STATUSES = {'Pendiente', 'Asignada', 'En proceso', 'En revisión', 'Observada'}
CANCELLATION_EVALUATION_EVENTS = {
    'cancelacion_pendiente', 'cancelacion_autorizada', 'cancelacion_denegada',
}
CANCELLATION_COMMERCIAL_EVENTS = {'revision_comercial_pend', 'revision_comercial_resuelta'}
CANCELLATION_EVENT_TYPES = {
    'cancelacion_propuesta', *CANCELLATION_EVALUATION_EVENTS,
    *CANCELLATION_COMMERCIAL_EVENTS, 'cancelacion_aplicada',
}

router = APIRouter()


def actor(user: dict) -> Collaborator:
    return Collaborator.objects.select_related('role').get(pk=user['collaborator_id'])


def task_queryset(user: dict):
    role = user.get('role')
    if role == 'L3':
        return Task.objects.filter(
            project__coordinations__coordinator_id=user['collaborator_id'],
            project__coordinations__is_active=True,
            project__coordinations__coordinator__is_active=True,
            project__coordinations__coordinator__role__level='L3',
        )
    if role == 'L4':
        delegated_coordinators = ProjectCoordination.objects.filter(
            project_id=OuterRef('project_id'), is_active=True,
            coordinator__is_active=True, coordinator__role__level='L3',
            leaderships__leader_id=user['collaborator_id'],
            leaderships__is_active=True,
            leaderships__leader__is_active=True,
            leaderships__leader__role__level='L4',
        ).values('coordinator_id')
        return Task.objects.filter(
            project__coordinations__leaderships__leader_id=user['collaborator_id'],
            project__coordinations__leaderships__is_active=True,
            project__coordinations__is_active=True,
            project__coordinations__coordinator__is_active=True,
            project__coordinations__coordinator__role__level='L3',
            project__coordinations__leaderships__leader__is_active=True,
            project__coordinations__leaderships__leader__role__level='L4',
        ).filter(
            Q(responsible_id=user['collaborator_id'])
            | Q(responsible_id__in=Subquery(delegated_coordinators))
        )
    if role == 'L5':
        return Task.objects.filter(
            assignee_id=user['collaborator_id'],
            assignee__is_active=True,
            assignee__role__level='L5',
        )
    return Task.objects.none()


def active_team_membership(task: Task, developer_id: int | None = None):
    return TeamMembership.objects.filter(
        leadership__coordination__project_id=task.project_id,
        leadership__leader_id=task.responsible_id,
        leadership__is_active=True,
        leadership__leader__is_active=True,
        leadership__leader__role__level='L4',
        leadership__coordination__is_active=True,
        leadership__coordination__coordinator__is_active=True,
        leadership__coordination__coordinator__role__level='L3',
        developer_id=developer_id if developer_id is not None else task.assignee_id,
        developer__is_active=True,
        developer__role__level='L5',
        is_active=True,
    )


def cancellation_event_data(event: TaskEvent) -> dict:
    try:
        value = json.loads(event.result_text or '{}')
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def cancellation_workflow(task: Task, events: list[TaskEvent]) -> dict:
    proposals = [event for event in events if event.event_type == 'cancelacion_propuesta']
    if not proposals:
        return {'proposal': None, 'evaluation': None, 'commercial': None, 'stale': False}
    proposal = proposals[-1]
    stale = (
        task.status != proposal.new_status
        or any(
            event.pk > proposal.pk and event.previous_status and event.new_status
            and event.previous_status != event.new_status
            for event in events
        )
    )
    proposal_data = cancellation_event_data(proposal)
    proposal_id = proposal_data.get('proposal_event_id', proposal.pk)
    evaluations = [
        event for event in events
        if event.event_type in CANCELLATION_EVALUATION_EVENTS
        and cancellation_event_data(event).get('proposal_event_id') == proposal_id
    ]
    evaluation = evaluations[-1] if evaluations else None
    commercial = None
    if evaluation:
        commercial = next((
            event for event in reversed(events)
            if event.event_type in CANCELLATION_COMMERCIAL_EVENTS
            and cancellation_event_data(event).get('evaluation_event_id') == evaluation.pk
        ), None)
    return {
        'proposal': proposal, 'proposal_data': proposal_data,
        'evaluation': evaluation,
        'evaluation_data': cancellation_event_data(evaluation) if evaluation else {},
        'commercial': commercial,
        'commercial_data': cancellation_event_data(commercial) if commercial else {},
        'stale': stale,
    }


def l2_can_review_cancellation(task: Task, user: dict, workflow: dict) -> bool:
    evaluation = workflow.get('evaluation')
    data = workflow.get('evaluation_data') or {}
    commercial = workflow.get('commercial')
    commercial_data = workflow.get('commercial_data') or {}
    if (
        user.get('role') != 'L2' or not evaluation or workflow.get('stale')
        or evaluation.event_type != 'cancelacion_autorizada'
        or data.get('commercial_impact') != 'new_or_uncertain'
        or (commercial and commercial.event_type == 'revision_comercial_resuelta')
    ):
        return False
    if commercial and commercial.event_type != 'revision_comercial_pend':
        return False
    return ProjectCoordination.objects.filter(
        project_id=task.project_id, coordinator_id=evaluation.actor_id,
        assigned_by_id=user.get('collaborator_id'), is_active=True,
        assigned_by__is_active=True, assigned_by__role__level='L2',
        coordinator__is_active=True, coordinator__role__level='L3',
    ).exists()


def task_action_permissions(task: Task, user: dict, events: list[TaskEvent] | None = None) -> dict:
    role = user.get('role')
    collaborator_id = user.get('collaborator_id')
    events = events if events is not None else list(task.events.all())
    workflow = cancellation_workflow(task, events)
    has_current_proposal = bool(
        workflow.get('proposal') and not workflow.get('stale')
        and task.status in CANCELABLE_TASK_STATUSES
    )
    evaluation = workflow.get('evaluation')
    evaluation_data = workflow.get('evaluation_data') or {}
    can_evaluate_cancellation = (
        has_current_proposal and (
            evaluation is None or evaluation.event_type == 'cancelacion_pendiente'
        )
    )
    commercial = workflow.get('commercial')
    needs_commercial_review = evaluation_data.get('commercial_impact') == 'new_or_uncertain'
    commercial_review_complete = bool(
        commercial and commercial.event_type == 'revision_comercial_resuelta'
        and (workflow.get('commercial_data') or {}).get('decision') == 'resuelta'
    )
    can_apply_cancellation = bool(
        has_current_proposal and evaluation and evaluation.event_type == 'cancelacion_autorizada'
        and evaluation_data.get('obligation_disposition') != 'unresolved'
        and (not needs_commercial_review or commercial_review_complete)
    )
    if role == 'L5':
        member = (
            task.assignee_id == collaborator_id
            and active_team_membership(task, collaborator_id).exists()
        )
        return {
            'can_start': member and task.status in {'Asignada', 'Observada'},
            'can_submit_result': member and task.status == 'En proceso',
            'can_review': False,
            'can_reassign': False,
            'can_remove_executor': False,
            'can_block': False,
            'can_unblock': False,
            'can_report_incident': member and task.status != 'Cancelada',
            'can_reopen': False,
            'can_propose_cancellation': False, 'can_evaluate_cancellation': False,
            'can_review_cancellation_commercial': False, 'can_apply_cancellation': False,
        }
    if role == 'L4':
        in_scope = task_queryset(user).filter(pk=task.pk).exists()
        member = active_team_membership(task).exists()
        responsible_leadership = ProjectLeadership.objects.filter(
            leader_id=collaborator_id, coordination__project_id=task.project_id,
            coordination__is_active=True, is_active=True,
            leader__is_active=True, leader__role__level='L4',
            coordination__coordinator__is_active=True,
            coordination__coordinator__role__level='L3',
        ).exists()
        return {
            'can_start': False,
            'can_submit_result': False,
            'can_review': (
                in_scope and task.responsible_id == collaborator_id
                and task.status == 'En revisión' and member
            ),
            'can_reassign': (
                in_scope and task.responsible_id == collaborator_id and responsible_leadership
                and task.status in {'En proceso', 'Observada'} and member
            ),
            'can_remove_executor': (
                in_scope and task.responsible_id == collaborator_id and responsible_leadership
                and task.status in {'Asignada', 'En proceso'} and member
            ),
            'can_block': (
                in_scope and task.responsible_id == collaborator_id and responsible_leadership
                and task.status not in {'Finalizada', 'Cancelada'} and not task.is_blocked
                and (task.assignee_id is None or member)
            ),
            'can_unblock': (
                in_scope and task.responsible_id == collaborator_id and responsible_leadership
                and task.status != 'Cancelada' and task.is_blocked
                and (task.assignee_id is None or member)
            ),
            'can_report_incident': False,
            'can_reopen': False,
            'can_propose_cancellation': (
                in_scope and task.responsible_id == collaborator_id and responsible_leadership
                and task.status in CANCELABLE_TASK_STATUSES
            ),
            'can_evaluate_cancellation': False,
            'can_review_cancellation_commercial': False, 'can_apply_cancellation': False,
        }
    if role == 'L3':
        in_scope = task_queryset(user).filter(pk=task.pk).exists()
        return {
            'can_start': False,
            'can_submit_result': False,
            'can_review': False,
            'can_reassign': in_scope and task.status in {'En proceso', 'Observada'},
            'can_remove_executor': in_scope and task.status in {'Asignada', 'En proceso'},
            'can_block': in_scope and task.status not in {'Finalizada', 'Cancelada'} and not task.is_blocked,
            'can_unblock': in_scope and task.status != 'Cancelada' and task.is_blocked,
            'can_report_incident': False,
            'can_reopen': in_scope and task.status == 'Finalizada',
            'can_propose_cancellation': False,
            'can_evaluate_cancellation': in_scope and can_evaluate_cancellation,
            'can_review_cancellation_commercial': False,
            'can_apply_cancellation': in_scope and can_apply_cancellation,
        }
    if role == 'L2':
        return {
            'can_start': False, 'can_submit_result': False, 'can_review': False,
            'can_reassign': False, 'can_remove_executor': False, 'can_block': False,
            'can_unblock': False, 'can_report_incident': False, 'can_reopen': False,
            'can_propose_cancellation': False, 'can_evaluate_cancellation': False,
            'can_review_cancellation_commercial': l2_can_review_cancellation(task, user, workflow),
            'can_apply_cancellation': False,
        }
    return {
        'can_start': False, 'can_submit_result': False, 'can_review': False,
        'can_reassign': False, 'can_remove_executor': False,
        'can_block': False, 'can_unblock': False, 'can_report_incident': False,
        'can_reopen': False,
        'can_propose_cancellation': False, 'can_evaluate_cancellation': False,
        'can_review_cancellation_commercial': False, 'can_apply_cancellation': False,
    }


def task_response(task: Task, user: dict) -> dict:
    events = list(task.events.select_related(
        'actor', 'assignee', 'previous_assignee', 'responsible', 'previous_responsible',
    ).all())
    return {
        'id': task.id,
        'project_id': task.project_id,
        'project_name': task.project.name,
        'title': task.title,
        'description': task.description,
        'status': task.status,
        'is_blocked': task.is_blocked,
        'block_reason': task.block_reason,
        'block_evidence': task.block_evidence,
        'created_by_id': task.created_by_id,
        'created_by_name': f'{task.created_by.first_name} {task.created_by.last_name}',
        'responsible_id': task.responsible_id,
        'responsible_name': f'{task.responsible.first_name} {task.responsible.last_name}',
        'assignee_id': task.assignee_id,
        'assignee_name': (
            f'{task.assignee.first_name} {task.assignee.last_name}' if task.assignee_id else None
        ),
        'created_at': task.created_at.isoformat(),
        'assigned_at': task.assigned_at.isoformat() if task.assigned_at else None,
        'events': [
            {
                'task_id': event.task_id,
                'event_type': event.event_type,
                'actor_id': event.actor_id,
                'actor_name': f'{event.actor.first_name} {event.actor.last_name}',
                'previous_status': event.previous_status or None,
                'new_status': event.new_status,
                'assignee_id': event.assignee_id,
                'assignee_name': (
                    f'{event.assignee.first_name} {event.assignee.last_name}' if event.assignee_id else None
                ),
                'previous_assignee_id': event.previous_assignee_id,
                'previous_assignee_name': (
                    f'{event.previous_assignee.first_name} {event.previous_assignee.last_name}'
                    if event.previous_assignee_id else None
                ),
                'responsible_id': event.responsible_id,
                'responsible_name': (
                    f'{event.responsible.first_name} {event.responsible.last_name}'
                    if event.responsible_id else None
                ),
                'previous_responsible_id': event.previous_responsible_id,
                'previous_responsible_name': (
                    f'{event.previous_responsible.first_name} {event.previous_responsible.last_name}'
                    if event.previous_responsible_id else None
                ),
                'is_blocked_before': event.is_blocked_before,
                'is_blocked_after': event.is_blocked_after,
                'evidence': event.evidence,
                'result_text': event.result_text,
                'reason': event.reason,
                'cancellation_data': cancellation_event_data(event)
                if event.event_type in CANCELLATION_EVENT_TYPES else None,
                'occurred_at': event.occurred_at.isoformat(),
            }
            for event in events
        ],
        'actions': task_action_permissions(task, user, events),
    }


def active_role_collaborators(level: str):
    return Collaborator.objects.filter(
        role__level=level, is_active=True,
    ).order_by('last_name', 'first_name')


def project_context(project: Project) -> dict:
    return {'id': project.id, 'name': project.name}


def lock_project_coordinations(project_id: int) -> list[ProjectCoordination]:
    """Lock active project scopes in a stable parent-first order."""
    ids = ProjectCoordination.objects.filter(
        project_id=project_id, is_active=True,
        coordinator__is_active=True, coordinator__role__level='L3',
    ).order_by('id').values_list('id', flat=True)
    return list(
        ProjectCoordination.objects.select_for_update(of=('self',)).filter(
            pk__in=ids, is_active=True,
            coordinator__is_active=True, coordinator__role__level='L3',
        ).order_by('id')
    )


def lock_l4_leaderships(project_id: int, leader_id: int) -> tuple[list[ProjectCoordination], list[ProjectLeadership]]:
    coordinations = lock_project_coordinations(project_id)
    coordination_ids = [item.id for item in coordinations]
    if not coordination_ids:
        return coordinations, []
    leadership_ids = ProjectLeadership.objects.filter(
        coordination_id__in=coordination_ids, leader_id=leader_id, is_active=True,
        leader__is_active=True, leader__role__level='L4',
    ).order_by('id').values_list('id', flat=True)
    leaderships = list(
        ProjectLeadership.objects.select_for_update(of=('self',)).filter(
            pk__in=leadership_ids, coordination_id__in=coordination_ids,
            leader_id=leader_id, is_active=True,
            leader__is_active=True, leader__role__level='L4',
        ).order_by('id')
    )
    return coordinations, leaderships


def lock_task_for_l5(task_id: int, collaborator_id: int) -> Task:
    candidate = Task.objects.filter(pk=task_id).values(
        'project_id', 'responsible_id', 'assignee_id',
    ).first()
    if candidate is None or candidate['assignee_id'] != collaborator_id:
        raise HTTPException(404, 'Tarea no encontrada en tu ámbito')
    _coordinations, leaderships = lock_l4_leaderships(
        candidate['project_id'], candidate['responsible_id'],
    )
    if not leaderships:
        raise HTTPException(404, 'La responsabilidad vigente de la tarea no está disponible')
    membership = TeamMembership.objects.select_for_update(of=('self',)).filter(
        leadership_id__in=[item.id for item in leaderships],
        developer_id=collaborator_id, developer__is_active=True,
        developer__role__level='L5', is_active=True,
    ).first()
    if membership is None:
        raise HTTPException(404, 'La pertenencia al equipo ya no está vigente')
    task = Task.objects.select_for_update().filter(pk=task_id).first()
    if task is None or task.assignee_id != collaborator_id or task.responsible_id != candidate['responsible_id']:
        raise HTTPException(404, 'Tarea no encontrada en tu ámbito')
    return task


def lock_task_for_l4_review(task_id: int, collaborator_id: int) -> Task:
    candidate = Task.objects.filter(pk=task_id).values(
        'project_id', 'responsible_id', 'assignee_id',
    ).first()
    if candidate is None or candidate['responsible_id'] != collaborator_id or not candidate['assignee_id']:
        raise HTTPException(404, 'Tarea no encontrada en tu responsabilidad')
    _coordinations, leaderships = lock_l4_leaderships(
        candidate['project_id'], collaborator_id,
    )
    if not leaderships:
        raise HTTPException(404, 'La responsabilidad L4 ya no está vigente')
    membership = TeamMembership.objects.select_for_update(of=('self',)).filter(
        leadership_id__in=[item.id for item in leaderships],
        developer_id=candidate['assignee_id'], developer__is_active=True,
        developer__role__level='L5', is_active=True,
    ).first()
    if membership is None:
        raise HTTPException(404, 'La pertenencia del ejecutor ya no está vigente')
    task = Task.objects.select_for_update().filter(pk=task_id).first()
    if task is None or task.responsible_id != collaborator_id or task.assignee_id != candidate['assignee_id']:
        raise HTTPException(404, 'Tarea no encontrada en tu responsabilidad')
    return task


def lock_task_for_reassignment(
    task_id: int, actor_id: int, target_responsible_id: int, target_assignee_id: int,
) -> tuple[Task, TeamMembership]:
    candidate = Task.objects.filter(pk=task_id).values(
        'project_id', 'responsible_id', 'assignee_id',
    ).first()
    if candidate is None or candidate['assignee_id'] is None:
        raise HTTPException(404, 'Tarea asignada no encontrada en tu ámbito')
    coordinations = lock_project_coordinations(candidate['project_id'])
    actor_role = Collaborator.objects.select_related('role').filter(pk=actor_id).values_list(
        'role__level', flat=True,
    ).first()
    if actor_role == 'L3':
        if not any(item.coordinator_id == actor_id for item in coordinations):
            raise HTTPException(404, 'Tarea no encontrada en tu coordinación vigente')
        leadership_ids = ProjectLeadership.objects.filter(
            coordination_id__in=[item.id for item in coordinations],
            leader_id__in=[candidate['responsible_id'], target_responsible_id],
            is_active=True, leader__is_active=True, leader__role__level='L4',
        ).order_by('id').values_list('id', flat=True)
        leaderships = list(ProjectLeadership.objects.select_for_update(of=('self',)).filter(
            pk__in=leadership_ids, coordination_id__in=[item.id for item in coordinations],
            is_active=True, leader__is_active=True, leader__role__level='L4',
        ).order_by('id'))
        if not any(item.leader_id == target_responsible_id for item in leaderships):
            raise HTTPException(400, 'El nuevo responsable debe ser L4 vigente de esta coordinación')
    elif actor_role == 'L4':
        if actor_id != candidate['responsible_id'] or target_responsible_id != actor_id:
            raise HTTPException(403, 'L4 solo puede reasignar dentro de su propia responsabilidad')
        _coordinations, leaderships = lock_l4_leaderships(candidate['project_id'], actor_id)
        if not leaderships:
            raise HTTPException(404, 'La responsabilidad L4 ya no está vigente')
    else:
        raise HTTPException(403, 'Solo L4 responsable o L3 coordinador puede reasignar')

    target_leaderships = [item.id for item in leaderships if item.leader_id == target_responsible_id]
    target_developer = Collaborator.objects.select_for_update().filter(
        pk=target_assignee_id, is_active=True, role__level='L5',
    ).first()
    if target_developer is None:
        raise HTTPException(400, 'El nuevo ejecutor debe ser un L5 activo')
    membership = TeamMembership.objects.select_for_update(of=('self',)).filter(
        leadership_id__in=target_leaderships,
        developer_id=target_developer.id, is_active=True,
    ).first()
    if membership is None:
        raise HTTPException(400, 'El nuevo ejecutor debe ser L5 activo del equipo responsable')
    task = Task.objects.select_for_update().filter(pk=task_id).first()
    if (
        task is None or task.project_id != candidate['project_id']
        or task.assignee_id != candidate['assignee_id']
        or task.responsible_id != candidate['responsible_id']
    ):
        raise HTTPException(409, 'La asignación cambió durante la operación')
    if actor_role == 'L4' and not task_queryset({'role': 'L4', 'collaborator_id': actor_id}).filter(pk=task_id).exists():
        raise HTTPException(404, 'Tarea fuera de tu ámbito vigente')
    return task, membership


def lock_task_for_executor_removal(task_id: int, actor_id: int) -> Task:
    candidate = Task.objects.filter(pk=task_id).values(
        'project_id', 'responsible_id', 'assignee_id',
    ).first()
    if candidate is None or candidate['assignee_id'] is None:
        raise HTTPException(404, 'Tarea con ejecutor no encontrada en tu ámbito')
    coordinations = lock_project_coordinations(candidate['project_id'])
    actor_role = Collaborator.objects.select_related('role').filter(pk=actor_id).values_list(
        'role__level', flat=True,
    ).first()
    if actor_role == 'L4':
        if actor_id != candidate['responsible_id']:
            raise HTTPException(404, 'Tarea fuera de tu responsabilidad vigente')
        _coordinations, leaderships = lock_l4_leaderships(candidate['project_id'], actor_id)
        if not leaderships:
            raise HTTPException(404, 'La responsabilidad L4 ya no está vigente')
        membership = TeamMembership.objects.select_for_update(of=('self',)).filter(
            leadership_id__in=[item.id for item in leaderships],
            developer_id=candidate['assignee_id'], developer__is_active=True,
            developer__role__level='L5', is_active=True,
        ).exists()
        if not membership:
            raise HTTPException(404, 'La pertenencia del ejecutor ya no está vigente')
    elif actor_role == 'L3':
        if not any(item.coordinator_id == actor_id for item in coordinations):
            raise HTTPException(404, 'Tarea no encontrada en tu coordinación vigente')
    else:
        raise HTTPException(403, 'Solo L4 responsable o L3 coordinador puede retirar ejecutores')
    if actor_role == 'L4' and not Collaborator.objects.select_for_update().filter(
        pk=candidate['assignee_id'], is_active=True, role__level='L5',
    ).exists():
        raise HTTPException(404, 'El ejecutor ya no está activo')
    task = Task.objects.select_for_update().filter(pk=task_id).first()
    if (
        task is None or task.assignee_id != candidate['assignee_id']
        or task.responsible_id != candidate['responsible_id']
    ):
        raise HTTPException(409, 'La asignación cambió durante la operación')
    return task


def lock_task_for_block_action(task_id: int, actor_id: int, actor_role: str) -> Task:
    candidate = Task.objects.filter(pk=task_id).values(
        'project_id', 'responsible_id', 'assignee_id', 'status', 'is_blocked',
    ).first()
    if candidate is None:
        raise HTTPException(404, 'Tarea no encontrada en tu ámbito')
    coordinations = lock_project_coordinations(candidate['project_id'])
    if actor_role == 'L3':
        if not any(item.coordinator_id == actor_id for item in coordinations):
            raise HTTPException(404, 'Tarea no encontrada en tu coordinación vigente')
    elif actor_role == 'L4':
        if candidate['responsible_id'] != actor_id:
            raise HTTPException(404, 'Tarea fuera de tu responsabilidad vigente')
        _coordinations, leaderships = lock_l4_leaderships(candidate['project_id'], actor_id)
        if not leaderships:
            raise HTTPException(404, 'La responsabilidad L4 ya no está vigente')
        if candidate['assignee_id'] is not None:
            membership = TeamMembership.objects.select_for_update(of=('self',)).filter(
                leadership_id__in=[item.id for item in leaderships],
                developer_id=candidate['assignee_id'], developer__is_active=True,
                developer__role__level='L5', is_active=True,
            ).exists()
            if not membership:
                raise HTTPException(404, 'La pertenencia del ejecutor ya no está vigente')
    else:
        raise HTTPException(403, 'Solo L3 coordinador o L4 responsable puede gestionar bloqueos')
    task = Task.objects.select_for_update().filter(pk=task_id).first()
    if task is None or (
        task.project_id != candidate['project_id']
        or task.responsible_id != candidate['responsible_id']
        or task.assignee_id != candidate['assignee_id']
        or task.status != candidate['status']
        or task.is_blocked != candidate['is_blocked']
    ):
        raise HTTPException(409, 'La tarea cambió durante la operación')
    return task


def lock_task_for_l3_reopen(task_id: int, coordinator_id: int) -> Task:
    candidate = Task.objects.filter(pk=task_id).values('project_id', 'status').first()
    if candidate is None:
        raise HTTPException(404, 'Tarea no encontrada en tu coordinación')
    coordinations = lock_project_coordinations(candidate['project_id'])
    if not any(item.coordinator_id == coordinator_id for item in coordinations):
        raise HTTPException(404, 'Tarea no encontrada en tu coordinación vigente')
    task = Task.objects.select_for_update().filter(pk=task_id).first()
    if task is None or task.project_id != candidate['project_id'] or task.status != candidate['status']:
        raise HTTPException(409, 'La tarea cambió durante la operación')
    if task.status != 'Finalizada':
        raise HTTPException(409, 'Solo una tarea Finalizada puede reabrirse')
    return task


def lock_task_for_cancellation(task_id: int, actor_id: int, actor_role: str) -> Task:
    candidate = Task.objects.filter(pk=task_id).values(
        'project_id', 'responsible_id', 'assignee_id', 'status',
    ).first()
    if candidate is None:
        raise HTTPException(404, 'Tarea no encontrada en tu ámbito')
    coordinations = lock_project_coordinations(candidate['project_id'])
    if actor_role == 'L3':
        if not any(item.coordinator_id == actor_id for item in coordinations):
            raise HTTPException(404, 'Tarea fuera de tu coordinación vigente')
    elif actor_role == 'L4':
        _coordinations, leaderships = lock_l4_leaderships(candidate['project_id'], actor_id)
        if candidate['responsible_id'] != actor_id or not leaderships:
            raise HTTPException(404, 'Tarea fuera de tu responsabilidad vigente')
    else:
        raise HTTPException(403, 'Nivel sin autorización para esta operación de cancelación')
    task = Task.objects.select_for_update().filter(pk=task_id).first()
    if task is None or any((
        task.project_id != candidate['project_id'],
        task.responsible_id != candidate['responsible_id'],
        task.assignee_id != candidate['assignee_id'],
        task.status != candidate['status'],
    )):
        raise HTTPException(409, 'La tarea cambió durante la operación')
    return task


def cancellation_event(task, event_type, current_actor, reason, data, evidence=''):
    event = TaskEvent.objects.create(
        task=task, event_type=event_type, actor=current_actor,
        previous_status=task.status, new_status=task.status,
        assignee_id=task.assignee_id, responsible_id=task.responsible_id,
        is_blocked_before=task.is_blocked, is_blocked_after=task.is_blocked,
        reason=reason, evidence=evidence or '', result_text=json.dumps(data, ensure_ascii=False),
    )
    return event


def valid_cancellation_proposal(task, events):
    workflow = cancellation_workflow(task, events)
    proposal = workflow.get('proposal')
    if not proposal or workflow.get('stale') or task.status not in CANCELABLE_TASK_STATUSES:
        return workflow, None
    return workflow, proposal


def commercial_cancellation_summary(task: Task, user: dict) -> dict | None:
    events = list(task.events.select_related('actor').all())
    workflow = cancellation_workflow(task, events)
    if not l2_can_review_cancellation(task, user, workflow):
        return None
    proposal = workflow['proposal']
    evaluation = workflow['evaluation']
    return {
        'task_id': task.id, 'project_id': task.project_id,
        'project_name': task.project.name, 'task_title': task.title,
        'status': task.status,
        'proposal': {
            'event_id': proposal.id, 'actor_name': f'{proposal.actor.first_name} {proposal.actor.last_name}',
            'occurred_at': proposal.occurred_at.isoformat(), 'reason': proposal.reason,
            'effects': workflow['proposal_data'].get('effects', ''), 'evidence': proposal.evidence,
        },
        'evaluation': {
            'event_id': evaluation.id, 'actor_name': f'{evaluation.actor.first_name} {evaluation.actor.last_name}',
            'occurred_at': evaluation.occurred_at.isoformat(), 'reason': evaluation.reason,
            'data': workflow['evaluation_data'], 'evidence': evaluation.evidence,
        },
    }


@router.get('/context')
def get_task_context(user: dict = Depends(get_current_user)):
    role = user.get('role')
    if role not in {'L2', 'L3', 'L4', 'L5'}:
        raise HTTPException(403, 'No tienes acceso al contexto de tareas')
    collaborator_id = user['collaborator_id']
    result = {
        'role': role, 'projects': [], 'coordinators': [], 'leaders': [],
        'developers': [], 'tasks': [], 'commercial_cancellations': [],
    }

    if role == 'L2':
        result['projects'] = [project_context(p) for p in Project.objects.order_by('id')]
        result['coordination_assignments'] = [
            {'project_id': c.project_id, 'coordinator_id': c.coordinator_id,
             'coordinator_name': f'{c.coordinator.first_name} {c.coordinator.last_name}',
             'can_remove': c.assigned_by_id == collaborator_id}
            for c in ProjectCoordination.objects.filter(
                is_active=True, coordinator__is_active=True, coordinator__role__level='L3',
            ).select_related('coordinator')
        ]
        result['coordinators'] = [
            {'id': c.id, 'name': f'{c.first_name} {c.last_name}'}
            for c in active_role_collaborators('L3')
        ]
        project_ids = ProjectCoordination.objects.filter(
            assigned_by_id=collaborator_id, is_active=True,
            assigned_by__is_active=True, assigned_by__role__level='L2',
            coordinator__is_active=True, coordinator__role__level='L3',
        ).values_list('project_id', flat=True)
        for task in Task.objects.filter(
            project_id__in=project_ids, status__in=CANCELABLE_TASK_STATUSES,
        ).select_related('project').distinct():
            summary = commercial_cancellation_summary(task, user)
            if summary:
                result['commercial_cancellations'].append(summary)
    elif role == 'L3':
        coordinations = ProjectCoordination.objects.filter(
            coordinator_id=collaborator_id, coordinator__is_active=True,
            coordinator__role__level='L3', is_active=True,
        ).select_related('project')
        result['projects'] = [project_context(c.project) for c in coordinations]
        result['leaders'] = [
            {'id': c.id, 'name': f'{c.first_name} {c.last_name}'}
            for c in active_role_collaborators('L4')
        ] if coordinations.exists() else []
        result['leadership_assignments'] = [
            {'project_id': item.coordination.project_id, 'leader_id': item.leader_id,
             'leadership_id': item.id, 'leader_name': f'{item.leader.first_name} {item.leader.last_name}',
             'can_remove': item.designated_by_id == collaborator_id}
            for item in ProjectLeadership.objects.filter(
                coordination__coordinator_id=collaborator_id,
                coordination__is_active=True, is_active=True,
                leader__is_active=True, leader__role__level='L4',
            ).select_related('coordination', 'leader')
        ]
        result['tasks'] = [task_response(t, user) for t in task_queryset(user).select_related('project', 'assignee').distinct()]
    elif role == 'L4':
        leaderships = ProjectLeadership.objects.filter(
            leader_id=collaborator_id, is_active=True, coordination__is_active=True,
            leader__is_active=True, leader__role__level='L4',
            coordination__coordinator__is_active=True,
            coordination__coordinator__role__level='L3',
        ).select_related('coordination__project')
        unique_projects = {}
        for leadership in leaderships:
            unique_projects.setdefault(leadership.coordination.project_id, {
                **project_context(leadership.coordination.project), 'leadership_id': leadership.id,
            })
        result['projects'] = list(unique_projects.values())
        result['all_developers'] = [
            {'id': c.id, 'name': f'{c.first_name} {c.last_name}'}
            for c in active_role_collaborators('L5')
        ]
        unique_members = {}
        for membership in TeamMembership.objects.filter(
                leadership__leader_id=collaborator_id, leadership__is_active=True,
                leadership__coordination__is_active=True, developer__is_active=True,
                leadership__leader__role__level='L4',
                leadership__coordination__coordinator__is_active=True,
                leadership__coordination__coordinator__role__level='L3',
                developer__role__level='L5', is_active=True,
            ).select_related('developer', 'leadership__coordination'):
            unique_members.setdefault((membership.leadership.coordination.project_id, membership.developer_id), {
                'id': membership.developer_id,
                'name': f'{membership.developer.first_name} {membership.developer.last_name}',
                'leadership_id': membership.leadership_id,
                'membership_id': membership.id,
                'can_remove': membership.added_by_id == collaborator_id,
                'project_id': membership.leadership.coordination.project_id,
                'responsible_id': membership.leadership.leader_id,
            })
        result['developers'] = list(unique_members.values())
        result['tasks'] = [task_response(t, user) for t in task_queryset(user).select_related('project', 'assignee').distinct()]
    elif role == 'L3':
        memberships = TeamMembership.objects.filter(
            leadership__coordination__coordinator_id=collaborator_id,
            leadership__coordination__is_active=True,
            leadership__coordination__coordinator__is_active=True,
            leadership__is_active=True, leadership__leader__is_active=True,
            leadership__leader__role__level='L4', is_active=True,
            developer__is_active=True, developer__role__level='L5',
        ).select_related('developer', 'leadership__coordination', 'leadership__leader')
        result['developers'] = [
            {
                'id': membership.developer_id,
                'name': f'{membership.developer.first_name} {membership.developer.last_name}',
                'project_id': membership.leadership.coordination.project_id,
                'responsible_id': membership.leadership.leader_id,
            }
            for membership in memberships
        ]
        result['tasks'] = [task_response(t, user) for t in task_queryset(user).select_related('project', 'assignee').distinct()]
    elif role == 'L5':
        result['tasks'] = [task_response(t, user) for t in task_queryset(user).select_related('project', 'assignee').distinct()]
    return result


@router.post('/projects/{project_id}/coordination', status_code=status.HTTP_201_CREATED)
def designate_coordinator(project_id: int, payload: Designation, user: dict = Depends(get_current_user)):
    if user.get('role') != 'L2':
        raise HTTPException(403, 'Solo L2 puede designar la coordinación del proyecto')
    project = Project.objects.filter(pk=project_id).first()
    coordinator = Collaborator.objects.select_related('role').filter(
        pk=payload.collaborator_id, is_active=True, role__level='L3',
    ).first()
    if project is None:
        raise HTTPException(404, 'Proyecto no encontrado')
    if coordinator is None:
        raise HTTPException(400, 'La coordinación requiere un colaborador L3 activo')
    try:
        with transaction.atomic():
            existing = ProjectCoordination.objects.select_for_update(of=('self',)).filter(
                project=project, coordinator=coordinator, is_active=True,
            ).first()
            if existing:
                return {'project_id': project.id, 'coordinator_id': coordinator.id, 'created': False}
            ProjectCoordination.objects.create(
                project=project, coordinator=coordinator, assigned_by=actor(user),
            )
    except IntegrityError:
        raise HTTPException(409, 'La coordinación ya existe')
    return {'project_id': project.id, 'coordinator_id': coordinator.id, 'created': True}


@router.post('/projects/{project_id}/leadership', status_code=status.HTTP_201_CREATED)
def designate_leader(project_id: int, payload: Designation, user: dict = Depends(get_current_user)):
    if user.get('role') != 'L3':
        raise HTTPException(403, 'Solo L3 puede designar líderes en su proyecto coordinado')
    leader = Collaborator.objects.filter(
        pk=payload.collaborator_id, is_active=True, role__level='L4',
    ).first()
    if leader is None:
        raise HTTPException(400, 'El líder debe ser un colaborador L4 activo')
    try:
        with transaction.atomic():
            coordination = ProjectCoordination.objects.select_for_update(of=('self',)).filter(
                project_id=project_id, coordinator_id=user['collaborator_id'],
                is_active=True, coordinator__is_active=True, coordinator__role__level='L3',
            ).first()
            if coordination is None:
                raise HTTPException(404, 'Proyecto fuera de la coordinación vigente')
            existing = ProjectLeadership.objects.select_for_update(of=('self',)).filter(
                coordination=coordination, leader=leader, is_active=True,
            ).first()
            if existing:
                return {'project_id': project_id, 'leader_id': leader.id, 'created': False}
            ProjectLeadership.objects.create(
                coordination=coordination, leader=leader,
                designated_by_id=user['collaborator_id'],
            )
    except IntegrityError:
        raise HTTPException(409, 'La designación ya existe')
    return {'project_id': project_id, 'leader_id': leader.id, 'created': True}


@router.post('/projects/{project_id}/team', status_code=status.HTTP_201_CREATED)
def add_team_member(project_id: int, payload: Designation, user: dict = Depends(get_current_user)):
    if user.get('role') != 'L4':
        raise HTTPException(403, 'Solo L4 puede incorporar L5 a su equipo')
    with transaction.atomic():
        _coordinations, leaderships = lock_l4_leaderships(project_id, user['collaborator_id'])
        if not leaderships:
            raise HTTPException(404, 'Proyecto fuera de la responsabilidad L4 vigente')
        developer = Collaborator.objects.filter(
            pk=payload.collaborator_id, is_active=True, role__level='L5',
        ).first()
        if developer is None:
            raise HTTPException(400, 'El integrante debe ser un colaborador L5 activo')
        leadership_ids = [item.id for item in leaderships]
        active_memberships = set(TeamMembership.objects.select_for_update(of=('self',)).filter(
            leadership_id__in=leadership_ids, developer=developer, is_active=True,
        ).values_list('leadership_id', flat=True))
        created = 0
        for leadership in leaderships:
            if leadership.id in active_memberships:
                continue
            TeamMembership.objects.create(
                leadership=leadership, developer=developer,
                added_by_id=user['collaborator_id'],
            )
            created += 1
    return {'project_id': project_id, 'developer_id': developer.id, 'created': bool(created)}


@router.delete('/projects/{project_id}/coordination/{collaborator_id}')
def remove_coordinator(project_id: int, collaborator_id: int, user: dict = Depends(get_current_user)):
    if user.get('role') != 'L2':
        raise HTTPException(403, 'Solo L2 puede retirar la coordinación que designó')
    now = timezone.now()
    with transaction.atomic():
        assignment = ProjectCoordination.objects.select_for_update().filter(
            project_id=project_id, coordinator_id=collaborator_id,
            assigned_by_id=user['collaborator_id'], is_active=True,
        ).first()
        if assignment is None:
            raise HTTPException(404, 'No existe una coordinación vigente designada por este usuario')
        assignment.is_active = False
        assignment.ended_by_id = user['collaborator_id']
        assignment.ended_at = now
        assignment.save(update_fields=['is_active', 'ended_by', 'ended_at'])
        leaderships = ProjectLeadership.objects.filter(coordination=assignment, is_active=True)
        leadership_ids = list(leaderships.values_list('id', flat=True))
        leaderships.update(is_active=False, ended_by_id=user['collaborator_id'], ended_at=now)
        TeamMembership.objects.filter(leadership_id__in=leadership_ids, is_active=True).update(
            is_active=False, ended_by_id=user['collaborator_id'], ended_at=now,
        )
    return {'project_id': project_id, 'coordinator_id': collaborator_id, 'active': False}


@router.delete('/projects/{project_id}/leadership/{collaborator_id}')
def remove_leader(project_id: int, collaborator_id: int, user: dict = Depends(get_current_user)):
    if user.get('role') != 'L3':
        raise HTTPException(403, 'Solo L3 puede retirar la designación que realizó')
    now = timezone.now()
    with transaction.atomic():
        coordination = ProjectCoordination.objects.select_for_update(of=('self',)).filter(
            project_id=project_id, coordinator_id=user['collaborator_id'],
            is_active=True, coordinator__is_active=True, coordinator__role__level='L3',
        ).first()
        if coordination is None:
            raise HTTPException(404, 'No existe una coordinación vigente para este proyecto')
        assignment = ProjectLeadership.objects.select_for_update(of=('self',)).filter(
            coordination=coordination, leader_id=collaborator_id,
            designated_by_id=user['collaborator_id'], is_active=True,
        ).first()
        if assignment is None:
            raise HTTPException(404, 'No existe una designación vigente realizada por este usuario')
        assignment.is_active = False
        assignment.ended_by_id = user['collaborator_id']
        assignment.ended_at = now
        assignment.save(update_fields=['is_active', 'ended_by', 'ended_at'])
        membership_ids = list(TeamMembership.objects.select_for_update(of=('self',)).filter(
            leadership=assignment, is_active=True,
        ).order_by('id').values_list('id', flat=True))
        TeamMembership.objects.filter(pk__in=membership_ids, is_active=True).update(
            is_active=False, ended_by_id=user['collaborator_id'], ended_at=now,
        )
    return {'project_id': project_id, 'leader_id': collaborator_id, 'active': False}


@router.delete('/projects/{project_id}/team/{collaborator_id}')
def remove_team_member(project_id: int, collaborator_id: int, user: dict = Depends(get_current_user)):
    if user.get('role') != 'L4':
        raise HTTPException(403, 'Solo L4 puede retirar integrantes que incorporó')
    now = timezone.now()
    with transaction.atomic():
        coordinations = lock_project_coordinations(project_id)
        coordination_ids = [item.id for item in coordinations]
        leadership_ids = list(ProjectLeadership.objects.select_for_update(of=('self',)).filter(
            coordination_id__in=coordination_ids, leader_id=user['collaborator_id'],
            is_active=True, leader__is_active=True, leader__role__level='L4',
        ).order_by('id').values_list('id', flat=True))
        membership_ids = list(TeamMembership.objects.select_for_update(of=('self',)).filter(
            leadership_id__in=leadership_ids, developer_id=collaborator_id,
            added_by_id=user['collaborator_id'], is_active=True,
        ).order_by('id').values_list('id', flat=True))
        if not membership_ids:
            raise HTTPException(404, 'No existe una pertenencia vigente incorporada por este usuario')
        TeamMembership.objects.filter(pk__in=membership_ids, is_active=True).update(
            is_active=False, ended_by_id=user['collaborator_id'], ended_at=now,
        )
    return {'project_id': project_id, 'developer_id': collaborator_id, 'active': False}


@router.get('/')
def list_tasks(user: dict = Depends(get_current_user)):
    if user.get('role') not in {'L3', 'L4', 'L5'}:
        raise HTTPException(403, 'No tienes permiso para consultar tareas')
    return [task_response(t, user) for t in task_queryset(user).select_related('project', 'assignee').distinct()]


@router.get('/{task_id}')
def get_task(task_id: int, user: dict = Depends(get_current_user)):
    if user.get('role') not in {'L3', 'L4', 'L5'}:
        raise HTTPException(403, 'No tienes permiso para consultar tareas')
    task = task_queryset(user).select_related('project', 'assignee').filter(pk=task_id).first()
    if task is None:
        raise HTTPException(404, 'Tarea no encontrada')
    return task_response(task, user)


@router.post('/', status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, user: dict = Depends(get_current_user)):
    role = user.get('role')
    if role not in {'L3', 'L4'}:
        raise HTTPException(403, 'No tienes permiso para crear tareas')
    if not payload.title.strip():
        raise HTTPException(422, 'El título de la tarea es obligatorio')
    project = Project.objects.filter(pk=payload.project_id).first()
    if project is None:
        raise HTTPException(404, 'Proyecto no encontrado')
    current_actor = actor(user)
    try:
        with transaction.atomic():
            assignee = None
            if role == 'L3':
                coordinator = ProjectCoordination.objects.select_for_update(of=('self',)).filter(
                    project=project, coordinator_id=user['collaborator_id'], is_active=True,
                    coordinator__is_active=True, coordinator__role__level='L3',
                ).first()
                if coordinator is None:
                    raise HTTPException(403, 'El proyecto está fuera de tu coordinación')
                if payload.status != 'Pendiente' or payload.assignee_id is not None:
                    raise HTTPException(403, 'L3 solo puede crear tareas Pendientes sin ejecutor')
            else:
                coordinations, leaderships = lock_l4_leaderships(project.id, user['collaborator_id'])
                if not leaderships:
                    raise HTTPException(403, 'El proyecto está fuera de tu responsabilidad L4')
                if payload.status == 'Asignada' and payload.assignee_id is None:
                    raise HTTPException(422, 'Selecciona un L5 activo de tu equipo para asignar la tarea')
                if payload.status == 'Pendiente' and payload.assignee_id is not None:
                    raise HTTPException(422, 'Una tarea Pendiente no puede incluir ejecutor')
                if payload.assignee_id is not None:
                    membership = TeamMembership.objects.select_for_update(of=('self',)).select_related('developer').filter(
                        leadership_id__in=[item.id for item in leaderships],
                        developer_id=payload.assignee_id, developer__is_active=True,
                        developer__role__level='L5', is_active=True,
                    ).first()
                    if membership is None:
                        raise HTTPException(400, 'El ejecutor debe ser L5 activo perteneciente a tu equipo')
                    assignee = membership.developer
            task = Task.objects.create(
                project=project, title=payload.title.strip(), description=payload.description,
                status=payload.status, created_by=current_actor, responsible=current_actor,
                assignee=assignee, assigned_at=timezone.now() if assignee else None,
            )
            TaskEvent.objects.create(
                task=task, event_type='creada', actor=current_actor,
                new_status=task.status, assignee=assignee,
            )
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar la tarea por una relación concurrente')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task.pk), user)


@router.post('/{task_id}/assignment')
def assign_task(task_id: int, payload: TaskAssign, user: dict = Depends(get_current_user)):
    if user.get('role') != 'L4':
        raise HTTPException(403, 'Solo L4 puede asignar tareas a su equipo')
    project_id = Task.objects.filter(pk=task_id).values_list('project_id', flat=True).first()
    if project_id is None:
        raise HTTPException(404, 'Tarea no encontrada en tu ámbito')
    current_actor = actor(user)
    try:
        with transaction.atomic():
            _coordinations, leaderships = lock_l4_leaderships(project_id, user['collaborator_id'])
            if not leaderships:
                raise HTTPException(404, 'Tarea no encontrada en tu ámbito')
            in_scope = task_queryset(user).filter(pk=task_id, project_id=project_id).first()
            if in_scope is None:
                raise HTTPException(404, 'Tarea no encontrada en tu ámbito')
            membership = TeamMembership.objects.select_for_update(of=('self',)).filter(
                leadership_id__in=[item.id for item in leaderships],
                developer_id=payload.assignee_id, developer__is_active=True,
                developer__role__level='L5', is_active=True,
            ).first()
            if membership is None:
                raise HTTPException(400, 'El ejecutor debe ser L5 activo perteneciente a tu equipo')
            locked = Task.objects.select_for_update().get(pk=task_id, project_id=project_id)
            if locked.status != 'Pendiente':
                raise HTTPException(409, 'La tarea ya fue asignada')
            locked.status = 'Asignada'
            locked.responsible = current_actor
            locked.assignee_id = membership.developer_id
            locked.assigned_at = timezone.now()
            locked.save(update_fields=['status', 'responsible', 'assignee', 'assigned_at'])
            TaskEvent.objects.create(
                task=locked, event_type='asignada', actor=current_actor,
                previous_status='Pendiente', new_status='Asignada', assignee_id=membership.developer_id,
            )
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar la asignación')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id), user)


@router.post('/{task_id}/reassignment')
def reassign_task(
    task_id: int, payload: TaskReassignment, user: dict = Depends(get_current_user),
):
    role = user.get('role')
    if role not in {'L3', 'L4'}:
        raise HTTPException(403, 'Solo L4 responsable o L3 coordinador puede reasignar')
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(422, 'El motivo de reasignación es obligatorio')
    if role == 'L3' and payload.responsible_id is None:
        raise HTTPException(422, 'L3 debe identificar al nuevo responsable L4')
    target_responsible_id = payload.responsible_id or user['collaborator_id']
    if payload.assignee_id == user['collaborator_id']:
        raise HTTPException(400, 'El nuevo ejecutor debe ser un colaborador L5 distinto al actor')
    current_actor = actor(user)
    try:
        with transaction.atomic():
            task, membership = lock_task_for_reassignment(
                task_id, user['collaborator_id'], target_responsible_id, payload.assignee_id,
            )
            if task.assignee_id == membership.developer_id and task.responsible_id == target_responsible_id:
                raise HTTPException(409, 'La tarea ya está asignada a ese ejecutor y responsable')
            if task.status not in {'En proceso', 'Observada'}:
                if task.status == 'En revisión':
                    raise HTTPException(409, 'L4 debe resolver la revisión abierta antes de reasignar')
                raise HTTPException(409, 'Solo tareas En proceso u Observadas admiten reasignación')
            previous_status = task.status
            previous_assignee_id = task.assignee_id
            previous_responsible_id = task.responsible_id
            task.assignee_id = membership.developer_id
            task.responsible_id = target_responsible_id
            task.assigned_at = timezone.now()
            if previous_status == 'En proceso':
                task.status = 'Asignada'
            task.save(update_fields=['assignee', 'responsible', 'assigned_at', 'status'])
            TaskEvent.objects.create(
                task=task, event_type='ejecutor_reasignado', actor=current_actor,
                previous_status=previous_status, new_status=task.status,
                previous_assignee_id=previous_assignee_id, assignee_id=membership.developer_id,
                previous_responsible_id=previous_responsible_id,
                responsible_id=target_responsible_id, reason=reason,
                is_blocked_before=task.is_blocked, is_blocked_after=task.is_blocked,
            )
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar la reasignación')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id), user)


@router.post('/{task_id}/remove-executor')
def remove_task_executor(
    task_id: int, payload: TaskExecutorRemoval, user: dict = Depends(get_current_user),
):
    role = user.get('role')
    if role not in {'L3', 'L4'}:
        raise HTTPException(403, 'Solo L4 responsable o L3 coordinador puede retirar ejecutores')
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(422, 'El motivo de retirada es obligatorio')
    current_actor = actor(user)
    try:
        with transaction.atomic():
            task = lock_task_for_executor_removal(task_id, user['collaborator_id'])
            if task.status not in {'Asignada', 'En proceso'}:
                if task.status == 'En revisión':
                    raise HTTPException(409, 'L4 debe resolver la revisión abierta antes de retirar al ejecutor')
                raise HTTPException(409, 'Solo tareas Asignadas o En proceso pueden quedar sin ejecutor')
            previous_status = task.status
            previous_assignee_id = task.assignee_id
            task.assignee = None
            task.assigned_at = None
            task.status = 'Pendiente'
            task.save(update_fields=['assignee', 'assigned_at', 'status'])
            TaskEvent.objects.create(
                task=task, event_type='ejecutor_retirado', actor=current_actor,
                previous_status=previous_status, new_status='Pendiente',
                previous_assignee_id=previous_assignee_id, assignee=None,
                responsible_id=task.responsible_id,
                previous_responsible_id=task.responsible_id, reason=reason,
                is_blocked_before=task.is_blocked, is_blocked_after=task.is_blocked,
            )
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar la retirada del ejecutor')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id), user)


@router.post('/{task_id}/block')
def block_task(task_id: int, payload: TaskBlockInput, user: dict = Depends(get_current_user)):
    role = user.get('role')
    if role not in {'L3', 'L4'}:
        raise HTTPException(403, 'Solo L3 coordinador o L4 responsable puede bloquear tareas')
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(422, 'El impedimento debe indicar un motivo')
    evidence = (payload.evidence or '').strip()
    current_actor = actor(user)
    try:
        with transaction.atomic():
            task = lock_task_for_block_action(task_id, user['collaborator_id'], role)
            if task.status == 'Cancelada':
                raise HTTPException(409, 'Una tarea Cancelada no admite nuevas condiciones de bloqueo')
            if task.is_blocked:
                raise HTTPException(409, 'La tarea ya está bloqueada')
            if task.status == 'Finalizada':
                raise HTTPException(409, 'T-03 no define declarar bloqueos sobre tareas Finalizadas')
            previous_blocked = task.is_blocked
            task.is_blocked = True
            task.block_reason = reason
            task.block_evidence = evidence
            task.save(update_fields=['is_blocked', 'block_reason', 'block_evidence'])
            TaskEvent.objects.create(
                task=task, event_type='bloqueo_declarado', actor=current_actor,
                previous_status=task.status, new_status=task.status,
                assignee_id=task.assignee_id, responsible_id=task.responsible_id,
                previous_responsible_id=task.responsible_id,
                is_blocked_before=previous_blocked, is_blocked_after=True,
                reason=reason, evidence=evidence,
            )
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar el bloqueo')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id), user)


@router.post('/{task_id}/unblock')
def unblock_task(task_id: int, payload: TaskBlockInput, user: dict = Depends(get_current_user)):
    role = user.get('role')
    if role not in {'L3', 'L4'}:
        raise HTTPException(403, 'Solo L3 coordinador o L4 responsable puede levantar bloqueos')
    resolution = payload.reason.strip()
    if not resolution:
        raise HTTPException(422, 'El resultado del levantamiento es obligatorio')
    evidence = (payload.evidence or '').strip()
    current_actor = actor(user)
    try:
        with transaction.atomic():
            task = lock_task_for_block_action(task_id, user['collaborator_id'], role)
            if task.status == 'Cancelada':
                raise HTTPException(409, 'Una tarea Cancelada conserva su historial de bloqueo sin nuevas operaciones')
            if not task.is_blocked:
                raise HTTPException(409, 'La tarea no tiene un bloqueo vigente')
            previous_blocked = task.is_blocked
            task.is_blocked = False
            task.block_reason = ''
            task.block_evidence = ''
            task.save(update_fields=['is_blocked', 'block_reason', 'block_evidence'])
            TaskEvent.objects.create(
                task=task, event_type='bloqueo_levantado', actor=current_actor,
                previous_status=task.status, new_status=task.status,
                assignee_id=task.assignee_id, responsible_id=task.responsible_id,
                previous_responsible_id=task.responsible_id,
                is_blocked_before=previous_blocked, is_blocked_after=False,
                reason=resolution, evidence=evidence,
            )
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar el levantamiento del bloqueo')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id), user)


@router.post('/{task_id}/incident')
def report_task_incident(
    task_id: int, payload: TaskIncidentInput, user: dict = Depends(get_current_user),
):
    if user.get('role') != 'L5':
        raise HTTPException(403, 'Solo L5 ejecutor informa incidencias de ejecución')
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(422, 'La incidencia debe incluir un motivo')
    evidence = (payload.evidence or '').strip()
    current_actor = actor(user)
    try:
        with transaction.atomic():
            task = lock_task_for_l5(task_id, user['collaborator_id'])
            if task.status not in {'Asignada', 'En proceso', 'En revisión', 'Observada'}:
                raise HTTPException(409, 'La tarea no está en una fase operativa para informar una incidencia')
            TaskEvent.objects.create(
                task=task, event_type='incidencia_comunicada', actor=current_actor,
                previous_status=task.status, new_status=task.status,
                assignee_id=task.assignee_id, responsible_id=task.responsible_id,
                previous_responsible_id=task.responsible_id,
                is_blocked_before=task.is_blocked, is_blocked_after=task.is_blocked,
                reason=reason, evidence=evidence,
            )
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar la incidencia')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id), user)


@router.post('/{task_id}/start')
def start_task(task_id: int, user: dict = Depends(get_current_user)):
    if user.get('role') != 'L5':
        raise HTTPException(403, 'Solo el ejecutor L5 puede iniciar esta tarea')
    current_actor = actor(user)
    try:
        with transaction.atomic():
            task = lock_task_for_l5(task_id, user['collaborator_id'])
            if task.status not in {'Asignada', 'Observada'}:
                raise HTTPException(409, 'La tarea no está disponible para iniciar o retomar')
            previous_status = task.status
            task.status = 'En proceso'
            task.save(update_fields=['status'])
            TaskEvent.objects.create(
                task=task,
                event_type='iniciada' if previous_status == 'Asignada' else 'correccion_iniciada',
                actor=current_actor,
                previous_status=previous_status,
                new_status=task.status,
                assignee_id=task.assignee_id,
                is_blocked_before=task.is_blocked, is_blocked_after=task.is_blocked,
            )
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar el inicio de la tarea')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id), user)


@router.post('/{task_id}/submit-review')
def submit_task_for_review(
    task_id: int, payload: TaskSubmission, user: dict = Depends(get_current_user),
):
    if user.get('role') != 'L5':
        raise HTTPException(403, 'Solo el ejecutor L5 puede presentar el resultado')
    result_text = payload.result_text.strip()
    if not result_text:
        raise HTTPException(422, 'El resultado presentado es obligatorio')
    current_actor = actor(user)
    try:
        with transaction.atomic():
            task = lock_task_for_l5(task_id, user['collaborator_id'])
            if task.status != 'En proceso':
                raise HTTPException(409, 'Solo una tarea En proceso puede presentarse a revisión')
            task.status = 'En revisión'
            task.save(update_fields=['status'])
            TaskEvent.objects.create(
                task=task, event_type='resultado_presentado', actor=current_actor,
                previous_status='En proceso', new_status='En revisión',
                assignee_id=task.assignee_id, result_text=result_text,
                is_blocked_before=task.is_blocked, is_blocked_after=task.is_blocked,
            )
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar el resultado de la tarea')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id), user)


@router.post('/{task_id}/review')
def review_task(task_id: int, payload: TaskReview, user: dict = Depends(get_current_user)):
    if user.get('role') != 'L4':
        raise HTTPException(403, 'Solo L4 responsable puede resolver la revisión')
    reason = (payload.reason or '').strip()
    if payload.resolution == 'Observada' and not reason:
        raise HTTPException(422, 'La observación debe indicar el motivo de corrección')
    current_actor = actor(user)
    try:
        with transaction.atomic():
            task = lock_task_for_l4_review(task_id, user['collaborator_id'])
            if not task_queryset(user).filter(pk=task_id).exists():
                raise HTTPException(404, 'Tarea no encontrada en tu responsabilidad')
            if task.status != 'En revisión':
                raise HTTPException(409, 'Solo una tarea En revisión puede resolverse')
            previous_status = task.status
            task.status = payload.resolution
            task.save(update_fields=['status'])
            TaskEvent.objects.create(
                task=task,
                event_type='observada' if payload.resolution == 'Observada' else 'aprobada_revision',
                actor=current_actor,
                previous_status=previous_status,
                new_status=task.status,
                assignee_id=task.assignee_id,
                reason=reason,
                is_blocked_before=task.is_blocked, is_blocked_after=task.is_blocked,
            )
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar la resolución de revisión')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id), user)


@router.post('/{task_id}/reopen')
def reopen_task(task_id: int, payload: TaskReopen, user: dict = Depends(get_current_user)):
    if user.get('role') != 'L3':
        raise HTTPException(403, 'Solo L3 puede autorizar la reapertura de una tarea')
    reason = payload.reason.strip()
    result_text = payload.result_text.strip()
    if not reason or not result_text:
        raise HTTPException(422, 'La justificación y el resultado de la reapertura son obligatorios')
    current_actor = Collaborator.objects.filter(
        pk=user['collaborator_id'], is_active=True, role__level='L3',
    ).first()
    if current_actor is None:
        raise HTTPException(403, 'El actor ya no tiene una cuenta L3 activa')
    try:
        with transaction.atomic():
            task = lock_task_for_l3_reopen(task_id, current_actor.id)
            previous_status = task.status
            task.status = 'Observada'
            task.save(update_fields=['status'])
            TaskEvent.objects.create(
                task=task, event_type='reapertura_autorizada', actor=current_actor,
                previous_status=previous_status, new_status='Observada',
                assignee_id=task.assignee_id, responsible_id=task.responsible_id,
                reason=reason, result_text=result_text,
                is_blocked_before=task.is_blocked, is_blocked_after=task.is_blocked,
            )
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar la reapertura de la tarea')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id), user)


@router.post('/{task_id}/cancellation/proposal')
def propose_task_cancellation(
    task_id: int, payload: TaskCancellationProposal, user: dict = Depends(get_current_user),
):
    if user.get('role') != 'L4':
        raise HTTPException(403, 'Solo L4 responsable puede proponer cancelar la tarea')
    reason, effects, evidence = payload.reason.strip(), payload.effects.strip(), (payload.evidence or '').strip()
    if not reason or not effects:
        raise HTTPException(422, 'La propuesta debe incluir motivo y efectos previstos')
    current_actor = Collaborator.objects.filter(
        pk=user['collaborator_id'], is_active=True, role__level='L4',
    ).first()
    if current_actor is None:
        raise HTTPException(403, 'El actor ya no tiene una cuenta L4 activa')
    try:
        with transaction.atomic():
            task = lock_task_for_cancellation(task_id, current_actor.id, 'L4')
            if task.status not in CANCELABLE_TASK_STATUSES:
                raise HTTPException(409, 'T-07 no permite proponer la cancelación desde este estado')
            event = cancellation_event(
                task, 'cancelacion_propuesta', current_actor, reason,
                {'effects': effects}, evidence,
            )
            event.result_text = json.dumps(
                {'proposal_event_id': event.id, 'effects': effects}, ensure_ascii=False,
            )
            event.save(update_fields=['result_text'])
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar la propuesta de cancelación')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id), user)


@router.post('/{task_id}/cancellation/evaluation')
def evaluate_task_cancellation(
    task_id: int, payload: TaskCancellationEvaluation, user: dict = Depends(get_current_user),
):
    if user.get('role') != 'L3':
        raise HTTPException(403, 'Solo L3 coordinador puede evaluar la cancelación')
    current_actor = Collaborator.objects.filter(
        pk=user['collaborator_id'], is_active=True, role__level='L3',
    ).first()
    if current_actor is None:
        raise HTTPException(403, 'El actor ya no tiene una cuenta L3 activa')
    reason = payload.reason.strip()
    follow_up = (payload.obligation_follow_up or '').strip()
    evidence = (payload.evidence or '').strip()
    if not reason or not all((
        payload.work_assessment.strip(), payload.evidence_assessment.strip(),
        payload.dependency_assessment.strip(), payload.obligation_assessment.strip(),
        payload.commercial_assessment.strip(),
    )):
        raise HTTPException(422, 'La evaluación debe cubrir trabajo, evidencia, dependencias, obligaciones e impacto comercial')
    if payload.obligation_disposition == 'follow_up' and not follow_up:
        raise HTTPException(422, 'Identifica el seguimiento de la obligación pendiente')
    if payload.decision == 'autorizar' and payload.obligation_disposition == 'unresolved':
        raise HTTPException(409, 'La cancelación queda pendiente hasta resolver el tratamiento necesario de las obligaciones')
    if payload.decision == 'autorizar' and payload.commercial_impact == 'existing_authorization' and not evidence:
        raise HTTPException(422, 'Referencia la autorización comercial vigente que cubre esta cancelación')
    try:
        with transaction.atomic():
            task = lock_task_for_cancellation(task_id, current_actor.id, 'L3')
            if task.status not in CANCELABLE_TASK_STATUSES:
                raise HTTPException(409, 'T-07 no permite cancelar una tarea desde este estado')
            events = list(task.events.all())
            workflow, proposal = valid_cancellation_proposal(task, events)
            if not proposal:
                raise HTTPException(409, 'No existe una propuesta vigente de L4 para evaluar')
            if workflow.get('evaluation') and workflow['evaluation'].event_type != 'cancelacion_pendiente':
                raise HTTPException(409, 'La propuesta ya fue autorizada o denegada; L4 debe presentar una propuesta nueva')
            event_type = {
                'pendiente': 'cancelacion_pendiente',
                'autorizar': 'cancelacion_autorizada',
                'denegar': 'cancelacion_denegada',
            }[payload.decision]
            data = {
                'proposal_event_id': proposal.id, 'decision': payload.decision,
                'work_assessment': payload.work_assessment.strip(),
                'evidence_assessment': payload.evidence_assessment.strip(),
                'dependency_assessment': payload.dependency_assessment.strip(),
                'obligation_disposition': payload.obligation_disposition,
                'obligation_assessment': payload.obligation_assessment.strip(),
                'obligation_follow_up': follow_up,
                'commercial_impact': payload.commercial_impact,
                'commercial_assessment': payload.commercial_assessment.strip(),
            }
            cancellation_event(task, event_type, current_actor, reason, data, evidence)
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar la evaluación de cancelación')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id), user)


@router.post('/{task_id}/cancellation/commercial-review')
def review_task_cancellation_commercially(
    task_id: int, payload: TaskCancellationCommercialReview,
    user: dict = Depends(get_current_user),
):
    if user.get('role') != 'L2':
        raise HTTPException(403, 'Solo L2 competente puede intervenir en las consecuencias comerciales')
    reason, evidence = payload.reason.strip(), payload.evidence.strip()
    if not reason or not evidence:
        raise HTTPException(422, 'La intervención comercial requiere resultado y referencia de respaldo')
    current_actor = Collaborator.objects.filter(
        pk=user['collaborator_id'], is_active=True, role__level='L2',
    ).first()
    if current_actor is None:
        raise HTTPException(403, 'El actor ya no tiene una cuenta L2 activa')
    candidate = Task.objects.filter(pk=task_id).values('project_id').first()
    if candidate is None:
        raise HTTPException(404, 'Tarea no encontrada para revisión comercial')
    try:
        with transaction.atomic():
            coordinations = lock_project_coordinations(candidate['project_id'])
            task = Task.objects.select_for_update().filter(pk=task_id).first()
            if task is None or task.project_id != candidate['project_id']:
                raise HTTPException(409, 'La tarea cambió durante la revisión')
            events = list(task.events.all())
            workflow = cancellation_workflow(task, events)
            evaluation = workflow.get('evaluation')
            if not evaluation or evaluation.event_type != 'cancelacion_autorizada' or workflow.get('stale'):
                raise HTTPException(409, 'No hay una autorización técnica vigente para revisar')
            if (workflow.get('evaluation_data') or {}).get('commercial_impact') != 'new_or_uncertain':
                raise HTTPException(409, 'La evaluación no requiere intervención comercial nueva')
            coordination = next((
                item for item in coordinations
                if item.coordinator_id == evaluation.actor_id
                and item.assigned_by_id == current_actor.id
            ), None)
            if coordination is None:
                raise HTTPException(404, 'No eres el L2 designador de la coordinación que autorizó la evaluación')
            if workflow.get('commercial') and workflow['commercial'].event_type == 'revision_comercial_resuelta':
                raise HTTPException(409, 'La intervención comercial de esta evaluación ya fue registrada')
            event_type = (
                'revision_comercial_resuelta' if payload.decision == 'resuelta'
                else 'revision_comercial_pend'
            )
            cancellation_event(
                task, event_type, current_actor, reason,
                {
                    'proposal_event_id': workflow['proposal'].id,
                    'evaluation_event_id': evaluation.id,
                    'decision': payload.decision,
                }, evidence,
            )
    except IntegrityError:
        raise HTTPException(409, 'No se pudo registrar la intervención comercial')
    return {'task_id': task_id, 'decision': payload.decision, 'status': 'pendiente' if payload.decision == 'pendiente' else 'resuelta'}


@router.post('/{task_id}/cancellation/apply')
def apply_task_cancellation(task_id: int, user: dict = Depends(get_current_user)):
    if user.get('role') != 'L3':
        raise HTTPException(403, 'Solo L3 coordinador puede aplicar la cancelación autorizada')
    current_actor = Collaborator.objects.filter(
        pk=user['collaborator_id'], is_active=True, role__level='L3',
    ).first()
    if current_actor is None:
        raise HTTPException(403, 'El actor ya no tiene una cuenta L3 activa')
    try:
        with transaction.atomic():
            task = lock_task_for_cancellation(task_id, current_actor.id, 'L3')
            if task.status not in CANCELABLE_TASK_STATUSES:
                raise HTTPException(409, 'La tarea ya no se encuentra en un estado cancelable')
            events = list(task.events.all())
            workflow, proposal = valid_cancellation_proposal(task, events)
            evaluation = workflow.get('evaluation')
            evaluation_data = workflow.get('evaluation_data') or {}
            if not proposal or not evaluation or evaluation.event_type != 'cancelacion_autorizada':
                raise HTTPException(409, 'La cancelación requiere autorización técnica vigente')
            if evaluation.actor_id != current_actor.id:
                raise HTTPException(403, 'La aplicación debe realizarla el L3 que autorizó la propuesta vigente')
            if evaluation_data.get('obligation_disposition') == 'unresolved':
                raise HTTPException(409, 'El tratamiento necesario de obligaciones sigue sin resolver')
            commercial = workflow.get('commercial')
            commercial_id = None
            if evaluation_data.get('commercial_impact') == 'new_or_uncertain':
                if not commercial or commercial.event_type != 'revision_comercial_resuelta':
                    raise HTTPException(409, 'La intervención comercial de L2 sigue pendiente')
                commercial_id = commercial.id
            previous_status = task.status
            task.status = 'Cancelada'
            task.save(update_fields=['status'])
            TaskEvent.objects.create(
                task=task, event_type='cancelacion_aplicada', actor=current_actor,
                previous_status=previous_status, new_status='Cancelada',
                assignee_id=task.assignee_id, responsible_id=task.responsible_id,
                is_blocked_before=task.is_blocked, is_blocked_after=task.is_blocked,
                reason=evaluation.reason, evidence=json.dumps({
                    'proposal_event_id': proposal.id,
                    'evaluation_event_id': evaluation.id,
                    'commercial_event_id': commercial_id,
                }),
                result_text=json.dumps({
                    'proposal_event_id': proposal.id,
                    'evaluation_event_id': evaluation.id,
                    'commercial_event_id': commercial_id,
                    'note': 'Cancelación aplicada; antecedentes, trabajo y obligaciones se conservan.',
                }, ensure_ascii=False),
            )
    except IntegrityError:
        raise HTTPException(409, 'No se pudo aplicar la cancelación de la tarea')
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id), user)
