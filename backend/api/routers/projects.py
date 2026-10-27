from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from fastapi import Depends, HTTPException, status

from api.dependencies import get_current_user
from api.router import APIRouter
from api.schemas.projects import (
    ProjectCommercialAuthorizationCreate, ProjectCommercialAuthorizationWithdrawal,
    ProjectCreate, ProjectResponse, ProjectStartReadiness, ProjectValidationReadiness,
)
from clients.models import (
    Client, Collaborator, Project, ProjectCommercialAuthorization,
    ProjectCommercialAuthorizationEvent, ProjectCoordination, ProjectEvent,
)

router = APIRouter()


def require_project_reader(user: dict) -> None:
    if user.get('role') not in {'L2', 'L3'}:
        raise HTTPException(status_code=403, detail='No tienes permiso para consultar proyectos')


def require_project_creator(user: dict) -> None:
    if user.get('role') != 'L2':
        raise HTTPException(status_code=403, detail='No tienes permiso para crear proyectos')


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
            project = Project.objects.select_for_update(of=('self',)).select_related('client').filter(
                pk=project_id,
            ).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
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


def active_commercial_authorizations(project_id: int, now=None):
    now = now or timezone.now()
    return ProjectCommercialAuthorization.objects.filter(
        project_id=project_id, effective_at__lte=now,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now),
    ).exclude(
        events__event_type__in=['retirada', 'sustituida'],
    ).distinct()


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
            project = Project.objects.select_for_update(of=('self',)).select_related('client').filter(
                pk=project_id,
            ).first()
            if project is None:
                raise HTTPException(status_code=404, detail='Proyecto no encontrado')
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


@router.post('/', response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, user: dict = Depends(get_current_user)):
    require_project_creator(user)
    if not payload.name.strip():
        raise HTTPException(status_code=422, detail='El nombre del proyecto es obligatorio')
    if payload.status not in (None, 'Planificado'):
        raise HTTPException(status_code=422, detail='Todo proyecto debe crearse en estado Planificado')
    try:
        client = Client.objects.get(pk=payload.client_id)
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
