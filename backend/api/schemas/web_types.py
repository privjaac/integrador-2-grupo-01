# ==============================================================================
# SCHEMAS/WEB_TYPES.PY — Schemas del catálogo de tipos de web
#
# Define la forma de los datos que entran y salen en los endpoints
# del catálogo (/api/web-types/).
#
# Los tipos de web son los productos que ofrece Elomux con sus precios base.
# Solo el Superadmin (L1) puede crear, editar o eliminar tipos de web.
#
# Hay 3 schemas:
#   - WebCatalogCreate   → datos para crear un tipo de web nuevo
#   - WebCatalogUpdate   → datos para editar un tipo de web existente
#   - WebCatalogResponse → datos que devuelve la API al consultar
# ==============================================================================

from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, Field
from api.schemas.safe_input import SafeInputModel
from datetime import datetime


# ------------------------------------------------------------------------------
# WEBCATALOGCREATE — Datos para crear un tipo de web nuevo
#
# React manda estos campos al hacer POST /api/web-types/
#
# Ejemplo de JSON que manda React:
# {
#   "name": "Pollería",
#   "base_price_rent": 149.00,
#   "base_price_sale": 894.00
# }
# ------------------------------------------------------------------------------
class WebCatalogCreate(SafeInputModel):
    name: str = Field(min_length=1, max_length=100)
    base_price_rent: Annotated[Decimal, Field(max_digits=8, decimal_places=2)]
    base_price_sale: Annotated[Decimal, Field(max_digits=8, decimal_places=2)]
    is_active: bool = True       # Por defecto activo al crear


# ------------------------------------------------------------------------------
# WEBCATALOGUPDATE — Datos para editar un tipo de web existente
#
# Todos Optional porque puede que solo quieras actualizar los precios
# sin cambiar el nombre, o desactivarlo sin tocar nada más.
# ------------------------------------------------------------------------------
class WebCatalogUpdate(SafeInputModel):
    non_nullable_update_fields = frozenset({
        'name', 'base_price_rent', 'base_price_sale', 'is_active',
    })

    name: Optional[Annotated[str, Field(min_length=1, max_length=100)]] = None
    base_price_rent: Optional[Annotated[Decimal, Field(max_digits=8, decimal_places=2)]] = None
    base_price_sale: Optional[Annotated[Decimal, Field(max_digits=8, decimal_places=2)]] = None
    is_active: Optional[bool] = None


# ------------------------------------------------------------------------------
# WEBCATALOGRESPONSE — Datos que devuelve la API al consultar un tipo de web
#
# Incluye cuántos clientes tienen ese tipo de web contratado.
# Útil para que React sepa si un tipo de web está en uso antes de eliminarlo.
# ------------------------------------------------------------------------------
class WebCatalogResponse(BaseModel):
    id: int
    name: str
    base_price_rent: float
    base_price_sale: float
    is_active: bool
    clients_count: int = 0   # Cuántos clientes tienen este tipo de web
    created_at: datetime

    class Config:
        from_attributes = True
