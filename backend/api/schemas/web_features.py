# ==============================================================================
# SCHEMAS/WEB_FEATURES.PY — Schemas de funcionalidades adicionales
#
# Define la forma de los datos que entran y salen en los endpoints
# de funcionalidades (/api/web-features/).
#
# Las funcionalidades son extras que se pueden agregar a cualquier cliente
# por un precio adicional — independiente del tipo de web.
#
# Ejemplos: Sistema de citas, Carrito de compras, Pasarela de pagos
#
# Hay 3 schemas:
#   - WebFeatureCreate   → datos para crear una funcionalidad nueva
#   - WebFeatureUpdate   → datos para editar una funcionalidad existente
#   - WebFeatureResponse → datos que devuelve la API al consultar
# ==============================================================================

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ------------------------------------------------------------------------------
# WEBFEATURECREATE — Datos para crear una funcionalidad nueva
#
# React manda estos campos al hacer POST /api/web-features/
# Solo Superadmin puede crear funcionalidades.
#
# Ejemplo de JSON que manda React:
# {
#   "name": "Sistema de citas",
#   "extra_price": 50.00
# }
# ------------------------------------------------------------------------------
class WebFeatureCreate(BaseModel):
    name: str               # Nombre de la funcionalidad
    extra_price: float      # Precio adicional en soles
    is_active: bool = True  # Por defecto activa al crear


# ------------------------------------------------------------------------------
# WEBFEATUREUPDATE — Datos para editar una funcionalidad existente
#
# Todos Optional porque puede que solo quieras cambiar el precio
# sin tocar el nombre, o desactivarla sin cambiar nada más.
# ------------------------------------------------------------------------------
class WebFeatureUpdate(BaseModel):
    name: Optional[str] = None
    extra_price: Optional[float] = None
    is_active: Optional[bool] = None


# ------------------------------------------------------------------------------
# WEBFEATURERESPONSE — Datos que devuelve la API al consultar
#
# Incluye todos los campos incluyendo id, is_active y created_at.
# ------------------------------------------------------------------------------
class WebFeatureResponse(BaseModel):
    id: int
    name: str
    extra_price: float
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True