# ==============================================================================
# SCHEMAS/CLIENT_FEATURES.PY — Schemas de funcionalidades de clientes
#
# Define la forma de los datos que entran y salen en los endpoints
# de funcionalidades de clientes (/api/client-features/).
#
# Esta tabla es la relación entre clientes y sus funcionalidades extra.
# Un cliente puede tener varias funcionalidades contratadas.
#
# Hay 3 schemas:
#   - ClientFeatureCreate   → datos para asignar una funcionalidad a un cliente
#   - ClientFeatureResponse → datos que devuelve la API al consultar
#   - ClientFeatureList     → versión resumida para listar
# ==============================================================================

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ------------------------------------------------------------------------------
# CLIENTFEATURECREATE — Datos para asignar una funcionalidad a un cliente
#
# React manda estos campos al hacer POST /api/client-features/
#
# Ejemplo de JSON que manda React:
# {
#   "client_id": 1,
#   "feature_id": 3
# }
#
# Al asignar una funcionalidad, FastAPI debe:
#   1. Crear el registro en client_features
#   2. Sumar el extra_price de la funcionalidad al extra_price del cliente
#   3. Recalcular el total_price del cliente
# ------------------------------------------------------------------------------
class ClientFeatureCreate(BaseModel):
    client_id: int    # ID del cliente al que se le asigna la funcionalidad
    feature_id: int   # ID de la funcionalidad que se le asigna


# ------------------------------------------------------------------------------
# CLIENTFEATURERESPONSE — Datos que devuelve la API al consultar
#
# Incluye los nombres expandidos del cliente y la funcionalidad
# para que React los muestre directamente sin consultas adicionales.
# ------------------------------------------------------------------------------
class ClientFeatureResponse(BaseModel):
    id: int
    client_id: int
    client_name: Optional[str]      # Nombre del cliente, ej: 'Pollería El Sabor'
    client_cupe: Optional[str]      # CUPE del cliente, ej: 'CLI-01007918'
    feature_id: int
    feature_name: Optional[str]     # Nombre de la funcionalidad, ej: 'Sistema de citas'
    feature_price: Optional[float]  # Precio extra de la funcionalidad
    added_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------------------------
# CLIENTFEATURELIST — Versión resumida para listar funcionalidades de un cliente
#
# Se usa cuando React pide las funcionalidades de un cliente específico.
# Menos campos = respuesta más liviana.
# ------------------------------------------------------------------------------
class ClientFeatureList(BaseModel):
    id: int
    feature_id: int
    feature_name: Optional[str]
    feature_price: Optional[float]
    added_at: datetime

    class Config:
        from_attributes = True