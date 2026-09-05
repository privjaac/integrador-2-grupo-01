# ==============================================================================
# SCHEMAS/ROLES.PY — Schemas de roles
#
# Define la forma de los datos que entran y salen en los endpoints
# de roles (/api/roles/).
#
# Los roles son una tabla simple con pocos campos.
# Solo el Superadmin (L1) puede crear o editar roles.
#
# Hay 3 schemas:
#   - RoleCreate   → datos para crear un rol nuevo
#   - RoleUpdate   → datos para editar un rol existente
#   - RoleResponse → datos que devuelve la API al consultar
# ==============================================================================

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ------------------------------------------------------------------------------
# ROLECREATE — Datos para crear un rol nuevo
#
# React manda estos campos al hacer POST /api/roles/
# Ambos son obligatorios — un rol sin nombre o sin nivel no tiene sentido.
# ------------------------------------------------------------------------------
class RoleCreate(BaseModel):
    name: str    # Nombre del rol, ej: 'Developer'
    level: str   # Nivel del rol, ej: 'L5' — debe ser L1, L2, L3, L4 o L5


# ------------------------------------------------------------------------------
# ROLEUPDATE — Datos para editar un rol existente
#
# Ambos Optional porque puede que solo quieras cambiar el nombre
# sin tocar el nivel, o viceversa.
# ------------------------------------------------------------------------------
class RoleUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[str] = None


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
    collaborators_count: int = 0   # Cuántos colaboradores tienen este rol
    created_at: datetime

    class Config:
        from_attributes = True