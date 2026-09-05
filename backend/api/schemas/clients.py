# ==============================================================================
# SCHEMAS/CLIENTS.PY — Schemas de clientes
#
# Define la forma de los datos que entran y salen en los endpoints
# de clientes (/api/clients/).
#
# Hay 4 schemas:
#   - ClientCreate    → datos para crear un cliente nuevo
#   - ClientUpdate    → datos para editar un cliente existente
#   - ClientResponse  → datos completos que devuelve la API
#   - ClientList      → versión resumida para listar clientes
# ==============================================================================

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, date


# ------------------------------------------------------------------------------
# CLIENTCREATE — Datos para crear un cliente nuevo
#
# React manda estos campos al hacer POST /api/clients/
#
# Campos que NO se mandan porque los genera el sistema:
#   - cupe          → se genera automáticamente con la fórmula
#   - extra_price   → se calcula sumando las funcionalidades
#   - total_price   → se calcula: base_price + extra_price
#   - next_payment_date → se calcula según el plan y delivery_date
#   - created_at, updated_at → los genera Django automáticamente
#   - created_by    → lo asigna FastAPI con el token del colaborador
# ------------------------------------------------------------------------------
class ClientCreate(BaseModel):
    name: str                               # Nombre o razón social
    document_type: str                      # 'DNI' o 'RUC'
    document_number: str                    # Número de documento
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    web_type_id: int                        # ID del tipo de web — obligatorio
    plan: str                               # 'alquiler' o 'venta'
    status: str = 'desarrollo'              # Por defecto en desarrollo
    base_price: Optional[float] = None      # Precio base del tipo de web
    initial_payment: Optional[float] = None # Monto que pagó al registrarse
    registration_date: Optional[date] = None  # Día que pagó el inicial
    delivery_date: Optional[date] = None    # Día que se entregó la web
    payment_frequency: Optional[str] = None # 'mensual' o 'anual'
    domain_price: Optional[float] = None    # NULL=sin dominio, 0=gratis, monto=precio
    notes: Optional[str] = None


# ------------------------------------------------------------------------------
# CLIENTUPDATE — Datos para editar un cliente existente
#
# Todos Optional porque puede que solo quieras cambiar el estado
# o llenar la delivery_date cuando la web esté lista.
# ------------------------------------------------------------------------------
class ClientUpdate(BaseModel):
    name: Optional[str] = None
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    web_type_id: Optional[int] = None
    plan: Optional[str] = None
    status: Optional[str] = None
    base_price: Optional[float] = None
    initial_payment: Optional[float] = None
    extra_price: Optional[float] = None
    total_price: Optional[float] = None
    registration_date: Optional[date] = None
    delivery_date: Optional[date] = None    # El trabajador llena esto manualmente
    next_payment_date: Optional[date] = None
    payment_frequency: Optional[str] = None
    domain_price: Optional[float] = None
    notes: Optional[str] = None


# ------------------------------------------------------------------------------
# CLIENTRESPONSE — Datos completos que devuelve la API al consultar un cliente
#
# Incluye todos los campos del modelo más el nombre del tipo de web
# expandido para que React no tenga que hacer una segunda consulta.
# ------------------------------------------------------------------------------
class ClientResponse(BaseModel):
    id: int
    cupe: Optional[str]
    name: str
    document_type: str
    document_number: str
    phone: Optional[str]
    email: Optional[str]
    web_type_id: int
    web_type_name: Optional[str]        # Nombre expandido, ej: 'Pollería'
    plan: str
    status: str
    base_price: Optional[float]
    initial_payment: Optional[float]
    extra_price: Optional[float]
    total_price: Optional[float]
    registration_date: Optional[date]
    delivery_date: Optional[date]
    next_payment_date: Optional[date]
    payment_frequency: Optional[str]
    domain_price: Optional[float]
    notes: Optional[str]
    created_by_id: Optional[int]        # ID del colaborador que registró al cliente
    created_by_name: Optional[str]      # Nombre del colaborador que registró
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------------------------
# CLIENTLIST — Versión resumida para listar clientes
#
# Solo los campos necesarios para mostrar la tabla de clientes en React.
# Menos campos = respuesta más liviana cuando hay muchos clientes.
# ------------------------------------------------------------------------------
class ClientList(BaseModel):
    id: int
    cupe: Optional[str]
    name: str
    document_type: str
    document_number: str
    web_type_name: Optional[str]
    plan: str
    status: str
    next_payment_date: Optional[date]
    total_price: Optional[float]

    class Config:
        from_attributes = True