from django.db import IntegrityError, transaction
from fastapi import Depends, HTTPException, status

from api.dependencies import get_current_user
from api.router import APIRouter
from api.schemas.projects import ProjectCreate, ProjectResponse, ProjectValidationReadiness
from clients.models import Client, Collaborator, Project, ProjectCoordination, ProjectEvent

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
