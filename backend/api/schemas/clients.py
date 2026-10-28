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

from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from api.schemas.safe_input import SafeInputModel
from datetime import datetime, date


Money8 = Annotated[Decimal, Field(max_digits=8, decimal_places=2)]
Money10 = Annotated[Decimal, Field(max_digits=10, decimal_places=2)]
ClientDocumentType = Literal['DNI', 'RUC']
ClientPlan = Literal['alquiler', 'venta']
ClientStatus = Literal['activo', 'desarrollo', 'inactivo']


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
class ClientCreate(SafeInputModel):
    name: str = Field(min_length=1, max_length=200)
    document_type: ClientDocumentType
    document_number: str = Field(min_length=1, max_length=20)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[EmailStr] = Field(default=None, max_length=254)
    web_type_id: int = Field(gt=0)
    plan: ClientPlan
    status: ClientStatus = 'desarrollo'
    initial_payment: Optional[Money10] = None
    registration_date: Optional[date] = None  # Día que pagó el inicial
    delivery_date: Optional[date] = None    # Día que se entregó la web
    domain_price: Optional[Money8] = None
    notes: Optional[str] = None
    feature_ids: list[Annotated[int, Field(gt=0)]] = Field(default_factory=list)


# ------------------------------------------------------------------------------
# CLIENTUPDATE — Datos para editar un cliente existente
#
# Todos Optional porque puede que solo quieras cambiar el estado
# o llenar la delivery_date cuando la web esté lista.
# ------------------------------------------------------------------------------
class ClientUpdate(SafeInputModel):
    non_nullable_update_fields = frozenset({
        'name', 'document_type', 'document_number', 'web_type_id', 'plan', 'status',
    })

    name: Optional[Annotated[str, Field(min_length=1, max_length=200)]] = None
    document_type: Optional[ClientDocumentType] = None
    document_number: Optional[Annotated[str, Field(min_length=1, max_length=20)]] = None
    phone: Optional[Annotated[str, Field(max_length=20)]] = None
    email: Optional[Annotated[EmailStr, Field(max_length=254)]] = None
    web_type_id: Optional[Annotated[int, Field(gt=0)]] = None
    plan: Optional[ClientPlan] = None
    status: Optional[ClientStatus] = None
    initial_payment: Optional[Money10] = None
    registration_date: Optional[date] = None
    delivery_date: Optional[date] = None    # El trabajador llena esto manualmente
    domain_price: Optional[Money8] = None
    notes: Optional[str] = None
    feature_ids: Optional[list[Annotated[int, Field(gt=0)]]] = None


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
    domain_price_type: str = 'ninguno'
    domain_custom_price: Optional[float] = None
    features: list[dict] = Field(default_factory=list)
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


class ContractedServiceWrite(SafeInputModel):
    service_name: str = Field(min_length=1, max_length=160)
    catalog_service_id: Optional[Annotated[int, Field(gt=0)]] = None
    commitment_reference: str = Field(min_length=1, max_length=200)
    scope: str = Field(min_length=1)
    agreed_amount: Optional[Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]] = None
    currency: str = Field(default='', max_length=3)
    frequency: Literal['unica', 'mensual', 'anual']
    effective_start: Optional[date] = None
    contracted_duration: str = Field(default='', max_length=120)
    documented_expiration: Optional[date] = None
    terms: str = ''
    evidence_reference: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1)
    impact_assessment: str = ''

    @field_validator('service_name', 'commitment_reference', 'scope', 'evidence_reference')
    @classmethod
    def reject_blank_contract_terms(cls, value):
        if not value.strip():
            raise ValueError('La referencia, alcance y evidencia son obligatorios')
        return value.strip()

    @model_validator(mode='after')
    def validate_service_dates(self):
        if self.effective_start and self.documented_expiration and self.documented_expiration < self.effective_start:
            raise ValueError('El vencimiento documentado no puede preceder al inicio contratado')
        if not self.reason.strip():
            raise ValueError('El motivo comercial es obligatorio')
        if self.agreed_amount is not None and not self.currency.strip():
            raise ValueError('Indica la moneda del importe acordado')
        return self


class ProjectServiceLinkInput(SafeInputModel):
    service_id: int = Field(gt=0)
    reason: str = Field(min_length=1)

    @field_validator('reason')
    @classmethod
    def reject_blank_link_reason(cls, value):
        if not value.strip():
            raise ValueError('El motivo de asociación es obligatorio')
        return value.strip()


class CustomerPaymentWrite(SafeInputModel):
    service_id: int = Field(gt=0)
    reference: str = Field(min_length=1, max_length=160)
    amount: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    currency: str = Field(min_length=3, max_length=3)
    effective_date: date
    evidence_reference: str = Field(min_length=1, max_length=300)

    @field_validator('reference', 'currency', 'evidence_reference')
    @classmethod
    def strip_payment_fields(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('El valor es obligatorio')
        return value.upper() if value and len(value) == 3 else value


class PaymentAdjustmentWrite(SafeInputModel):
    amount: Annotated[Decimal, Field(ne=0, max_digits=12, decimal_places=2)]
    reason: str = Field(min_length=1)
    evidence_reference: str = Field(min_length=1, max_length=300)

    @field_validator('reason', 'evidence_reference')
    @classmethod
    def strip_adjustment_fields(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('El valor es obligatorio')
        return value
