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

from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, Field
from api.schemas.safe_input import SafeInputModel
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
class WebFeatureCreate(SafeInputModel):
    name: str = Field(min_length=1, max_length=100)
    extra_price: Annotated[Decimal, Field(max_digits=8, decimal_places=2)]
    is_active: bool = True  # Por defecto activa al crear
    web_type_ids: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list)


# ------------------------------------------------------------------------------
# WEBFEATUREUPDATE — Datos para editar una funcionalidad existente
#
# Todos Optional porque puede que solo quieras cambiar el precio
# sin tocar el nombre, o desactivarla sin cambiar nada más.
# ------------------------------------------------------------------------------
class WebFeatureUpdate(SafeInputModel):
    non_nullable_update_fields = frozenset({
        'name', 'extra_price', 'is_active', 'web_type_ids',
    })

    name: Optional[Annotated[str, Field(min_length=1, max_length=100)]] = None
    extra_price: Optional[Annotated[Decimal, Field(max_digits=8, decimal_places=2)]] = None
    is_active: Optional[bool] = None
    web_type_ids: Optional[list[Annotated[int, Field(gt=0)]]] = None


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
    web_type_ids: list[int]
    created_at: datetime

    class Config:
        from_attributes = True
