# ==============================================================================
# SCHEMAS/USERS.PY — Schemas de colaboradores
#
# Define la forma de los datos que entran y salen en los endpoints
# de colaboradores (/api/users/).
#
# Hay 4 schemas:
#   - CollaboratorCreate  → datos para crear un colaborador nuevo
#   - CollaboratorUpdate  → datos para editar un colaborador existente
#   - CollaboratorResponse → datos que devuelve la API al consultar
#   - CollaboratorList    → versión resumida para listar varios colaboradores
#
# ¿Por qué varios schemas para lo mismo?
# Porque no siempre necesitas todos los campos.
# Al crear necesitas la contraseña. Al responder nunca la mandas.
# Al editar no todos los campos son obligatorios.
# ==============================================================================

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# ------------------------------------------------------------------------------
# COLLABORATORCREATE — Datos para crear un colaborador nuevo
#
# React manda todos estos campos al hacer POST /api/users/
# Todos son obligatorios excepto los que tienen Optional o valor por defecto.
# ------------------------------------------------------------------------------
class CollaboratorCreate(BaseModel):
    first_name: str
    last_name: str
    document_type: str        # 'DNI', 'Pasaporte' o 'CE'
    document_number: str
    email: EmailStr           # EmailStr valida que tenga formato de email válido
    phone: Optional[str] = None   # Optional → puede no mandarse, queda como None
    city: str
    username: str
    password: str             # Contraseña en texto plano — FastAPI la encripta antes de guardar
    role_id: int              # ID del rol asignado (referencia a la tabla roles)
    area: Optional[str] = None


# ------------------------------------------------------------------------------
# COLLABORATORUPDATE — Datos para editar un colaborador existente
#
# React manda solo los campos que quiere cambiar al hacer PUT /api/users/5
# Todos son Optional porque puede que solo quieras cambiar el teléfono,
# por ejemplo, sin tocar los demás campos.
# ------------------------------------------------------------------------------
class CollaboratorUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None   # Si no se manda, no se cambia la contraseña
    role_id: Optional[int] = None
    area: Optional[str] = None
    is_active: Optional[bool] = None


# ------------------------------------------------------------------------------
# COLLABORATORRESPONSE — Datos que devuelve la API al consultar un colaborador
#
# Nunca incluye password_hash — jamás se manda la contraseña al frontend.
# Incluye los datos del rol expandidos (nombre y nivel), no solo el ID.
#
# FastAPI usa este schema para armar el JSON de respuesta.
# ------------------------------------------------------------------------------
class CollaboratorResponse(BaseModel):
    id: int
    cupe: Optional[str]
    first_name: str
    last_name: str
    document_type: str
    document_number: str
    email: str
    phone: Optional[str]
    city: str
    username: str
    role_id: Optional[int]
    role_name: Optional[str]    # Nombre del rol, ej: 'Developer'
    role_level: Optional[str]   # Nivel del rol, ej: 'L5'
    area: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        # Permite que FastAPI convierta objetos Django directamente a este schema
        # Sin esto, FastAPI no sabría cómo leer un objeto Collaborator de Django
        from_attributes = True


# ------------------------------------------------------------------------------
# COLLABORATORLIST — Versión resumida para listar colaboradores
#
# Cuando React pide GET /api/users/ (lista completa), no necesita todos
# los campos de cada colaborador — solo los principales para mostrar la tabla.
# Menos datos = respuesta más rápida.
# ------------------------------------------------------------------------------
class CollaboratorList(BaseModel):
    id: int
    cupe: Optional[str]
    first_name: str
    last_name: str
    role_name: Optional[str]
    city: str
    is_active: bool

    class Config:
        from_attributes = True