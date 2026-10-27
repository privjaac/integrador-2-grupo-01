from django.db import IntegrityError, transaction
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone
from fastapi import Depends, HTTPException, status

from api.dependencies import get_current_user
from api.router import APIRouter
from api.schemas.tasks import Designation, TaskAssign, TaskCreate
from clients.models import (
    Collaborator, Project, ProjectCoordination, ProjectLeadership, Task,
    TaskEvent, TeamMembership,
)

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


def task_response(task: Task) -> dict:
    return {
        'id': task.id,
        'project_id': task.project_id,
        'project_name': task.project.name,
        'title': task.title,
        'description': task.description,
        'status': task.status,
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
                'event_type': event.event_type,
                'actor_id': event.actor_id,
                'actor_name': f'{event.actor.first_name} {event.actor.last_name}',
                'previous_status': event.previous_status or None,
                'new_status': event.new_status,
                'assignee_id': event.assignee_id,
                'assignee_name': (
                    f'{event.assignee.first_name} {event.assignee.last_name}' if event.assignee_id else None
                ),
                'occurred_at': event.occurred_at.isoformat(),
            }
            for event in task.events.select_related('actor', 'assignee').all()
        ],
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


@router.get('/context')
def get_task_context(user: dict = Depends(get_current_user)):
    role = user.get('role')
    if role not in {'L2', 'L3', 'L4', 'L5'}:
        raise HTTPException(403, 'No tienes acceso al contexto de tareas')
    collaborator_id = user['collaborator_id']
    result = {'role': role, 'projects': [], 'coordinators': [], 'leaders': [], 'developers': [], 'tasks': []}

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
        result['tasks'] = [task_response(t) for t in task_queryset(user).select_related('project', 'assignee').distinct()]
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
            })
        result['developers'] = list(unique_members.values())
        result['tasks'] = [task_response(t) for t in task_queryset(user).select_related('project', 'assignee').distinct()]
    elif role == 'L5':
        result['tasks'] = [task_response(t) for t in task_queryset(user).select_related('project', 'assignee').distinct()]
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
    return [task_response(t) for t in task_queryset(user).select_related('project', 'assignee').distinct()]


@router.get('/{task_id}')
def get_task(task_id: int, user: dict = Depends(get_current_user)):
    if user.get('role') not in {'L3', 'L4', 'L5'}:
        raise HTTPException(403, 'No tienes permiso para consultar tareas')
    task = task_queryset(user).select_related('project', 'assignee').filter(pk=task_id).first()
    if task is None:
        raise HTTPException(404, 'Tarea no encontrada')
    return task_response(task)


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
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task.pk))


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
    return task_response(Task.objects.select_related('project', 'assignee').get(pk=task_id))
