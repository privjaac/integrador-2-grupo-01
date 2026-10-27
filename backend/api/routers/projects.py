from fastapi import Depends, HTTPException, status

from api.dependencies import get_current_user
from api.router import APIRouter
from api.schemas.projects import ProjectCreate, ProjectResponse
from clients.models import Client, Project

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
    }


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
