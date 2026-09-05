# ==============================================================================
# SCHEMAS/CUPE_LOG.PY — Schemas del historial de cambios de CUPE
#
# Define la forma de los datos que entran y salen en los endpoints
# del historial de CUPE (/api/cupe-log/).
#
# Solo el Superadmin (L1) puede autorizar cambios de CUPE.
# Cuando se aprueba, el sistema actualiza el CUPE en la tabla original
# y registra el cambio aquí en una sola transacción.
#
# Hay 3 schemas:
#   - CupeLogCreate   → datos para solicitar un cambio de CUPE
#   - CupeLogResponse → datos que devuelve la API al consultar
#   - CupeLogList     → versión resumida para listar el historial
# ==============================================================================

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ------------------------------------------------------------------------------
# CUPELOGCREATE — Datos para solicitar un cambio de CUPE
#
# React manda estos campos al hacer POST /api/cupe-log/
#
# Ejemplo de JSON que manda React:
# {
#   "entity_type": "client",
#   "entity_id": 5,
#   "new_cupe": "CLI-01023756",
#   "reason": "error_generacion",
#   "observations": "Se generó con ID incorrecto"
# }
#
# El campo old_cupe no se manda — FastAPI lo obtiene automáticamente
# buscando el CUPE actual del cliente o colaborador en la BD.
# ------------------------------------------------------------------------------
class CupeLogCreate(BaseModel):
    # 'client' o 'collaborator' — a quién se le cambia el CUPE
    entity_type: str

    # ID del cliente o colaborador al que se le cambia el CUPE
    entity_id: int

    # El nuevo CUPE que se quiere asignar
    new_cupe: str

    # Motivo del cambio
    reason: str  # 'error_generacion', 'reingreso', 'correccion_admin', 'otro'

    # Observaciones adicionales — obligatorio si reason='otro'
    observations: Optional[str] = None


# ------------------------------------------------------------------------------
# CUPELOGRESPONSE — Datos completos que devuelve la API al consultar
#
# Incluye los nombres del colaborador que solicitó y del Superadmin
# que autorizó el cambio, expandidos para que React los muestre.
# ------------------------------------------------------------------------------
class CupeLogResponse(BaseModel):
    id: int
    entity_type: str                    # 'client' o 'collaborator'
    entity_id: int                      # ID del cliente o colaborador
    old_cupe: str                       # CUPE anterior
    new_cupe: str                       # CUPE nuevo
    reason: str                         # Motivo del cambio
    observations: Optional[str]

    # Quién solicitó el cambio
    changed_by_id: Optional[int]
    changed_by_name: Optional[str]      # Nombre expandido del solicitante

    # Quién autorizó el cambio — siempre Superadmin
    authorized_by_id: Optional[int]
    authorized_by_name: Optional[str]   # Nombre expandido del autorizador

    changed_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------------------------
# CUPELOGLIST — Versión resumida para listar el historial
#
# Se usa cuando React pide el historial completo de cambios de CUPE.
# Muestra los datos más importantes sin expandir todos los nombres.
# ------------------------------------------------------------------------------
class CupeLogList(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    old_cupe: str
    new_cupe: str
    reason: str
    changed_by_name: Optional[str]
    authorized_by_name: Optional[str]
    changed_at: datetime

    class Config:
        from_attributes = True