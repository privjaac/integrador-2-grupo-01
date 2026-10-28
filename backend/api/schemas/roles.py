# ==============================================================================
# SCHEMAS/ROLES.PY — Schemas de roles
#
# Define la forma de los datos que entran y salen en los endpoints
# de roles (/api/roles/).
#
# Los roles son una tabla simple con pocos campos.
# Solo el Superadmin (L1) puede editar roles.
#
# Hay schemas para editar y consultar los cinco niveles fijos.
# ==============================================================================

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field
from api.schemas.safe_input import SafeInputModel
from datetime import datetime


# ------------------------------------------------------------------------------
# ROLEUPDATE — Datos para editar un rol existente
#
# El nivel jerárquico no puede modificarse.
# ------------------------------------------------------------------------------
class RoleUpdate(SafeInputModel):
    non_nullable_update_fields = frozenset({'name', 'description', 'permissions', 'is_active'})

    name: Optional[Annotated[str, Field(min_length=1, max_length=50)]] = None
    description: Optional[Annotated[str, Field(max_length=1000)]] = None
    permissions: Optional[list[str]] = None
    is_active: Optional[bool] = None


class RoleCreate(SafeInputModel):
    name: str = Field(min_length=2, max_length=50)
    level: Literal['L1', 'L2', 'L3', 'L4', 'L5']
    description: str = Field(default='', max_length=1000)
    permissions: list[str] = Field(default_factory=list)
    is_active: bool = True


# ------------------------------------------------------------------------------
# ROLERESPONSE — Datos que devuelve la API al consultar un rol
#
# Incluye también cuántos colaboradores tienen ese rol asignado.
# Útil para que React muestre esa info en la pantalla de roles del mockup.
# ------------------------------------------------------------------------------
class RoleResponse(BaseModel):
    id: int
    name: str
    level: str
    hierarchy: int
    can_create_users: bool
    min_role_create: Optional[int]
    description: str
    is_active: bool
    permissions: list[str]
    permissions_editable: bool = True
    collaborators_count: int = 0   # Cuántos colaboradores tienen este rol
    created_at: datetime

    class Config:
        from_attributes = True
