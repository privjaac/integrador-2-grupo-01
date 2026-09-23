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

from pydantic import BaseModel
from api.schemas.safe_input import SafeInputModel
from typing import Optional
from datetime import datetime


# ------------------------------------------------------------------------------
# ROLEUPDATE — Datos para editar un rol existente
#
# El nivel jerárquico no puede modificarse.
# ------------------------------------------------------------------------------
class RoleUpdate(SafeInputModel):
    name: Optional[str] = None
    description: Optional[str] = None


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
    collaborators_count: int = 0   # Cuántos colaboradores tienen este rol
    created_at: datetime

    class Config:
        from_attributes = True
