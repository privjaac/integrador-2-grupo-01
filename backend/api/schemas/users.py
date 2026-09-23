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

from pydantic import BaseModel, EmailStr, Field, model_validator
from api.schemas.safe_input import SafeInputModel
from typing import Optional
from datetime import datetime


# ------------------------------------------------------------------------------
# COLLABORATORCREATE — Datos para crear un colaborador nuevo
#
# React manda todos estos campos al hacer POST /api/users/
# Todos son obligatorios excepto los que tienen Optional o valor por defecto.
# ------------------------------------------------------------------------------
class CollaboratorCreate(SafeInputModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    document_type: str        # 'DNI', 'Pasaporte' o 'CE'
    document_number: str
    email: EmailStr           # EmailStr valida que tenga formato de email válido
    phone: Optional[str] = None   # Optional → puede no mandarse, queda como None
    city: str
    username: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=8)  # Se almacena únicamente como hash bcrypt
    role_id: int              # ID del rol asignado (referencia a la tabla roles)
    area: Optional[str] = None


# ------------------------------------------------------------------------------
# COLLABORATORUPDATE — Datos para editar un colaborador existente
#
# React manda solo los campos que quiere cambiar al hacer PUT /api/users/5
# Todos son Optional porque puede que solo quieras cambiar el teléfono,
# por ejemplo, sin tocar los demás campos.
# ------------------------------------------------------------------------------
class CollaboratorUpdate(SafeInputModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8)
    role_id: Optional[int] = None
    area: Optional[str] = None
    is_active: Optional[bool] = None

    @model_validator(mode='after')
    def reject_null_password(self):
        if 'password' in self.model_fields_set and self.password is None:
            raise ValueError('La contraseña nueva no puede ser null')
        return self


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
    role: Optional[str] = None
    area: Optional[str]
    work_area: Optional[str] = None
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
