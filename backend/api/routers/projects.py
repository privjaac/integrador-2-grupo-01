import json
from datetime import datetime

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from fastapi import Depends, HTTPException, status

from api.dependencies import get_current_user
from api.router import APIRouter
from api.schemas.projects import (
    ProjectCommercialAuthorizationCreate, ProjectCommercialAuthorizationWithdrawal,
    ProjectCancellationCreate, ProjectCancellationDecision,
    ProjectCancellationEffectivity, ProjectCancellationTechnicalEvaluation,
    ProjectCreate, ProjectDeliveryAuthorizationCreate, ProjectExecutionReturn,
    ProjectDeliveryCreate, ProjectDeliveryFormalizeInput, ProjectDeliveryTechnicalReviewInput,
    ProjectReadyForDeliveryInput, ProjectResponse, ProjectStartReadiness,
    ProjectTaskClassificationInput, ProjectTechnicalEvaluationInput,
    ProjectValidationReadiness,
)
from api.schemas.clients import ProjectServiceLinkInput
from clients.models import (
    Client, Collaborator, Project, ProjectCommercialAuthorization,
    ProjectCancellation, ProjectCancellationEvent,
    ProjectCommercialAuthorizationEvent, ProjectCoordination, ProjectDeliveryAuthorization,
    ProjectDeliveryAuthorizationEvent, ProjectDelivery, ProjectDeliveryTechnicalReview,
    ProjectDeliveryTransition, ProjectEvent, ProjectTaskClassification, ProjectTechnicalEvaluation,
    Task, TaskEvent, ContractedService, ProjectContractedService,
)

router = APIRouter()


def require_project_reader(user: dict) -> None:
    if user.get('role') not in {'L2', 'L3'}:
        raise HTTPException(status_code=403, detail='No tienes permiso para consultar proyectos')


def require_project_creator(user: dict) -> None:
    if user.get('role') != 'L2':
        raise HTTPException(status_code=403, detail='No tienes permiso para crear proyectos')


def active_l3_actor(user: dict) -> Collaborator:
    if user.get('role') != 'L3':
        raise HTTPException(status_code=403, detail='La operación corresponde a L3')
    actor = Collaborator.objects.filter(
        pk=user['collaborator_id'], is_active=True, role__level='L3',
    ).first()
    if actor is None:
        raise HTTPException(status_code=403, detail='El colaborador L3 no está activo')
    return actor


def active_l2_actor(user: dict) -> Collaborator:
    if user.get('role') != 'L2':
        raise HTTPException(status_code=403, detail='La operación comercial corresponde a L2')
    actor = Collaborator.objects.filter(
        pk=user['collaborator_id'], is_active=True, role__level='L2',
    ).first()
    if actor is None:
        raise HTTPException(status_code=403, detail='El colaborador L2 no está activo')
    return actor


def lock_coordinated_project(project_id: int, actor: Collaborator) -> Project:
    project = Project.objects.select_for_update(of=('self',)).filter(pk=project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail='Proyecto no encontrado')
    coordination = ProjectCoordination.objects.select_for_update(of=('self',)).filter(
        project_id=project_id, coordinator=actor, is_active=True,
        coordinator__is_active=True, coordinator__role__level='L3',
    ).order_by('id').first()
    if coordination is None:
        raise HTTPException(status_code=404, detail='Proyecto fuera de tu coordinación vigente')
    ensure_project_not_cancelled(project_id)
    return project


def ensure_project_not_cancelled(project_id: int) -> None:
    if ProjectCancellationEvent.objects.filter(
        cancellation__project_id=project_id, event_type='efectiva',
        effective_at__lte=timezone.now(),
    ).exists():
        raise HTTPException(status_code=409, detail='El alcance del proyecto tiene una cancelación efectiva')


def cancellation_latest_event(cancellation: ProjectCancellation):
    return cancellation.events.order_by('-occurred_at', '-id').first()


def cancellation_is_open(cancellation: ProjectCancellation) -> bool:
    latest = cancellation_latest_event(cancellation)
    return latest is None or latest.event_type not in {'denegada', 'efectiva'}


def cancellation_response(cancellation: ProjectCancellation) -> dict:
    return {
        'id': cancellation.id,
        'project_id': cancellation.project_id,
        'opened_by_id': cancellation.opened_by_id,
        'opened_by_name': f'{cancellation.opened_by.first_name} {cancellation.opened_by.last_name}',
        'opened_at': cancellation.opened_at.isoformat(),
        'cancelled_scope': cancellation.cancelled_scope,
        'reason': cancellation.reason,
        'evidence': cancellation.evidence,
        'events': [
            {
                'event_type': item.event_type,
                'actor_id': item.actor_id,
                'actor_name': f'{item.actor.first_name} {item.actor.last_name}',
                'reason': item.reason,
                'evidence': item.evidence,
                'data': item.data,
                'effective_at': item.effective_at.isoformat() if item.effective_at else None,
                'occurred_at': item.occurred_at.isoformat(),
            }
            for item in cancellation.events.select_related('actor').all()
        ],
    }


def project_cancellation_audit(project: Project, actor: Collaborator, event_type: str, reason: str, data: dict):
    snapshot = project.status
    ProjectEvent.objects.create(
        event_type=event_type, project=project, actor=actor,
        previous_status=snapshot, new_status=snapshot,
        reason=reason, evidence=json.dumps(data, ensure_ascii=False),
    )


def normalized_scope(value: str) -> str:
    return ' '.join(value.split()).casefold()


def project_scope_snapshot(project: Project) -> str:
    if project.scope and project.scope.strip():
        return project.scope.strip()
    start_event = ProjectEvent.objects.filter(
        project=project, event_type='inicio_ejecucion',
    ).select_related('commercial_authorization').order_by('-occurred_at', '-id').first()
    if start_event and start_event.commercial_authorization_id:
        return start_event.commercial_authorization.authorized_scope.strip()
    raise HTTPException(status_code=409, detail='No se puede acreditar el alcance vigente del proyecto')


def current_task_snapshot(project_id: int, *, lock: bool = False) -> tuple[list[dict], dict[int, Task]]:
    queryset = Task.objects.filter(project_id=project_id).order_by('id')
    if lock:
        queryset = queryset.select_for_update(of=('self',))
    tasks = list(queryset)
    classifications = {
        item.task_id: item
        for item in ProjectTaskClassification.objects.filter(
            project_id=project_id, is_current=True,
        )
    }
    snapshot = []
    task_by_id = {task.id: task for task in tasks}
    for task in tasks:
        last_event = TaskEvent.objects.filter(task_id=task.id).order_by('-occurred_at', '-id').first()
        classification = classifications.get(task.id)
        snapshot.append({
            'task_id': task.id,
            'classification_id': classification.id if classification else None,
            'is_mandatory': classification.is_mandatory if classification else None,
            'status': task.status,
            'is_blocked': task.is_blocked,
            'last_event_id': last_event.id if last_event else None,
            'last_event_type': last_event.event_type if last_event else None,
            'last_event_status': last_event.new_status if last_event else None,
        })
    return snapshot, task_by_id


def task_close_issues(snapshot: list[dict], optional_assessments: list[dict]) -> list[str]:
    issues = []
    assessment_ids = {item.get('task_id') for item in optional_assessments}
    for row in snapshot:
        task_id = row['task_id']
        if row['classification_id'] is None:
            issues.append(f'La tarea #{task_id} no tiene clasificación vigente')
            continue
        if row['is_mandatory']:
            if row['status'] != 'Finalizada' or row['is_blocked']:
                issues.append(f'La tarea obligatoria #{task_id} no está aprobada y sin bloqueo vigente')
            elif row['last_event_type'] != 'aprobada_revision' or row['last_event_status'] != 'Finalizada':
                issues.append(f'La tarea obligatoria #{task_id} no conserva aprobación vigente')
        elif row['status'] != 'Finalizada' and task_id not in assessment_ids:
            issues.append(f'La tarea opcional pendiente #{task_id} no fue evaluada expresamente por L3')
    expected_optional_ids = {
        row['task_id'] for row in snapshot
        if row['classification_id'] is not None and not row['is_mandatory'] and row['status'] != 'Finalizada'
    }
    if assessment_ids != expected_optional_ids:
        issues.append('La evaluación debe corresponder exactamente a las tareas opcionales pendientes actuales')
    return issues


def active_delivery_authorizations(project_id: int, now=None):
    now = now or timezone.now()
    closed_events = ProjectDeliveryAuthorizationEvent.objects.filter(
        authorization_id=OuterRef('pk'), event_type__in=['retirada', 'sustituida'],
    )
    return ProjectDeliveryAuthorization.objects.filter(
        project_id=project_id, effective_at__lte=now, conditions_accredited=True,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now),
    ).annotate(is_closed=Exists(closed_events)).filter(is_closed=False)


def delivery_authorization_valid_at(authorization: ProjectDeliveryAuthorization, occurred_at) -> bool:
    if (
        not authorization.conditions_accredited
        or authorization.effective_at > occurred_at
        or (authorization.expires_at is not None and authorization.expires_at <= occurred_at)
    ):
        return False
    return not authorization.events.filter(
        event_type__in=['retirada', 'sustituida'], occurred_at__lte=occurred_at,
    ).exists()


def project_delivery_response(delivery: ProjectDelivery) -> dict:
    return {
        'id': delivery.id,
        'project_id': delivery.project_id,
        'delivery_type': delivery.delivery_type,
        'scope': delivery.scope,
        'scope_within_authorization': delivery.scope_within_authorization,
        'covers_project_scope': delivery.covers_project_scope,
        'version_reference': delivery.version_reference,
        'recipient': delivery.recipient,
        'delivery_method': delivery.delivery_method,
        'performed_by': delivery.performed_by,
        'evidence_reference': delivery.evidence_reference,
        'occurred_at': delivery.occurred_at.isoformat(),
        'recorded_at': delivery.recorded_at.isoformat(),
        'recorded_by_id': delivery.recorded_by_id,
        'recorded_by_name': f'{delivery.recorded_by.first_name} {delivery.recorded_by.last_name}',
        'preparation_authorization_id': delivery.preparation_authorization_id,
        'technical_reviews': [
            {
                'actor_id': item.actor_id,
                'actor_name': f'{item.actor.first_name} {item.actor.last_name}',
                'version_reference': item.version_reference,
                'technical_evaluation_id': item.technical_evaluation_id,
                'satisfactory': item.satisfactory,
                'technical_enablement_status': item.technical_enablement_status,
                'result_summary': item.result_summary,
                'evidence': item.evidence,
                'reviewed_at': item.reviewed_at.isoformat(),
            }
            for item in ProjectDeliveryTechnicalReview.objects.filter(
                project_id=delivery.project_id,
                version_reference__iexact=delivery.version_reference,
            ).select_related('actor').order_by('reviewed_at', 'id')
        ],
        'formalized': delivery.transition_links.exists(),
    }


def to_response(project: Project) -> dict:
    return {
        'id': project.id,
        'client_id': project.client_id,
        'client_name': project.client.name,
        'name': project.name,
        'objective': project.objective,
        'scope': project.scope,
        'status': project.status,
        'events': [
            {
                'event_type': event.event_type,
                'actor_id': event.actor_id,
                'actor_name': f'{event.actor.first_name} {event.actor.last_name}',
                'previous_status': event.previous_status,
                'new_status': event.new_status,
                'reason': event.reason,
                'evidence': event.evidence,
                'occurred_at': event.occurred_at.isoformat(),
                'commercial_authorization_id': event.commercial_authorization_id,
                'technical_evaluation_id': event.technical_evaluation_id,
                'delivery_authorization_id': event.delivery_authorization_id,
                'delivery_record_ids': list(event.delivery_records.values_list('id', flat=True)),
            }
            for event in project.events.select_related('actor').all()
        ],
    }


@router.post('/{project_id}/technical-validation', response_model=ProjectResponse)
def enter_technical_validation(
    project_id: int,
    payload: ProjectValidationReadiness,
    user: dict = Depends(get_current_user),
):
    if user.get('role') != 'L3':
        raise HTTPException(status_code=403, detail='Solo L3 puede autorizar el ingreso a validación técnica')
    actor = Collaborator.objects.filter(
        pk=user['collaborator_id'], is_active=True, role__level='L3',
    ).first()
    if actor is None:
        raise HTTPException(status_code=403, detail='El colaborador L3 no está activo')

    try:
        with transaction.atomic():
            project = Project.objects.select_for_update(of=('self',)).select_related('client').filter(
                pk=project_id,
            ).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
            ensure_project_not_cancelled(project_id)
            coordination_ids = list(ProjectCoordination.objects.filter(
                project_id=project_id, coordinator=actor, is_active=True,
                coordinator__is_active=True, coordinator__role__level='L3',
            ).order_by('id').values_list('id', flat=True))
            if not coordination_ids:
                if not Project.objects.filter(pk=project_id).exists():
                    raise HTTPException(status_code=404, detail='Proyecto no encontrado')
                raise HTTPException(status_code=404, detail='Proyecto fuera de tu coordinación vigente')
            locked_coordinations = list(ProjectCoordination.objects.select_for_update(of=('self',)).filter(
                pk__in=coordination_ids, is_active=True,
                coordinator__is_active=True, coordinator__role__level='L3',
            ).order_by('id'))
            if not locked_coordinations:
                raise HTTPException(status_code=404, detail='Proyecto fuera de tu coordinación vigente')
            if project.status != 'En ejecución':
                raise HTTPException(status_code=409, detail='El proyecto debe estar En ejecución')
            if not all((
                payload.scope_within_current_commitment,
                payload.criteria_identifiable,
                payload.results_and_evidence_available,
                payload.validation_conditions_ready,
                payload.responsible_parties_identified,
                payload.dependencies_ready,
                payload.pending_obligations_assessed,
            )):
                raise HTTPException(
                    status_code=409,
                    detail='La preparación para validar está incompleta; no se aplicó el cambio de estado',
                )
            previous_status = project.status
            project.status = 'En validación técnica'
            project.save(update_fields=['status'])
            ProjectEvent.objects.create(
                event_type='ingreso_validacion_tecnica', project=project, actor=actor,
                previous_status=previous_status, new_status=project.status,
                reason=payload.reason.strip(),
                evidence=(
                    'Alcance incluido en compromiso vigente: sí\n'
                    'Criterios identificables: sí\n'
                    'Resultados y evidencia disponibles: sí\n'
                    'Condiciones y recursos de validación listos: sí\n'
                    'Responsables identificados: sí\n'
                    'Dependencias indispensables listas: sí\n'
                    'Pendientes y obligaciones evaluados: sí\n'
                    f"Evidencia declarada: {payload.evidence.strip()}"
                ),
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail='No se pudo registrar la transición por un cambio concurrente')

    return to_response(Project.objects.select_related('client').get(pk=project_id))


@router.post('/{project_id}/return-to-execution', response_model=ProjectResponse)
def return_project_to_execution(
    project_id: int,
    payload: ProjectExecutionReturn,
    user: dict = Depends(get_current_user),
):
    if user.get('role') != 'L3':
        raise HTTPException(status_code=403, detail='Solo L3 puede autorizar la devolución a ejecución')
    actor = Collaborator.objects.filter(
        pk=user['collaborator_id'], is_active=True, role__level='L3',
    ).first()
    if actor is None:
        raise HTTPException(status_code=403, detail='El colaborador L3 no está activo')
    if not all((
        payload.additional_execution_required,
        payload.materially_affects_validation,
        payload.within_current_commitment,
    )):
        raise HTTPException(status_code=409, detail='La devolución no cumple las condiciones autorizadas')

    try:
        with transaction.atomic():
            project = Project.objects.select_for_update(of=('self',)).filter(pk=project_id).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
            ensure_project_not_cancelled(project_id)
            coordination_ids = list(ProjectCoordination.objects.filter(
                project_id=project_id, coordinator=actor, is_active=True,
                coordinator__is_active=True, coordinator__role__level='L3',
            ).order_by('id').values_list('id', flat=True))
            if not coordination_ids:
                if not Project.objects.filter(pk=project_id).exists():
                    raise HTTPException(status_code=404, detail='Proyecto no encontrado')
                raise HTTPException(status_code=404, detail='Proyecto fuera de tu coordinación vigente')
            locked_coordinations = list(ProjectCoordination.objects.select_for_update(of=('self',)).filter(
                pk__in=coordination_ids, is_active=True,
                coordinator__is_active=True, coordinator__role__level='L3',
            ).order_by('id'))
            if not locked_coordinations:
                raise HTTPException(status_code=404, detail='Proyecto fuera de tu coordinación vigente')
            if project.status != 'En validación técnica':
                raise HTTPException(status_code=409, detail='El proyecto debe estar En validación técnica')
            previous_status = project.status
            project.status = 'En ejecución'
            project.save(update_fields=['status'])
            ProjectEvent.objects.create(
                event_type='devolucion_ejecucion', project=project, actor=actor,
                previous_status=previous_status, new_status=project.status,
                reason=payload.reason.strip(),
                evidence=(
                    'Trabajo adicional necesario: sí\n'
                    'Afecta materialmente suficiencia/continuidad de validación: sí\n'
                    'Dentro del compromiso vigente: sí\n'
                    f'Evidencia: {payload.evidence.strip()}'
                ),
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail='No se pudo registrar la devolución por un cambio concurrente')

    return to_response(Project.objects.select_related('client').get(pk=project_id))


def active_commercial_authorizations(project_id: int, now=None):
    now = now or timezone.now()
    return ProjectCommercialAuthorization.objects.filter(
        project_id=project_id, effective_at__lte=now,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now),
    ).exclude(
        events__event_type__in=['retirada', 'sustituida'],
    )


def commercial_authorization_response(authorization: ProjectCommercialAuthorization, *, include_private: bool):
    result = {
        'id': authorization.id,
        'project_id': authorization.project_id,
        'authorized_by_id': authorization.authorized_by_id,
        'authorized_by_name': f'{authorization.authorized_by.first_name} {authorization.authorized_by.last_name}',
        'authorized_at': authorization.authorized_at.isoformat(),
        'effective_at': authorization.effective_at.isoformat(),
        'expires_at': authorization.expires_at.isoformat() if authorization.expires_at else None,
        'authorized_scope': authorization.authorized_scope,
    }
    if include_private:
        result.update({
            'commitment_reference': authorization.commitment_reference,
            'start_conditions': authorization.start_conditions,
            'start_conditions_accredited': authorization.start_conditions_accredited,
            'evidence_reference': authorization.evidence_reference,
            'events': [
                {
                    'event_type': event.event_type,
                    'actor_id': event.actor_id,
                    'actor_name': f'{event.actor.first_name} {event.actor.last_name}',
                    'reason': event.reason,
                    'replacement_id': event.replacement_id,
                    'occurred_at': event.occurred_at.isoformat(),
                }
                for event in authorization.events.select_related('actor').all()
            ],
        })
    return result


@router.post('/{project_id}/commercial-authorizations', status_code=status.HTTP_201_CREATED)
def authorize_project_start(
    project_id: int,
    payload: ProjectCommercialAuthorizationCreate,
    user: dict = Depends(get_current_user),
):
    if user.get('role') != 'L2':
        raise HTTPException(status_code=403, detail='Solo L2 puede habilitar comercialmente el inicio')
    actor = Collaborator.objects.filter(
        pk=user['collaborator_id'], is_active=True, role__level='L2',
    ).first()
    if actor is None:
        raise HTTPException(status_code=403, detail='El colaborador L2 no está activo')

    now = timezone.now()
    if payload.effective_at < now:
        raise HTTPException(status_code=422, detail='No se admiten habilitaciones comerciales retroactivas')
    if payload.expires_at is not None and payload.expires_at <= payload.effective_at:
        raise HTTPException(status_code=422, detail='El vencimiento debe ser posterior a la efectividad')
    if not payload.start_conditions_accredited:
        raise HTTPException(status_code=409, detail='L2 debe acreditar que las condiciones de inicio están satisfechas')
    if payload.replaces_authorization_id is not None and not payload.replacement_reason:
        raise HTTPException(status_code=422, detail='La sustitución requiere motivo')

    try:
        with transaction.atomic():
            project = Project.objects.select_for_update(of=('self',)).filter(pk=project_id).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
            ensure_project_not_cancelled(project_id)
            replaced = None
            if payload.replaces_authorization_id is not None:
                replaced = ProjectCommercialAuthorization.objects.select_for_update(of=('self',)).filter(
                    pk=payload.replaces_authorization_id, project=project,
                ).first()
                if replaced is None:
                    raise HTTPException(status_code=404, detail='La habilitación a sustituir no pertenece al proyecto')
                if replaced.events.filter(event_type__in=['retirada', 'sustituida']).exists():
                    raise HTTPException(status_code=409, detail='La habilitación ya fue retirada o sustituida')
            authorization = ProjectCommercialAuthorization.objects.create(
                project=project, authorized_by=actor,
                effective_at=payload.effective_at, expires_at=payload.expires_at,
                authorized_scope=payload.authorized_scope.strip(),
                commitment_reference=payload.commitment_reference.strip(),
                start_conditions=payload.start_conditions.strip(),
                start_conditions_accredited=payload.start_conditions_accredited,
                evidence_reference=payload.evidence_reference.strip(),
            )
            if replaced is not None:
                ProjectCommercialAuthorizationEvent.objects.create(
                    authorization=replaced, event_type='sustituida', actor=actor,
                    reason=payload.replacement_reason.strip(), replacement=authorization,
                )
    except IntegrityError:
        raise HTTPException(status_code=409, detail='La habilitación fue modificada concurrentemente')

    authorization = ProjectCommercialAuthorization.objects.select_related('authorized_by').get(pk=authorization.pk)
    return commercial_authorization_response(authorization, include_private=True)


@router.post('/{project_id}/commercial-authorizations/{authorization_id}/withdrawal')
def withdraw_project_start_authorization(
    project_id: int,
    authorization_id: int,
    payload: ProjectCommercialAuthorizationWithdrawal,
    user: dict = Depends(get_current_user),
):
    if user.get('role') != 'L2':
        raise HTTPException(status_code=403, detail='Solo L2 puede retirar una habilitación comercial')
    actor = Collaborator.objects.filter(
        pk=user['collaborator_id'], is_active=True, role__level='L2',
    ).first()
    if actor is None:
        raise HTTPException(status_code=403, detail='El colaborador L2 no está activo')
    try:
        with transaction.atomic():
            project = Project.objects.select_for_update(of=('self',)).filter(pk=project_id).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
            ensure_project_not_cancelled(project_id)
            authorization = ProjectCommercialAuthorization.objects.select_for_update(of=('self',)).filter(
                pk=authorization_id, project=project,
            ).first()
            if authorization is None:
                raise HTTPException(status_code=404, detail='Habilitación no encontrada en el proyecto')
            if authorization.events.filter(event_type__in=['retirada', 'sustituida']).exists():
                raise HTTPException(status_code=409, detail='La habilitación ya fue retirada o sustituida')
            ProjectCommercialAuthorizationEvent.objects.create(
                authorization=authorization, event_type='retirada', actor=actor,
                reason=payload.reason.strip(),
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail='La habilitación fue modificada concurrentemente')
    return {'authorization_id': authorization_id, 'withdrawn': True}


@router.get('/{project_id}/commercial-authorizations')
def list_project_commercial_authorizations(project_id: int, user: dict = Depends(get_current_user)):
    role = user.get('role')
    if role not in {'L2', 'L3'}:
        raise HTTPException(status_code=403, detail='No tienes permiso para consultar habilitaciones del proyecto')
    project_exists = Project.objects.filter(pk=project_id).exists()
    if not project_exists:
        raise HTTPException(status_code=404, detail='Proyecto no encontrado')
    include_private = role == 'L2'
    queryset = ProjectCommercialAuthorization.objects.filter(project_id=project_id)
    if role == 'L3':
        in_scope = ProjectCoordination.objects.filter(
            project_id=project_id, coordinator_id=user['collaborator_id'], is_active=True,
            coordinator__is_active=True, coordinator__role__level='L3',
        ).exists()
        if not in_scope:
            raise HTTPException(status_code=404, detail='Proyecto fuera de tu coordinación vigente')
        queryset = active_commercial_authorizations(project_id)
    queryset = queryset.select_related('authorized_by').order_by('-authorized_at', '-id')
    return [
        commercial_authorization_response(item, include_private=include_private)
        for item in queryset
    ]


def delivery_authorization_response(authorization: ProjectDeliveryAuthorization) -> dict:
    return {
        'id': authorization.id,
        'project_id': authorization.project_id,
        'authorized_by_id': authorization.authorized_by_id,
        'authorized_by_name': f'{authorization.authorized_by.first_name} {authorization.authorized_by.last_name}',
        'authorized_at': authorization.authorized_at.isoformat(),
        'authorized_scope': authorization.authorized_scope,
        'scope_snapshot': authorization.scope_snapshot,
        'effectivity_conditions': authorization.effectivity_conditions,
        'conditions_accredited': authorization.conditions_accredited,
        'evidence_reference': authorization.evidence_reference,
        'effective_at': authorization.effective_at.isoformat(),
        'expires_at': authorization.expires_at.isoformat() if authorization.expires_at else None,
        'events': [
            {
                'event_type': event.event_type,
                'actor_id': event.actor_id,
                'actor_name': f'{event.actor.first_name} {event.actor.last_name}',
                'reason': event.reason,
                'replacement_id': event.replacement_id,
                'occurred_at': event.occurred_at.isoformat(),
            }
            for event in authorization.events.select_related('actor').all()
        ],
    }


@router.get('/{project_id}/delivery-context')
def delivery_context(project_id: int, user: dict = Depends(get_current_user)):
    actor = active_l3_actor(user)
    project = Project.objects.filter(pk=project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail='Proyecto no encontrado')
    if not ProjectCoordination.objects.filter(
        project=project, coordinator=actor, is_active=True,
        coordinator__is_active=True, coordinator__role__level='L3',
    ).exists():
        raise HTTPException(status_code=404, detail='Proyecto fuera de tu coordinación vigente')
    snapshot, tasks = current_task_snapshot(project_id)
    classifications = {
        item.task_id: item
        for item in ProjectTaskClassification.objects.filter(project_id=project_id).select_related('actor')
    }
    task_rows = []
    for row in snapshot:
        classification = classifications.get(row['task_id'])
        task_rows.append({
            **row,
            'title': tasks[row['task_id']].title,
            'description': tasks[row['task_id']].description,
            'classification_history': [
                {
                    'is_mandatory': revision.is_mandatory,
                    'scope_snapshot': revision.scope_snapshot,
                    'reason': revision.reason,
                    'actor_id': revision.actor_id,
                    'actor_name': f'{revision.actor.first_name} {revision.actor.last_name}',
                    'occurred_at': revision.occurred_at.isoformat(),
                    'is_current': revision.is_current,
                }
                for revision in ProjectTaskClassification.objects.filter(
                    project_id=project_id, task_id=row['task_id'],
                ).select_related('actor')
            ],
        })
    validation_event = ProjectEvent.objects.filter(
        project=project, event_type='ingreso_validacion_tecnica',
    ).order_by('-occurred_at', '-id').first()
    evaluations = ProjectTechnicalEvaluation.objects.filter(
        project=project,
    ).select_related('actor', 'validation_event')
    try:
        scope_snapshot = project_scope_snapshot(project) if project.status != 'Planificado' else ''
    except HTTPException:
        scope_snapshot = ''
    return {
        'project_id': project.id,
        'status': project.status,
        'scope_snapshot': scope_snapshot,
        'tasks': task_rows,
        'current_validation_event_id': validation_event.id if validation_event else None,
        'technical_evaluations': [
            {
                'id': item.id,
                'validation_event_id': item.validation_event_id,
                'actor_id': item.actor_id,
                'actor_name': f'{item.actor.first_name} {item.actor.last_name}',
                'scope_snapshot': item.scope_snapshot,
                'satisfactory': item.satisfactory,
                'technical_enablement_status': item.technical_enablement_status,
                'ordinary_close_valid': item.ordinary_close_valid,
                'result_summary': item.result_summary,
                'evidence': item.evidence,
                'obligations_assessment': item.obligations_assessment,
                'optional_task_assessments': item.optional_task_assessments,
                'validated_versions': item.validated_versions,
                'evaluated_at': item.evaluated_at.isoformat(),
            }
            for item in evaluations
        ],
    }


@router.post('/{project_id}/tasks/{task_id}/delivery-classification')
def classify_project_task(
    project_id: int, task_id: int, payload: ProjectTaskClassificationInput,
    user: dict = Depends(get_current_user),
):
    actor = active_l3_actor(user)
    try:
        with transaction.atomic():
            project = lock_coordinated_project(project_id, actor)
            if project.status not in {'En ejecución', 'En validación técnica'}:
                raise HTTPException(status_code=409, detail='La clasificación solo puede realizarse antes del cierre del proyecto')
            scope_snapshot = project_scope_snapshot(project)
            task = Task.objects.select_for_update(of=('self',)).filter(
                pk=task_id, project=project,
            ).first()
            if task is None:
                raise HTTPException(status_code=404, detail='Tarea no encontrada en el proyecto')
            current = ProjectTaskClassification.objects.select_for_update(of=('self',)).filter(
                task=task, is_current=True,
            ).first()
            if (
                current
                and current.is_mandatory == payload.is_mandatory
                and normalized_scope(current.scope_snapshot) == normalized_scope(scope_snapshot)
                and current.reason == payload.reason.strip()
            ):
                return {'classification_id': current.id, 'created': False, 'is_mandatory': current.is_mandatory}
            if current:
                current.is_current = False
                current.save(update_fields=['is_current'])
            classification = ProjectTaskClassification.objects.create(
                project=project, task=task, actor=actor,
                is_mandatory=payload.is_mandatory, scope_snapshot=scope_snapshot,
                reason=payload.reason.strip(),
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail='La clasificación cambió concurrentemente')
    return {
        'classification_id': classification.id,
        'created': True,
        'is_mandatory': classification.is_mandatory,
        'scope_snapshot': classification.scope_snapshot,
        'reason': classification.reason,
        'occurred_at': classification.occurred_at.isoformat(),
    }


@router.post('/{project_id}/technical-evaluations')
def record_project_technical_evaluation(
    project_id: int, payload: ProjectTechnicalEvaluationInput,
    user: dict = Depends(get_current_user),
):
    actor = active_l3_actor(user)
    try:
        with transaction.atomic():
            project = lock_coordinated_project(project_id, actor)
            if project.status != 'En validación técnica':
                raise HTTPException(status_code=409, detail='El proyecto debe estar En validación técnica')
            validation_event = ProjectEvent.objects.filter(
                project=project, event_type='ingreso_validacion_tecnica',
            ).order_by('-occurred_at', '-id').first()
            if validation_event is None:
                raise HTTPException(status_code=409, detail='Falta el ingreso vigente a validación técnica')
            scope_snapshot = project_scope_snapshot(project)
            task_snapshot, _tasks = current_task_snapshot(project.id, lock=True)
            if payload.ordinary_close_valid:
                issues = task_close_issues(
                    task_snapshot, [item.model_dump() for item in payload.optional_task_assessments],
                )
                if issues:
                    raise HTTPException(status_code=409, detail='; '.join(issues))
            evaluation = ProjectTechnicalEvaluation.objects.create(
                project=project, validation_event=validation_event, actor=actor,
                scope_snapshot=scope_snapshot, satisfactory=payload.satisfactory,
                technical_enablement_status=payload.technical_enablement_status,
                ordinary_close_valid=payload.ordinary_close_valid,
                obligations_compatible=payload.obligations_compatible,
                result_summary=payload.result_summary.strip(), evidence=payload.evidence.strip(),
                ordinary_close_evidence=payload.ordinary_close_evidence.strip(),
                obligations_assessment=payload.obligations_assessment.strip(),
                optional_task_assessments=[item.model_dump() for item in payload.optional_task_assessments],
                validated_versions=payload.validated_versions,
                task_snapshot=task_snapshot,
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail='No se pudo guardar la evaluación técnica')
    return {
        'id': evaluation.id,
        'project_id': project_id,
        'validation_event_id': evaluation.validation_event_id,
        'satisfactory': evaluation.satisfactory,
        'technical_enablement_status': evaluation.technical_enablement_status,
        'ordinary_close_valid': evaluation.ordinary_close_valid,
        'validated_versions': evaluation.validated_versions,
        'evaluated_at': evaluation.evaluated_at.isoformat(),
    }


@router.get('/{project_id}/delivery-authorizations')
def list_delivery_authorizations(project_id: int, user: dict = Depends(get_current_user)):
    role = user.get('role')
    if role not in {'L2', 'L3'}:
        raise HTTPException(status_code=403, detail='No tienes permiso para consultar habilitaciones de entrega')
    project = Project.objects.filter(pk=project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail='Proyecto no encontrado')
    if role == 'L3' and not ProjectCoordination.objects.filter(
        project=project, coordinator_id=user['collaborator_id'], is_active=True,
        coordinator__is_active=True, coordinator__role__level='L3',
    ).exists():
        raise HTTPException(status_code=404, detail='Proyecto fuera de tu coordinación vigente')
    return [
        delivery_authorization_response(item)
        for item in ProjectDeliveryAuthorization.objects.filter(project=project)
        .select_related('authorized_by').prefetch_related('events__actor')
    ]


@router.post('/{project_id}/delivery-authorizations', status_code=status.HTTP_201_CREATED)
def create_delivery_authorization(
    project_id: int, payload: ProjectDeliveryAuthorizationCreate,
    user: dict = Depends(get_current_user),
):
    actor = active_l2_actor(user)
    if not payload.conditions_accredited:
        raise HTTPException(status_code=409, detail='L2 debe acreditar las condiciones de efectividad')
    if payload.expires_at is not None and payload.expires_at <= payload.effective_at:
        raise HTTPException(status_code=422, detail='El vencimiento debe ser posterior a la efectividad')
    if payload.replaces_authorization_id is not None and not payload.replacement_reason:
        raise HTTPException(status_code=422, detail='La sustitución requiere motivo')
    try:
        with transaction.atomic():
            project = Project.objects.select_for_update(of=('self',)).filter(pk=project_id).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
            ensure_project_not_cancelled(project_id)
            if payload.effective_at < timezone.now():
                raise HTTPException(status_code=422, detail='No se admiten habilitaciones de entrega retroactivas')
            scope_snapshot = project_scope_snapshot(project)
            if normalized_scope(payload.authorized_scope) != normalized_scope(scope_snapshot):
                raise HTTPException(status_code=409, detail='La habilitación debe corresponder al alcance vigente del proyecto')
            replaced = None
            if payload.replaces_authorization_id is not None:
                replaced = ProjectDeliveryAuthorization.objects.select_for_update(of=('self',)).filter(
                    pk=payload.replaces_authorization_id, project=project,
                ).first()
                if replaced is None:
                    raise HTTPException(status_code=404, detail='La habilitación a sustituir no pertenece al proyecto')
                if replaced.events.filter(event_type__in=['retirada', 'sustituida']).exists():
                    raise HTTPException(status_code=409, detail='La habilitación ya fue retirada o sustituida')
            authorization = ProjectDeliveryAuthorization.objects.create(
                project=project, authorized_by=actor,
                authorized_scope=payload.authorized_scope.strip(), scope_snapshot=scope_snapshot,
                effectivity_conditions=payload.effectivity_conditions.strip(),
                conditions_accredited=payload.conditions_accredited,
                evidence_reference=payload.evidence_reference.strip(),
                effective_at=payload.effective_at, expires_at=payload.expires_at,
            )
            if replaced is not None:
                ProjectDeliveryAuthorizationEvent.objects.create(
                    authorization=replaced, event_type='sustituida', actor=actor,
                    reason=payload.replacement_reason.strip(), replacement=authorization,
                )
    except IntegrityError:
        raise HTTPException(status_code=409, detail='La habilitación fue modificada concurrentemente')
    authorization = ProjectDeliveryAuthorization.objects.select_related('authorized_by').get(pk=authorization.pk)
    return delivery_authorization_response(authorization)


@router.post('/{project_id}/delivery-authorizations/{authorization_id}/withdrawal')
def withdraw_delivery_authorization(
    project_id: int, authorization_id: int, payload: ProjectCommercialAuthorizationWithdrawal,
    user: dict = Depends(get_current_user),
):
    actor = active_l2_actor(user)
    try:
        with transaction.atomic():
            project = Project.objects.select_for_update(of=('self',)).filter(pk=project_id).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
            ensure_project_not_cancelled(project_id)
            authorization = ProjectDeliveryAuthorization.objects.select_for_update(of=('self',)).filter(
                pk=authorization_id, project=project,
            ).first()
            if authorization is None:
                raise HTTPException(status_code=404, detail='Habilitación no encontrada en el proyecto')
            if authorization.events.filter(event_type__in=['retirada', 'sustituida']).exists():
                raise HTTPException(status_code=409, detail='La habilitación ya fue retirada o sustituida')
            ProjectDeliveryAuthorizationEvent.objects.create(
                authorization=authorization, event_type='retirada', actor=actor,
                reason=payload.reason.strip(),
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail='La habilitación fue modificada concurrentemente')
    return {'authorization_id': authorization_id, 'withdrawn': True}


@router.post('/{project_id}/ready-for-delivery', response_model=ProjectResponse)
def mark_project_ready_for_delivery(
    project_id: int, payload: ProjectReadyForDeliveryInput,
    user: dict = Depends(get_current_user),
):
    actor = active_l3_actor(user)
    try:
        with transaction.atomic():
            project = lock_coordinated_project(project_id, actor)
            if project.status != 'En validación técnica':
                raise HTTPException(status_code=409, detail='El proyecto debe estar En validación técnica')
            scope_snapshot = project_scope_snapshot(project)
            validation_event = ProjectEvent.objects.filter(
                project=project, event_type='ingreso_validacion_tecnica',
            ).order_by('-occurred_at', '-id').first()
            if validation_event is None:
                raise HTTPException(status_code=409, detail='Falta el ingreso vigente a validación técnica')
            evaluation = ProjectTechnicalEvaluation.objects.select_for_update(of=('self',)).filter(
                project=project, validation_event=validation_event,
            ).order_by('-evaluated_at', '-id').first()
            if evaluation is None:
                raise HTTPException(status_code=409, detail='Falta la evaluación técnica integral del ciclo vigente')
            if normalized_scope(evaluation.scope_snapshot) != normalized_scope(scope_snapshot):
                raise HTTPException(status_code=409, detail='La evaluación técnica no corresponde al alcance vigente')
            if not evaluation.satisfactory:
                raise HTTPException(status_code=409, detail='La evaluación técnica integral no es satisfactoria')
            if evaluation.technical_enablement_status != 'Vigente':
                raise HTTPException(status_code=409, detail='La habilitación técnica no está vigente')
            if not evaluation.ordinary_close_valid or not evaluation.obligations_compatible:
                raise HTTPException(status_code=409, detail='El cierre técnico ordinario u obligaciones no son compatibles')
            task_snapshot, _tasks = current_task_snapshot(project.id, lock=True)
            if task_snapshot != evaluation.task_snapshot:
                raise HTTPException(status_code=409, detail='Las tareas o clasificaciones cambiaron después de la evaluación; se requiere evaluar de nuevo')
            issues = task_close_issues(task_snapshot, evaluation.optional_task_assessments)
            if issues:
                raise HTTPException(status_code=409, detail='; '.join(issues))
            authorization = active_delivery_authorizations(project.id, timezone.now()).select_for_update(of=('self',)).filter(
                pk=payload.delivery_authorization_id,
            ).first()
            if authorization is None:
                raise HTTPException(status_code=409, detail='La habilitación comercial seleccionada no está vigente y aplicable')
            if normalized_scope(authorization.scope_snapshot) != normalized_scope(scope_snapshot) or normalized_scope(authorization.authorized_scope) != normalized_scope(scope_snapshot):
                raise HTTPException(status_code=409, detail='La habilitación comercial no corresponde al alcance vigente')
            previous_status = project.status
            project.status = 'Listo para entrega'
            project.save(update_fields=['status'])
            ProjectEvent.objects.create(
                event_type='listo_para_entrega', project=project, actor=actor,
                technical_evaluation=evaluation, delivery_authorization=authorization,
                previous_status=previous_status, new_status=project.status,
                reason=payload.reason.strip(),
                evidence=(
                    f'Alcance evaluado: {scope_snapshot}\n'
                    f'Evaluación técnica integral #{evaluation.id}: {evaluation.result_summary.strip()}\n'
                    f'Evidencia técnica: {evaluation.evidence.strip()}\n'
                    f'Cierre técnico ordinario acreditado: {evaluation.ordinary_close_evidence.strip()}\n'
                    f'Obligaciones: {evaluation.obligations_assessment.strip()}\n'
                    f'Habilitación comercial L2 #{authorization.id}: {authorization.evidence_reference}\n'
                    f'Condiciones de efectividad: {authorization.effectivity_conditions.strip()}\n'
                    f'Tareas y clasificaciones verificadas: {len(task_snapshot)}'
                ),
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail='No se pudo registrar la transición por un cambio concurrente')
    return to_response(Project.objects.select_related('client').get(pk=project_id))


@router.get('/{project_id}/deliveries')
def list_project_deliveries(project_id: int, user: dict = Depends(get_current_user)):
    role = user.get('role')
    if role == 'L2':
        active_l2_actor(user)
    elif role == 'L3':
        actor = active_l3_actor(user)
        if not ProjectCoordination.objects.filter(
            project_id=project_id, coordinator=actor, is_active=True,
            coordinator__is_active=True, coordinator__role__level='L3',
        ).exists():
            raise HTTPException(status_code=404, detail='Proyecto fuera de tu coordinación vigente')
    else:
        raise HTTPException(status_code=403, detail='Solo L2 o L3 puede consultar las entregas del proyecto')
    if not Project.objects.filter(pk=project_id).exists():
        raise HTTPException(status_code=404, detail='Proyecto no encontrado')
    return [
        project_delivery_response(item)
        for item in ProjectDelivery.objects.filter(project_id=project_id)
        .select_related('recorded_by', 'preparation_authorization')
        .prefetch_related('transition_links')
    ]


@router.post('/{project_id}/deliveries', status_code=status.HTTP_201_CREATED)
def record_project_delivery(
    project_id: int, payload: ProjectDeliveryCreate,
    user: dict = Depends(get_current_user),
):
    actor = active_l2_actor(user)
    if payload.occurred_at > timezone.now():
        raise HTTPException(status_code=422, detail='La fecha real de entrega no puede estar en el futuro')
    try:
        with transaction.atomic():
            project = Project.objects.select_for_update(of=('self',)).filter(pk=project_id).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
            ensure_project_not_cancelled(project_id)
            if project.status not in {'En ejecución', 'En validación técnica', 'Listo para entrega'}:
                raise HTTPException(status_code=409, detail='No se pueden registrar entregas en el estado actual')
            if payload.delivery_type == 'integral' and project.status != 'Listo para entrega':
                raise HTTPException(status_code=409, detail='La entrega integral ordinaria requiere Listo para entrega')
            authorization = ProjectDeliveryAuthorization.objects.select_for_update(of=('self',)).filter(
                pk=payload.preparation_authorization_id, project=project,
            ).first()
            if authorization is None:
                raise HTTPException(status_code=404, detail='La habilitación no corresponde al proyecto')
            if authorization.authorized_at > payload.occurred_at or not delivery_authorization_valid_at(
                authorization, payload.occurred_at,
            ):
                raise HTTPException(status_code=409, detail='La habilitación no era aplicable en la fecha efectiva de entrega')
            scope_snapshot = project_scope_snapshot(project)
            if normalized_scope(authorization.scope_snapshot) != normalized_scope(scope_snapshot) or normalized_scope(
                authorization.authorized_scope,
            ) != normalized_scope(scope_snapshot):
                raise HTTPException(status_code=409, detail='La habilitación no corresponde al alcance actual del proyecto')
            if payload.delivery_type == 'integral' and normalized_scope(payload.scope) != normalized_scope(scope_snapshot):
                raise HTTPException(status_code=409, detail='La entrega integral debe cubrir el alcance vigente del proyecto')
            delivery = ProjectDelivery.objects.create(
                project=project, recorded_by=actor, preparation_authorization=authorization,
                delivery_type=payload.delivery_type, scope=payload.scope.strip(),
                scope_within_authorization=payload.scope_within_authorization,
                covers_project_scope=payload.covers_project_scope,
                version_reference=payload.version_reference.strip(), recipient=payload.recipient.strip(),
                delivery_method=payload.delivery_method.strip(), performed_by=payload.performed_by.strip(),
                evidence_reference=payload.evidence_reference.strip(), occurred_at=payload.occurred_at,
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail='No se pudo conservar la constancia de entrega')
    delivery = ProjectDelivery.objects.select_related('recorded_by', 'preparation_authorization').get(pk=delivery.pk)
    return project_delivery_response(delivery)


@router.post('/{project_id}/delivery-version-reviews')
def review_project_delivery_version(
    project_id: int, payload: ProjectDeliveryTechnicalReviewInput,
    user: dict = Depends(get_current_user),
):
    actor = active_l3_actor(user)
    try:
        with transaction.atomic():
            project = lock_coordinated_project(project_id, actor)
            if project.status != 'Listo para entrega':
                raise HTTPException(status_code=409, detail='La revisión de versión requiere Listo para entrega')
            ready_event = ProjectEvent.objects.filter(
                project=project, event_type='listo_para_entrega', new_status='Listo para entrega',
            ).order_by('-occurred_at', '-id').first()
            evaluation = ready_event.technical_evaluation if ready_event else None
            scope_snapshot = project_scope_snapshot(project)
            if (
                evaluation is None
                or evaluation.project_id != project.id
                or normalized_scope(evaluation.scope_snapshot) != normalized_scope(scope_snapshot)
            ):
                raise HTTPException(status_code=409, detail='No existe una evaluación técnica aplicable al alcance vigente')
            task_snapshot, _tasks = current_task_snapshot(project.id, lock=True)
            if task_snapshot != evaluation.task_snapshot:
                raise HTTPException(status_code=409, detail='Las tareas cambiaron después de la evaluación técnica')
            review = ProjectDeliveryTechnicalReview.objects.create(
                project=project, version_reference=payload.version_reference.strip(),
                technical_evaluation=evaluation, actor=actor,
                satisfactory=payload.satisfactory,
                technical_enablement_status=payload.technical_enablement_status,
                result_summary=payload.result_summary.strip(), evidence=payload.evidence.strip(),
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail='No se pudo registrar la revisión técnica de versión')
    return {
        'project_id': project_id, 'version_reference': review.version_reference,
        'technical_evaluation_id': review.technical_evaluation_id,
        'actor_id': review.actor_id, 'satisfactory': review.satisfactory,
        'technical_enablement_status': review.technical_enablement_status,
        'reviewed_at': review.reviewed_at.isoformat(),
    }


@router.post('/{project_id}/deliveries/formalize', response_model=ProjectResponse)
def formalize_project_delivery(
    project_id: int, payload: ProjectDeliveryFormalizeInput,
    user: dict = Depends(get_current_user),
):
    actor = active_l2_actor(user)
    try:
        with transaction.atomic():
            project = Project.objects.select_for_update(of=('self',)).filter(pk=project_id).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
            ensure_project_not_cancelled(project_id)
            if project.status != 'Listo para entrega':
                raise HTTPException(status_code=409, detail='El proyecto debe estar Listo para entrega')
            scope_snapshot = project_scope_snapshot(project)
            ready_event = ProjectEvent.objects.filter(
                project=project, event_type='listo_para_entrega', new_status='Listo para entrega',
            ).order_by('-occurred_at', '-id').first()
            evaluation = ready_event.technical_evaluation if ready_event else None
            authorization_id = ready_event.delivery_authorization_id if ready_event else None
            if evaluation is None or authorization_id is None:
                raise HTTPException(status_code=409, detail='Falta el cierre técnico y la habilitación comercial de B4-10')
            if (
                not evaluation.satisfactory
                or evaluation.technical_enablement_status != 'Vigente'
                or not evaluation.ordinary_close_valid
                or not evaluation.obligations_compatible
                or normalized_scope(evaluation.scope_snapshot) != normalized_scope(scope_snapshot)
            ):
                raise HTTPException(status_code=409, detail='La evaluación técnica o habilitación vigente no es suficiente')
            task_snapshot, _tasks = current_task_snapshot(project.id, lock=True)
            if task_snapshot != evaluation.task_snapshot:
                raise HTTPException(status_code=409, detail='Las tareas o clasificaciones cambiaron después de la evaluación técnica')
            authorization = active_delivery_authorizations(project.id, timezone.now()).select_for_update(
                of=('self',),
            ).filter(pk=authorization_id).first()
            if authorization is None:
                raise HTTPException(status_code=409, detail='La habilitación para preparar entrega ya no está vigente')
            if normalized_scope(authorization.scope_snapshot) != normalized_scope(scope_snapshot):
                raise HTTPException(status_code=409, detail='La habilitación no corresponde al alcance vigente')
            deliveries = list(ProjectDelivery.objects.select_for_update(of=('self',)).filter(
                project=project, pk__in=payload.delivery_ids,
            ).select_related('preparation_authorization').order_by('occurred_at', 'id'))
            if len(deliveries) != len(payload.delivery_ids):
                raise HTTPException(status_code=404, detail='Una o más entregas no pertenecen al proyecto')
            if ProjectDeliveryTransition.objects.filter(delivery_id__in=payload.delivery_ids).exists():
                raise HTTPException(status_code=409, detail='Una entrega ya quedó vinculada a una transición')
            integral = [item for item in deliveries if item.delivery_type == 'integral']
            if integral:
                if len(deliveries) != 1 or not integral[0].covers_project_scope or normalized_scope(
                    integral[0].scope,
                ) != normalized_scope(scope_snapshot):
                    raise HTTPException(status_code=409, detail='Una entrega integral debe acreditar por sí sola el alcance completo')
            elif any(item.delivery_type != 'parcial' for item in deliveries):
                raise HTTPException(status_code=409, detail='La combinación de entregas no es válida')
            if not any(item.occurred_at >= ready_event.occurred_at for item in deliveries):
                raise HTTPException(status_code=409, detail='La cobertura integral ocurrió antes de Listo para entrega; no se admite regularización por esta ruta')
            for item in deliveries:
                if not delivery_authorization_valid_at(item.preparation_authorization, item.occurred_at):
                    raise HTTPException(status_code=409, detail=f'La habilitación no cubría la entrega #{item.id} en su fecha efectiva')
                if (
                    normalized_scope(item.preparation_authorization.scope_snapshot) != normalized_scope(scope_snapshot)
                    or normalized_scope(item.preparation_authorization.authorized_scope) != normalized_scope(scope_snapshot)
                    or not item.scope_within_authorization
                ):
                    raise HTTPException(status_code=409, detail=f'La entrega #{item.id} no acredita alcance comprendido en la habilitación vigente')
                same_version = any(
                    version.strip().casefold() == item.version_reference.strip().casefold()
                    for version in evaluation.validated_versions
                )
                if not same_version:
                    review = ProjectDeliveryTechnicalReview.objects.filter(
                        project=project, version_reference__iexact=item.version_reference,
                        technical_evaluation=evaluation, reviewed_at__lte=item.occurred_at,
                    ).order_by('-reviewed_at', '-id').first()
                    if (
                        review is None or not review.satisfactory
                        or review.technical_enablement_status != 'Vigente'
                    ):
                        raise HTTPException(status_code=409, detail=f'La versión de entrega #{item.id} requiere revisión técnica satisfactoria de L3')
            evidence_lines = [
                f'Cobertura integral comprobada por L2: {payload.coverage_evidence.strip()}',
                f'Actor L2: {actor.id}; alcance del proyecto: {scope_snapshot}',
                f'Evaluación técnica B4-10 #{evaluation.id}; habilitación para preparar #{authorization.id}',
            ]
            evidence_lines.extend(
                f'Entrega #{item.id}: {item.delivery_type}; alcance={item.scope}; versión={item.version_reference}; '
                f'destinatario={item.recipient}; mecanismo={item.delivery_method}; responsable={item.performed_by}; '
                f'fecha efectiva={item.occurred_at.isoformat()}; evidencia={item.evidence_reference}; '
                f'habilitación=#{item.preparation_authorization_id}; alcance dentro de habilitación acreditado por L2={item.scope_within_authorization}'
                for item in deliveries
            )
            previous_status = project.status
            project.status = 'Entregado'
            project.save(update_fields=['status'])
            event = ProjectEvent.objects.create(
                event_type='entrega_formalizada', project=project, actor=actor,
                technical_evaluation=evaluation, delivery_authorization=authorization,
                previous_status=previous_status, new_status=project.status,
                reason=payload.reason.strip(), evidence='\n'.join(evidence_lines),
            )
            ProjectDeliveryTransition.objects.bulk_create([
                ProjectDeliveryTransition(event=event, delivery=item) for item in deliveries
            ])
    except IntegrityError:
        raise HTTPException(status_code=409, detail='No se pudo formalizar la entrega por un cambio concurrente')
    return to_response(Project.objects.select_related('client').get(pk=project_id))


@router.post('/{project_id}/start', response_model=ProjectResponse)
def start_project(project_id: int, payload: ProjectStartReadiness, user: dict = Depends(get_current_user)):
    if user.get('role') != 'L3':
        raise HTTPException(status_code=403, detail='Solo L3 puede iniciar técnicamente el proyecto')
    actor = Collaborator.objects.filter(
        pk=user['collaborator_id'], is_active=True, role__level='L3',
    ).first()
    if actor is None:
        raise HTTPException(status_code=403, detail='El colaborador L3 no está activo')
    if not all((
        payload.responsible_parties_identified,
        payload.resources_ready,
        payload.dependencies_ready,
        payload.initial_scope_within_authorization,
        payload.restrictions_assessed,
    )):
        raise HTTPException(status_code=409, detail='La preparación técnica inicial está incompleta')

    now = timezone.now()
    try:
        with transaction.atomic():
            project = Project.objects.select_for_update(of=('self',)).select_related('client').filter(
                pk=project_id,
            ).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
            ensure_project_not_cancelled(project_id)
            coordination_ids = list(ProjectCoordination.objects.filter(
                project_id=project_id, coordinator=actor, is_active=True,
                coordinator__is_active=True, coordinator__role__level='L3',
            ).order_by('id').values_list('id', flat=True))
            if not coordination_ids:
                if not Project.objects.filter(pk=project_id).exists():
                    raise HTTPException(status_code=404, detail='Proyecto no encontrado')
                raise HTTPException(status_code=404, detail='Proyecto fuera de tu coordinación vigente')
            locked_coordinations = list(ProjectCoordination.objects.select_for_update(of=('self',)).filter(
                pk__in=coordination_ids, is_active=True,
                coordinator__is_active=True, coordinator__role__level='L3',
            ).order_by('id'))
            if not locked_coordinations:
                raise HTTPException(status_code=404, detail='Proyecto fuera de tu coordinación vigente')
            if project.status != 'Planificado':
                raise HTTPException(status_code=409, detail='El proyecto debe estar Planificado')
            authorization = active_commercial_authorizations(project_id, now).select_for_update(of=('self',)).filter(
                pk=payload.commercial_authorization_id,
            ).first()
            if authorization is None:
                raise HTTPException(status_code=409, detail='No existe una habilitación comercial aplicable para este proyecto')
            previous_status = project.status
            project.status = 'En ejecución'
            project.save(update_fields=['status'])
            ProjectEvent.objects.create(
                event_type='inicio_ejecucion', project=project, actor=actor,
                commercial_authorization=authorization,
                previous_status=previous_status, new_status=project.status,
                reason=payload.reason.strip(),
                evidence=(
                    f'Habilitación comercial L2 #{authorization.id}; '
                    f'alcance autorizado: {authorization.authorized_scope.strip()}\n'
                    f'Compromiso: {authorization.commitment_reference}\n'
                    f'Actividades iniciales: {payload.initial_activities.strip()}\n'
                    'Alcance inicial comprendido en la habilitación: sí\n'
                    f'Responsables identificados: sí\nRecursos indispensables listos: sí\n'
                    f'Dependencias iniciales listas: sí\nRestricciones relevantes evaluadas: sí\n'
                    f'Evidencia técnica: {payload.evidence.strip()}'
                ),
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail='No se pudo registrar el inicio por un cambio concurrente')

    return to_response(Project.objects.select_related('client').get(pk=project_id))


@router.get('/{project_id}/cancellations')
def list_project_cancellations(project_id: int, user: dict = Depends(get_current_user)):
    role = user.get('role')
    if role not in {'L2', 'L3'}:
        raise HTTPException(status_code=403, detail='No tienes permiso para consultar cancelaciones de proyectos')
    project = Project.objects.filter(pk=project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail='Proyecto no encontrado')
    if role == 'L3' and not ProjectCoordination.objects.filter(
        project_id=project_id, coordinator_id=user.get('collaborator_id'), is_active=True,
        coordinator__is_active=True, coordinator__role__level='L3',
    ).exists():
        raise HTTPException(status_code=404, detail='Proyecto fuera de tu coordinación vigente')
    return [cancellation_response(item) for item in ProjectCancellation.objects.filter(
        project_id=project_id,
    ).select_related('opened_by').prefetch_related('events__actor')]


@router.post('/{project_id}/cancellations', status_code=status.HTTP_201_CREATED)
def open_project_cancellation(
    project_id: int, payload: ProjectCancellationCreate, user: dict = Depends(get_current_user),
):
    actor = active_l2_actor(user)
    try:
        with transaction.atomic():
            project = Project.objects.select_for_update(of=('self',)).filter(pk=project_id).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
            if project.status == 'Entregado':
                raise HTTPException(status_code=409, detail='La cancelación integral de un proyecto Entregado requiere tratamiento funcional específico')
            ensure_project_not_cancelled(project_id)
            expected_scope = project_scope_snapshot(project)
            if normalized_scope(payload.cancelled_scope) != normalized_scope(expected_scope):
                raise HTTPException(status_code=409, detail='Esta operación solo admite la cancelación integral del alcance vigente del proyecto')
            open_cases = [item for item in ProjectCancellation.objects.filter(project=project).prefetch_related('events')
                          if cancellation_is_open(item)]
            if open_cases:
                raise HTTPException(status_code=409, detail='Ya existe una solicitud de cancelación pendiente o autorizada')
            cancellation = ProjectCancellation.objects.create(
                project=project, opened_by=actor, cancelled_scope=expected_scope,
                reason=payload.reason, evidence=payload.evidence,
            )
            ProjectCancellationEvent.objects.create(
                cancellation=cancellation, event_type='solicitada', actor=actor,
                reason=payload.reason, evidence=payload.evidence,
                data={'cancelled_scope': expected_scope, 'scope_type': 'project_full'},
            )
            project_cancellation_audit(project, actor, 'cancelacion_solicitada', payload.reason, {
                'cancellation_id': cancellation.id, 'scope_type': 'project_full',
                'cancelled_scope': expected_scope, 'evidence': payload.evidence,
            })
    except IntegrityError:
        raise HTTPException(status_code=409, detail='No se pudo registrar la solicitud de cancelación')
    return cancellation_response(ProjectCancellation.objects.select_related('opened_by').prefetch_related(
        'events__actor',
    ).get(pk=cancellation.pk))


@router.post('/{project_id}/cancellations/{cancellation_id}/technical-evaluation')
def evaluate_project_cancellation(
    project_id: int, cancellation_id: int, payload: ProjectCancellationTechnicalEvaluation,
    user: dict = Depends(get_current_user),
):
    actor = active_l3_actor(user)
    try:
        with transaction.atomic():
            project = lock_coordinated_project(project_id, actor)
            cancellation = ProjectCancellation.objects.select_for_update(of=('self',)).filter(
                pk=cancellation_id, project=project,
            ).first()
            if cancellation is None:
                raise HTTPException(status_code=404, detail='Solicitud de cancelación no encontrada')
            if cancellation_latest_event(cancellation).event_type != 'solicitada':
                raise HTTPException(status_code=409, detail='La solicitud ya recibió una evaluación o decisión')
            task_snapshot, _tasks = current_task_snapshot(project.id, lock=True)
            event = ProjectCancellationEvent.objects.create(
                cancellation=cancellation, event_type='evaluacion_tecnica', actor=actor,
                reason=payload.affected_tasks_assessment,
                evidence=payload.evidence,
                data={
                    'affected_tasks_assessment': payload.affected_tasks_assessment,
                    'obligations_assessment': payload.obligations_assessment,
                    'task_snapshot': task_snapshot,
                },
            )
            project_cancellation_audit(project, actor, 'cancelacion_evaluacion_tecnica', event.reason, {
                'cancellation_id': cancellation.id,
                'obligations_assessment': payload.obligations_assessment,
                'evidence': payload.evidence, 'task_snapshot': task_snapshot,
            })
    except IntegrityError:
        raise HTTPException(status_code=409, detail='No se pudo registrar la evaluación técnica')
    return cancellation_response(ProjectCancellation.objects.select_related('opened_by').prefetch_related(
        'events__actor',
    ).get(pk=cancellation_id))


@router.post('/{project_id}/cancellations/{cancellation_id}/decision')
def decide_project_cancellation(
    project_id: int, cancellation_id: int, payload: ProjectCancellationDecision,
    user: dict = Depends(get_current_user),
):
    actor = active_l2_actor(user)
    try:
        with transaction.atomic():
            project = Project.objects.select_for_update(of=('self',)).filter(pk=project_id).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
            cancellation = ProjectCancellation.objects.select_for_update(of=('self',)).filter(
                pk=cancellation_id, project=project,
            ).first()
            if cancellation is None:
                raise HTTPException(status_code=404, detail='Solicitud de cancelación no encontrada')
            latest = cancellation_latest_event(cancellation)
            if latest is None or latest.event_type != 'evaluacion_tecnica':
                raise HTTPException(status_code=409, detail='L3 debe evaluar primero las consecuencias técnicas')
            if not payload.authorized:
                event_type = 'denegada'
                data = {'commercial_consequences': 'No se autorizó la cancelación ordinaria'}
            else:
                ensure_project_not_cancelled(project_id)
                if ProjectCancellation.objects.filter(project=project).exclude(pk=cancellation_id).filter(
                    events__event_type='efectiva', events__effective_at__lte=timezone.now(),
                ).exists():
                    raise HTTPException(status_code=409, detail='El proyecto ya tiene una cancelación efectiva')
                if payload.planned_effective_at < timezone.now():
                    raise HTTPException(status_code=422, detail='La fecha prevista de efectividad no puede ser anterior a la autorización')
                event_type = 'autorizada'
                data = {
                    'commercial_consequences': payload.commercial_consequences,
                    'effectivity_conditions': payload.effectivity_conditions,
                    'planned_effective_at': payload.planned_effective_at.isoformat(),
                    'authority': 'L2 ordinary cancellation',
                }
            event = ProjectCancellationEvent.objects.create(
                cancellation=cancellation, event_type=event_type, actor=actor,
                reason=payload.reason, evidence=payload.evidence, data=data,
            )
            project_cancellation_audit(project, actor, f'cancelacion_{event_type}', payload.reason, {
                'cancellation_id': cancellation.id, **data, 'evidence': payload.evidence,
            })
    except IntegrityError:
        raise HTTPException(status_code=409, detail='No se pudo registrar la decisión comercial')
    return cancellation_response(ProjectCancellation.objects.select_related('opened_by').prefetch_related(
        'events__actor',
    ).get(pk=cancellation_id))


@router.post('/{project_id}/cancellations/{cancellation_id}/effectivity')
def record_project_cancellation_effectivity(
    project_id: int, cancellation_id: int, payload: ProjectCancellationEffectivity,
    user: dict = Depends(get_current_user),
):
    actor = active_l2_actor(user)
    try:
        with transaction.atomic():
            project = Project.objects.select_for_update(of=('self',)).filter(pk=project_id).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
            cancellation = ProjectCancellation.objects.select_for_update(of=('self',)).filter(
                pk=cancellation_id, project=project,
            ).first()
            if cancellation is None:
                raise HTTPException(status_code=404, detail='Solicitud de cancelación no encontrada')
            latest = cancellation_latest_event(cancellation)
            if latest is None or latest.event_type != 'autorizada':
                raise HTTPException(status_code=409, detail='Solo una cancelación autorizada puede hacerse efectiva')
            effective_at = timezone.now()
            planned = datetime.fromisoformat(latest.data['planned_effective_at'])
            if planned > effective_at:
                raise HTTPException(status_code=409, detail='La fecha prevista todavía no ha llegado')
            event = ProjectCancellationEvent.objects.create(
                cancellation=cancellation, event_type='efectiva', actor=actor,
                reason=payload.reason, evidence=payload.evidence,
                effective_at=effective_at,
                data={
                    'conditions_satisfied': payload.conditions_satisfied,
                    'authorization_event_id': latest.id,
                    'cancelled_scope': cancellation.cancelled_scope,
                },
            )
            project_cancellation_audit(project, actor, 'cancelacion_efectiva', payload.reason, {
                'cancellation_id': cancellation.id, 'effective_at': effective_at.isoformat(),
                'authorization_event_id': latest.id, 'conditions_satisfied': True,
                'evidence': payload.evidence,
            })
    except IntegrityError:
        raise HTTPException(status_code=409, detail='No se pudo registrar la efectividad de la cancelación')
    return cancellation_response(ProjectCancellation.objects.select_related('opened_by').prefetch_related(
        'events__actor',
    ).get(pk=cancellation_id))


@router.post('/', response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, user: dict = Depends(get_current_user)):
    require_project_creator(user)
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail='El nombre del proyecto es obligatorio')
    if payload.status not in (None, 'Planificado'):
        raise HTTPException(status_code=422, detail='Todo proyecto debe crearse en estado Planificado')
    with transaction.atomic():
        try:
            client = Client.objects.select_for_update().get(pk=payload.client_id)
        except Client.DoesNotExist:
            raise HTTPException(status_code=404, detail='Cliente no encontrado')
        if client.status == 'inactivo':
            raise HTTPException(status_code=400, detail='No se pueden crear proyectos para clientes inactivos')
        project = Project.objects.create(
            client=client,
            name=payload.name.strip(),
            objective=payload.objective,
            scope=payload.scope,
            status='Planificado',
        )
    return to_response(project)


@router.get('/', response_model=list[ProjectResponse])
def list_projects(client_id: int | None = None, user: dict = Depends(get_current_user)):
    require_project_reader(user)
    projects = Project.objects.select_related('client').all()
    if client_id is not None:
        projects = projects.filter(client_id=client_id)
    return [to_response(project) for project in projects]


@router.get('/{project_id}', response_model=ProjectResponse)
def get_project(project_id: int, user: dict = Depends(get_current_user)):
    require_project_reader(user)
    try:
        project = Project.objects.select_related('client').get(pk=project_id)
    except Project.DoesNotExist:
        raise HTTPException(status_code=404, detail='Proyecto no encontrado')
    return to_response(project)


@router.get('/{project_id}/contracted-services')
def list_project_contracted_services(project_id: int, user: dict = Depends(get_current_user)):
    require_project_reader(user)
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        raise HTTPException(status_code=404, detail='Proyecto no encontrado')
    if user.get('role') == 'L3' and not ProjectCoordination.objects.filter(
        project=project, coordinator_id=user.get('collaborator_id'), is_active=True,
        coordinator__is_active=True, coordinator__role__level='L3',
    ).exists():
        raise HTTPException(status_code=404, detail='Proyecto fuera de tu coordinación vigente')
    links = ProjectContractedService.objects.filter(project=project).select_related(
        'service__catalog_service', 'linked_by', 'unlinked_by',
    )
    return [{
        'id': link.id, 'service_id': link.service_id,
        'service_name': link.commitment_snapshot.get('service_name', link.service.service_name),
        'commitment_reference': link.commitment_snapshot.get('commitment_reference', link.service.commitment_reference),
        'scope': link.commitment_snapshot.get('scope', link.service.scope),
        'effective_start': link.commitment_snapshot.get('effective_start'),
        'contracted_duration': link.commitment_snapshot.get('contracted_duration', ''),
        'documented_expiration': link.commitment_snapshot.get('documented_expiration'),
        'frequency': link.commitment_snapshot.get('frequency', link.service.frequency),
        'commitment_snapshot': link.commitment_snapshot,
        'linked_by_id': link.linked_by_id, 'linked_at': link.linked_at,
        'link_reason': link.link_reason, 'unlinked_by_id': link.unlinked_by_id,
        'unlinked_at': link.unlinked_at, 'unlink_reason': link.unlink_reason,
        'is_active': link.unlinked_at is None,
    } for link in links]


@router.post('/{project_id}/contracted-services', status_code=status.HTTP_201_CREATED)
def link_contracted_service(
    project_id: int, payload: ProjectServiceLinkInput, user: dict = Depends(get_current_user),
):
    actor = active_l3_actor(user)
    with transaction.atomic():
        project = lock_coordinated_project(project_id, actor)
        if project.status == 'Entregado':
            raise HTTPException(status_code=409, detail='No se asocian servicios a un proyecto ya entregado')
        service = ContractedService.objects.select_for_update().select_related('client').filter(pk=payload.service_id).first()
        if service is None:
            raise HTTPException(status_code=404, detail='Servicio contratado no encontrado')
        if service.client_id != project.client_id:
            raise HTTPException(status_code=409, detail='El servicio y el proyecto deben pertenecer al mismo cliente')
        if ProjectContractedService.objects.filter(service=service, unlinked_at__isnull=True).exists():
            raise HTTPException(status_code=409, detail='El servicio ya está asociado a un proyecto; se requiere resolver la relación vigente antes de reasociar')
        link = ProjectContractedService.objects.create(
            project=project, service=service, linked_by=actor,
            link_reason=payload.reason,
            commitment_snapshot={
                'catalog_service_id': service.catalog_service_id,
                'catalog_service_name': service.catalog_service.name if service.catalog_service_id else None,
                'service_name': service.service_name,
                'commitment_reference': service.commitment_reference,
                'scope': service.scope,
                'frequency': service.frequency,
                'effective_start': service.effective_start.isoformat() if service.effective_start else None,
                'contracted_duration': service.contracted_duration,
                'documented_expiration': service.documented_expiration.isoformat() if service.documented_expiration else None,
                'evidence_reference': service.evidence_reference,
            },
        )
    return {'id': link.id, 'project_id': link.project_id, 'service_id': link.service_id, 'linked_at': link.linked_at}


@router.post('/{project_id}/contracted-services/{link_id}/withdrawal')
def unlink_contracted_service(
    project_id: int, link_id: int, payload: ProjectServiceLinkInput, user: dict = Depends(get_current_user),
):
    actor = active_l3_actor(user)
    with transaction.atomic():
        project = lock_coordinated_project(project_id, actor)
        link = ProjectContractedService.objects.select_for_update().filter(
            pk=link_id, project=project, unlinked_at__isnull=True,
        ).first()
        if link is None:
            raise HTTPException(status_code=404, detail='Vínculo activo no encontrado')
        if link.service_id != payload.service_id:
            raise HTTPException(status_code=409, detail='El servicio indicado no corresponde al vínculo')
        if project.status != 'Planificado' or Task.objects.filter(project=project).exists():
            raise HTTPException(status_code=409, detail='El vínculo afecta trabajo u obligaciones que requieren evaluación y autorización antes de desvincular')
        link.unlinked_by = actor
        link.unlinked_at = timezone.now()
        link.unlink_reason = payload.reason
        link.save(update_fields=['unlinked_by', 'unlinked_at', 'unlink_reason'])
    return {'id': link.id, 'unlinked_at': link.unlinked_at}
