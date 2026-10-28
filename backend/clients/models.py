# ==============================================================================
# MODELS.PY — Modelos de la base de datos para la app 'clients'
#
# Cada clase aquí representa una tabla en PostgreSQL.
# Django lee estos modelos y genera las tablas automáticamente con:
#   python manage.py makemigrations
#   python manage.py migrate
#
# Tablas que se crean en este archivo:
#   - Role          → roles de los colaboradores (Superadmin, Dev, etc.)
#   - Collaborator  → personal interno de Elomux
#   - WebCatalog    → catálogo de tipos de web con precios
#   - Client        → clientes de Elomux
#   - WebFeature    → funcionalidades extra disponibles
#   - ClientFeature → funcionalidades contratadas por cada cliente
#   - CupeLog       → historial de cambios de CUPE
# ==============================================================================

from django.db import models
from django.db.models.functions import Lower
from django.core.validators import MinValueValidator
import uuid


# ------------------------------------------------------------------------------
# ROLE — Roles del sistema
#
# Define los 5 niveles de acceso del sistema ELISA.
# Un colaborador tiene exactamente un rol.
#
# Niveles:
#   L1 - Superadmin   → acceso total, autoriza cambios de CUPE
#   L2 - Scrum Master → gestión de proyectos
#   L3 - Tech Lead    → une staging con producción
#   L4 - Líder        → lidera un área
#   L5 - Developer    → solo consulta, no puede crear usuarios
# ------------------------------------------------------------------------------
class Role(models.Model):

    LEVEL_CHOICES = [
        ('L1', 'Superadmin'),
        ('L2', 'Scrum Master'),
        ('L3', 'Tech Lead'),
        ('L4', 'Líder'),
        ('L5', 'Developer'),
    ]

    # Nombre del rol, ej: "Superadmin"
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default='')

    # Nivel del rol (L1 a L5)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES)
    is_active = models.BooleanField(default=True)
    # NULL preserves the pre-existing five-level policy; an explicit list is
    # the selected subset for an organizational role.
    permissions = models.JSONField(blank=True, null=True, default=None)

    # Fecha de creación — automática
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'roles'
        ordering = ['level']
        constraints = [
            models.UniqueConstraint(Lower('name'), name='role_name_case_insensitive_unique'),
        ]

    def __str__(self):
        return f"{self.level} - {self.name}"


class RoleHistory(models.Model):
    ACTION_CHOICES = [
        ('created', 'Creación'), ('updated', 'Modificación'),
        ('deactivated', 'Desactivación'), ('deleted', 'Eliminación'),
    ]
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='history')
    role_id_snapshot = models.IntegerField()
    role_name_snapshot = models.CharField(max_length=50)
    actor = models.ForeignKey('clients.Collaborator', on_delete=models.PROTECT, related_name='role_changes')
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    before_data = models.JSONField(null=True, blank=True)
    after_data = models.JSONField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'role_history'
        ordering = ['-recorded_at', '-id']


# ------------------------------------------------------------------------------
# COLLABORATOR — Colaboradores (personal interno de Elomux)
#
# Representa a cada persona que usa el sistema ELISA.
# Tiene credenciales de acceso (username + password) y un rol asignado.
#
# El CUPE es el código único de identificación interno, formato: ELO-XXXXXXXX
# Se genera automáticamente al crear el colaborador desde FastAPI.
# Solo Superadmin puede modificarlo.
# ------------------------------------------------------------------------------
class Collaborator(models.Model):

    DOCUMENT_TYPE_CHOICES = [
        ('DNI', 'DNI'),
        ('Pasaporte', 'Pasaporte'),
        ('CE', 'Carné de Extranjería'),
    ]

    CITY_CHOICES = [
        ('Lima', 'Lima'),
        ('Arequipa', 'Arequipa'),
        ('Cusco', 'Cusco'),
        ('Trujillo', 'Trujillo'),
        ('Piura', 'Piura'),
        ('Ica', 'Ica'),
    ]

    # CUPE — Código Único de Personal Elomux
    # Formato: ELO-XXXXXXXX (ELO + 8 dígitos generados con fórmula)
    # blank=True, null=True → se genera después de crear el registro
    cupe = models.CharField(max_length=15, unique=True, blank=True, null=True)

    # Datos personales
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPE_CHOICES,
        default='DNI'
    )
    document_number = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    city = models.CharField(max_length=50, choices=CITY_CHOICES, default='Lima')

    # Credenciales de acceso
    username = models.CharField(max_length=50, unique=True)
    # Contraseña encriptada con bcrypt — nunca se guarda en texto plano
    password_hash = models.CharField(max_length=255)

    # Rol asignado
    # on_delete=PROTECT → no deja borrar un rol si tiene colaboradores
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='collaborators'
    )

    # Área de trabajo interna
    area = models.CharField(max_length=100, blank=True, null=True)

    # Si puede o no ingresar al sistema
    # True = activo, False = dado de baja (soft delete)
    is_active = models.BooleanField(default=True)

    # Fechas automáticas
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'collaborators'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.cupe} — {self.first_name} {self.last_name}"


class CollaboratorSession(models.Model):
    """Server-side state for one independently revocable login session."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collaborator = models.ForeignKey(Collaborator, on_delete=models.PROTECT, related_name='auth_sessions')
    refresh_jti = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'collaborator_sessions'
        indexes = [models.Index(fields=['collaborator', 'revoked_at'])]


class PasswordResetRequest(models.Model):
    """Single-use password recovery; only a digest of the bearer token is stored."""
    collaborator = models.ForeignKey(Collaborator, on_delete=models.PROTECT, related_name='password_reset_requests')
    token_digest = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'password_reset_requests'


# ------------------------------------------------------------------------------
# WEBCATALOG — Catálogo de tipos de web con precios
#
# Tabla de referencia con los tipos de web que ofrece Elomux
# y sus precios base (alquiler mensual y venta única).
#
# base_price_rent → precio mensual plan alquiler
# base_price_sale → precio único plan venta (mínimo S/499)
# is_active → si está disponible para asignar a clientes
# ------------------------------------------------------------------------------
class WebCatalog(models.Model):

    # Nombre del tipo de web, ej: "Tienda/Ecommerce", "Pollería"
    name = models.CharField(max_length=100, unique=True)

    # Precio mensual en soles (plan alquiler)
    base_price_rent = models.DecimalField(max_digits=8, decimal_places=2)

    # Precio de venta única en soles (plan venta)
    # Equivale a 6 meses de alquiler, mínimo S/499
    base_price_sale = models.DecimalField(max_digits=8, decimal_places=2)

    # Si está disponible para asignar a clientes
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'web_catalog'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (S/{self.base_price_rent}/mes)"


# ------------------------------------------------------------------------------
# CLIENT — Clientes de Elomux
#
# Representa a cada cliente que contrató un servicio web con Elomux.
#
# Flujo de estados:
#   1. Cliente paga inicial → status = 'desarrollo', delivery_date = NULL
#   2. Web terminada → trabajador llena delivery_date → status = 'activo'
#   3. Las vigencias recurrentes se registran por servicio contratado.
#   4. Si no paga → status = 'inactivo'
#
# next_payment_date se conserva para compatibilidad con registros anteriores;
# no sustituye el calendario propio de cada servicio contratado.
# ------------------------------------------------------------------------------
class Client(models.Model):

    DOCUMENT_TYPE_CHOICES = [
        ('DNI', 'DNI'),
        ('RUC', 'RUC'),
    ]

    PLAN_CHOICES = [
        ('alquiler', 'Alquiler'),  # Pago mensual
        ('venta', 'Venta'),        # Pago único anual
    ]

    STATUS_CHOICES = [
        ('activo', 'Activo'),
        ('desarrollo', 'En desarrollo'),
        ('inactivo', 'Inactivo'),
    ]

    PAYMENT_FREQUENCY_CHOICES = [
        ('mensual', 'Mensual'),  # Plan alquiler
        ('anual', 'Anual'),      # Plan venta
    ]

    # CUPE del cliente — formato CLI-XXXXXXXX
    cupe = models.CharField(max_length=15, unique=True, blank=True, null=True)

    # Datos del cliente
    name = models.CharField(max_length=200)
    document_type = models.CharField(
        max_length=10,
        choices=DOCUMENT_TYPE_CHOICES,
        default='DNI'
    )
    document_number = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    # Tipo de web contratada
    # on_delete=PROTECT → no deja borrar un tipo de web si tiene clientes
    web_type = models.ForeignKey(
        WebCatalog,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        related_name='clients'
    )

    # Plan contratado
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES, default='alquiler')

    # Estado actual
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='desarrollo'
    )

    # ------------------------------------------------------------------
    # PRECIOS
    # base_price   → precio base del tipo de web (se copia al crear)
    # extra_price  → suma de precios de funcionalidades extra
    # total_price  → base_price + extra_price (calculado por FastAPI)
    # ------------------------------------------------------------------
    base_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True
    )
    initial_payment = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True
    )
    extra_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=0.00
    )
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True
    )

    # ------------------------------------------------------------------
    # FECHAS
    # registration_date  → día que pagó el inicial y se registró
    # delivery_date      → día que la web fue entregada (llena el trabajador)
    # next_payment_date  → legado; el vencimiento actual se calcula por servicio
    # ------------------------------------------------------------------
    registration_date = models.DateField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    next_payment_date = models.DateField(null=True, blank=True)

    # Frecuencia de pago según el plan
    payment_frequency = models.CharField(
        max_length=10,
        choices=PAYMENT_FREQUENCY_CHOICES,
        null=True, blank=True
    )

    # ------------------------------------------------------------------
    # DOMINIO
    # NULL  → no tiene dominio propio
    # 0.00  → cliente especial, no paga dominio
    # monto → precio acordado con el cliente
    # ------------------------------------------------------------------
    domain_price = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True
    )

    # Notas internas
    notes = models.TextField(blank=True, null=True)

    # Qué trabajador registró al cliente
    # on_delete=SET_NULL → si el trabajador es eliminado, el cliente se conserva
    created_by = models.ForeignKey(
        'Collaborator',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients_created'
    )

    # Fechas automáticas
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clients'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.cupe} — {self.name}"


class ClientChangeRequest(models.Model):
    """Audited modification or logical deactivation request for a client."""

    REQUEST_TYPES = [
        ('modificacion', 'Modificación'),
        ('baja', 'Baja'),
    ]
    STATUS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='change_requests')
    request_type = models.CharField(max_length=16, choices=REQUEST_TYPES)
    requester = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='client_change_requests',
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()
    proposed_data = models.JSONField(default=dict, blank=True)
    previous_data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pendiente')
    resolved_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, null=True, blank=True,
        related_name='client_change_resolutions',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_reason = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'client_change_requests'
        ordering = ['-requested_at', '-id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(request_type__in=['modificacion', 'baja']),
                name='client_change_request_type_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=['pendiente', 'aprobado', 'rechazado']),
                name='client_change_request_status_valid',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status='pendiente', resolved_by__isnull=True, resolved_at__isnull=True)
                    | models.Q(status__in=['aprobado', 'rechazado'], resolved_by__isnull=False, resolved_at__isnull=False)
                ),
                name='client_change_request_resolution_consistent',
            ),
        ]


class ClientHistory(models.Model):
    """Append-only chronology for client creation, requests and decisions."""

    EVENT_TYPES = [
        ('cliente_creado', 'Cliente creado'),
        ('modificacion_solicitada', 'Modificación solicitada'),
        ('modificacion_aprobada', 'Modificación aprobada'),
        ('modificacion_rechazada', 'Modificación rechazada'),
        ('baja_solicitada', 'Baja solicitada'),
        ('baja_aprobada', 'Baja aprobada'),
        ('baja_rechazada', 'Baja rechazada'),
    ]

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='history')
    request = models.ForeignKey(
        ClientChangeRequest, on_delete=models.PROTECT, null=True, blank=True,
        related_name='history_events',
    )
    actor = models.ForeignKey(Collaborator, on_delete=models.PROTECT, related_name='client_history_events')
    event_type = models.CharField(max_length=28, choices=EVENT_TYPES)
    occurred_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True, default='')
    before_data = models.JSONField(default=dict, blank=True)
    after_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'client_history'
        ordering = ['-occurred_at', '-id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(event_type__in=[
                    'cliente_creado', 'modificacion_solicitada', 'modificacion_aprobada',
                    'modificacion_rechazada', 'baja_solicitada', 'baja_aprobada', 'baja_rechazada',
                ]),
                name='client_history_event_type_valid',
            ),
            models.UniqueConstraint(
                fields=['request', 'event_type'], condition=models.Q(request__isnull=False),
                name='client_history_request_event_unique',
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('El historial de clientes es inmutable')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('El historial de clientes es inmutable')


class Project(models.Model):
    STATUS_CHOICES = [
        ('Planificado', 'Planificado'),
        ('En ejecución', 'En ejecución'),
        ('En validación técnica', 'En validación técnica'),
        ('Listo para entrega', 'Listo para entrega'),
        ('Entregado', 'Entregado'),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name='projects',
    )
    name = models.CharField(max_length=200)
    objective = models.TextField(blank=True, null=True)
    scope = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default='Planificado')

    class Meta:
        db_table = 'projects'
        ordering = ['id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=[
                    'Planificado', 'En ejecución', 'En validación técnica',
                    'Listo para entrega', 'Entregado',
                ]),
                name='project_status_valid',
            ),
        ]

    def __str__(self):
        return self.name


class ProjectCoordination(models.Model):
    """Explicit L2→L3 coordination assignment for one project."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='coordinations')
    coordinator = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='project_coordinations',
    )
    assigned_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='coordinations_made',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    ended_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, null=True, blank=True, related_name='coordinations_ended',
    )
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'project_coordinations'
        constraints = [models.UniqueConstraint(
            fields=['project', 'coordinator'], condition=models.Q(is_active=True),
            name='project_coordinator_unique',
        )]


class ProjectCommercialAuthorization(models.Model):
    """Positive L2 evidence that a project's authorized work may start."""

    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name='commercial_authorizations',
    )
    authorized_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='project_commercial_authorizations',
    )
    authorized_at = models.DateTimeField(auto_now_add=True)
    effective_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    authorized_scope = models.TextField()
    commitment_reference = models.CharField(max_length=200)
    start_conditions = models.TextField()
    start_conditions_accredited = models.BooleanField(default=False)
    evidence_reference = models.CharField(max_length=300)

    class Meta:
        db_table = 'project_commercial_authorizations'
        ordering = ['-authorized_at', '-id']


class ProjectCommercialAuthorizationEvent(models.Model):
    EVENT_CHOICES = [
        ('retirada', 'Retirada'),
        ('sustituida', 'Sustituida'),
    ]

    authorization = models.ForeignKey(
        ProjectCommercialAuthorization, on_delete=models.PROTECT, related_name='events',
    )
    event_type = models.CharField(max_length=12, choices=EVENT_CHOICES)
    actor = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='commercial_authorization_events',
    )
    reason = models.TextField()
    replacement = models.ForeignKey(
        ProjectCommercialAuthorization, on_delete=models.PROTECT, null=True, blank=True,
        related_name='replaced_authorizations',
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_commercial_authorization_events'
        ordering = ['occurred_at', 'id']
        constraints = [models.UniqueConstraint(
            fields=['authorization'],
            condition=models.Q(event_type__in=['retirada', 'sustituida']),
            name='project_auth_single_close_event',
        )]


class ProjectLeadership(models.Model):
    """Explicit L3→L4 delegation within an L3-coordinated project."""

    coordination = models.ForeignKey(
        ProjectCoordination, on_delete=models.CASCADE, related_name='leaderships',
    )
    leader = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='project_leaderships',
    )
    designated_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='leaderships_designated',
    )
    designated_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    ended_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, null=True, blank=True, related_name='leaderships_ended',
    )
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'project_leaderships'
        constraints = [models.UniqueConstraint(
            fields=['coordination', 'leader'], condition=models.Q(is_active=True),
            name='coordination_leader_unique',
        )]


class OrganizationalSubstitution(models.Model):
    """Time-bounded, auditable substitution within an existing project scope."""

    ABSENT_LEVELS = [('L3', 'L3'), ('L4', 'L4')]
    FACULTY_CHOICES = [
        ('tasks.view', 'Consultar tareas'),
        ('tasks.review', 'Revisar tareas'),
    ]

    coordination = models.ForeignKey(
        ProjectCoordination, on_delete=models.PROTECT, related_name='substitutions',
    )
    leadership = models.ForeignKey(
        ProjectLeadership, on_delete=models.PROTECT, null=True, blank=True,
        related_name='substitutions',
    )
    absent_level = models.CharField(max_length=2, choices=ABSENT_LEVELS)
    absent_person = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='substitutions_as_absent',
    )
    substitute = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, null=True, blank=True,
        related_name='organizational_substitutions',
    )
    designated_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='substitutions_designated',
    )
    reason = models.TextField()
    evidence = models.TextField()
    scope = models.TextField()
    faculties = models.JSONField(default=list)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    ended_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, null=True, blank=True,
        related_name='substitutions_ended',
    )
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'organizational_substitutions'
        ordering = ['-created_at', '-id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_until__gt=models.F('valid_from')),
                name='org_substitution_valid_period',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(is_active=True, ended_by__isnull=True, ended_at__isnull=True)
                    | models.Q(is_active=False, ended_at__isnull=False)
                ),
                name='org_substitution_end_consistent',
            ),
            models.UniqueConstraint(
                fields=['coordination', 'absent_person'], condition=models.Q(is_active=True),
                name='org_substitution_single_active_scope',
            ),
        ]


class ProjectEvent(models.Model):
    """Audit record of explicitly authorized project status transitions."""

    event_type = models.CharField(max_length=40)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(Collaborator, on_delete=models.PROTECT, related_name='project_events')
    commercial_authorization = models.ForeignKey(
        ProjectCommercialAuthorization, on_delete=models.PROTECT, null=True, blank=True,
        related_name='project_transitions',
    )
    technical_evaluation = models.ForeignKey(
        'ProjectTechnicalEvaluation', on_delete=models.PROTECT, null=True, blank=True,
        related_name='project_transitions',
    )
    delivery_authorization = models.ForeignKey(
        'ProjectDeliveryAuthorization', on_delete=models.PROTECT, null=True, blank=True,
        related_name='project_transitions',
    )
    delivery_records = models.ManyToManyField(
        'ProjectDelivery', through='ProjectDeliveryTransition', related_name='project_transitions',
    )
    previous_status = models.CharField(max_length=24)
    new_status = models.CharField(max_length=24)
    reason = models.TextField()
    evidence = models.TextField()
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_events'
        ordering = ['occurred_at', 'id']


class ProjectCancellation(models.Model):
    """A full-project cancellation workflow, separate from ordinary project status."""

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='cancellations')
    opened_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='project_cancellations_opened',
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    cancelled_scope = models.TextField()
    reason = models.TextField()
    evidence = models.TextField()

    class Meta:
        db_table = 'project_cancellations'
        ordering = ['opened_at', 'id']


class ProjectCancellationEvent(models.Model):
    EVENT_CHOICES = [
        ('solicitada', 'Cancelación solicitada'),
        ('evaluacion_tecnica', 'Evaluación técnica'),
        ('evaluacion_comercial', 'Evaluación comercial'),
        ('escalamiento_l1', 'Escalamiento formal a L1'),
        ('autorizada', 'Cancelación autorizada'),
        ('denegada', 'Cancelación denegada'),
        ('efectiva', 'Cancelación efectiva'),
        ('decision_l1_autorizada', 'Cancelación excepcional autorizada por L1'),
        ('decision_l1_denegada', 'Cancelación excepcional denegada por L1'),
    ]

    cancellation = models.ForeignKey(
        ProjectCancellation, on_delete=models.PROTECT, related_name='events',
    )
    event_type = models.CharField(max_length=24, choices=EVENT_CHOICES)
    actor = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='project_cancellation_events',
    )
    reason = models.TextField()
    evidence = models.TextField()
    data = models.JSONField(default=dict)
    effective_at = models.DateTimeField(null=True, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_cancellation_events'
        ordering = ['occurred_at', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['cancellation'], condition=models.Q(event_type='evaluacion_tecnica'),
                name='project_cancel_single_technical_eval',
            ),
            models.UniqueConstraint(
                fields=['cancellation'], condition=models.Q(event_type__in=['autorizada', 'denegada']),
                name='project_cancel_single_decision',
            ),
            models.UniqueConstraint(
                fields=['cancellation'], condition=models.Q(event_type='efectiva'),
                name='project_cancel_single_effectivity',
            ),
            models.UniqueConstraint(
                fields=['cancellation'],
                condition=models.Q(event_type__in=['decision_l1_autorizada', 'decision_l1_denegada']),
                name='project_cancel_single_l1_decision',
            ),
            models.CheckConstraint(
                condition=(models.Q(event_type='efectiva', effective_at__isnull=False)
                           | (~models.Q(event_type='efectiva') & models.Q(effective_at__isnull=True))),
                name='project_cancel_effectivity_consistent',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('El historial de cancelación de proyectos es inmutable')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('El historial de cancelación de proyectos es inmutable')


class ProjectResumption(models.Model):
    """Independent resumption record linked to an effective cancellation."""

    cancellation = models.OneToOneField(
        ProjectCancellation, on_delete=models.PROTECT, related_name='resumption',
    )
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='resumptions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_resumptions'
        ordering = ['created_at', 'id']


class ProjectResumptionEvent(models.Model):
    EVENT_CHOICES = [
        ('evaluacion_tecnica', 'Evaluación técnica L3'),
        ('decision_comercial_aprobada', 'Decisión comercial aprobada por L2'),
        ('decision_comercial_denegada', 'Decisión comercial denegada por L2'),
        ('decision_l1_aprobada', 'Decisión L1 aprobada'),
        ('decision_l1_denegada', 'Decisión L1 denegada'),
        ('reanudacion_registrada', 'Reanudación registrada'),
    ]

    resumption = models.ForeignKey(
        ProjectResumption, on_delete=models.PROTECT, related_name='events',
    )
    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES)
    actor = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='project_resumption_events',
    )
    reason = models.TextField()
    evidence = models.TextField()
    data = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_resumption_events'
        ordering = ['occurred_at', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['resumption'], condition=models.Q(event_type='evaluacion_tecnica'),
                name='project_resume_single_technical_eval',
            ),
            models.UniqueConstraint(
                fields=['resumption'], condition=models.Q(event_type__in=[
                    'decision_comercial_aprobada', 'decision_comercial_denegada',
                ]), name='project_resume_single_l2_decision',
            ),
            models.UniqueConstraint(
                fields=['resumption'], condition=models.Q(event_type__in=[
                    'decision_l1_aprobada', 'decision_l1_denegada',
                ]), name='project_resume_single_l1_decision',
            ),
            models.UniqueConstraint(
                fields=['resumption'], condition=models.Q(event_type='reanudacion_registrada'),
                name='project_resume_single_registration',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('El historial de reanudación de proyectos es inmutable')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('El historial de reanudación de proyectos es inmutable')


class ProjectTaskClassification(models.Model):
    """Immutable audit revisions for L3's delivery-scope classification of tasks."""

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='task_classifications')
    task = models.ForeignKey('Task', on_delete=models.PROTECT, related_name='project_classifications')
    actor = models.ForeignKey(Collaborator, on_delete=models.PROTECT, related_name='task_classifications_made')
    is_mandatory = models.BooleanField()
    scope_snapshot = models.TextField()
    reason = models.TextField()
    is_current = models.BooleanField(default=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_task_classifications'
        ordering = ['occurred_at', 'id']
        constraints = [models.UniqueConstraint(
            fields=['task'], condition=models.Q(is_current=True),
            name='project_task_classification_current_unique',
        )]


class ProjectTechnicalEvaluation(models.Model):
    """Historical L3 technical close evaluation for one validation cycle."""

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='technical_evaluations')
    validation_event = models.ForeignKey(
        ProjectEvent, on_delete=models.PROTECT, related_name='technical_evaluations',
    )
    actor = models.ForeignKey(Collaborator, on_delete=models.PROTECT, related_name='project_technical_evaluations')
    scope_snapshot = models.TextField()
    satisfactory = models.BooleanField()
    technical_enablement_status = models.CharField(max_length=16, choices=[
        ('Vigente', 'Vigente'), ('En revisión', 'En revisión'), ('No vigente', 'No vigente'),
    ])
    ordinary_close_valid = models.BooleanField()
    obligations_compatible = models.BooleanField()
    result_summary = models.TextField()
    evidence = models.TextField()
    ordinary_close_evidence = models.TextField()
    obligations_assessment = models.TextField()
    optional_task_assessments = models.JSONField(default=list)
    validated_versions = models.JSONField(default=list)
    task_snapshot = models.JSONField(default=list)
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_technical_evaluations'
        ordering = ['evaluated_at', 'id']
        constraints = [models.CheckConstraint(
            condition=models.Q(technical_enablement_status__in=['Vigente', 'En revisión', 'No vigente']),
            name='project_technical_enablement_status_valid',
        )]


class ProjectDeliveryAuthorization(models.Model):
    """L2 authorization for preparing delivery, distinct from project start authorization."""

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='delivery_authorizations')
    authorized_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='project_delivery_authorizations',
    )
    authorized_at = models.DateTimeField(auto_now_add=True)
    effective_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    authorized_scope = models.TextField()
    scope_snapshot = models.TextField()
    effectivity_conditions = models.TextField()
    conditions_accredited = models.BooleanField(default=False)
    evidence_reference = models.CharField(max_length=300)

    class Meta:
        db_table = 'project_delivery_authorizations'
        ordering = ['-authorized_at', '-id']
        constraints = [models.CheckConstraint(
            condition=(
                models.Q(expires_at__isnull=True)
                | models.Q(expires_at__gt=models.F('effective_at'))
            ),
            name='project_delivery_auth_expiry_after_effective',
        )]


class ProjectDeliveryAuthorizationEvent(models.Model):
    EVENT_CHOICES = [
        ('retirada', 'Retirada'),
        ('sustituida', 'Sustituida'),
    ]

    authorization = models.ForeignKey(
        ProjectDeliveryAuthorization, on_delete=models.PROTECT, related_name='events',
    )
    event_type = models.CharField(max_length=12, choices=EVENT_CHOICES)
    actor = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='delivery_authorization_events',
    )
    reason = models.TextField()
    replacement = models.ForeignKey(
        ProjectDeliveryAuthorization, on_delete=models.PROTECT, null=True, blank=True,
        related_name='replaced_authorizations',
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_delivery_authorization_events'
        ordering = ['occurred_at', 'id']
        constraints = [models.UniqueConstraint(
            fields=['authorization'],
            condition=models.Q(event_type__in=['retirada', 'sustituida']),
            name='project_delivery_auth_single_close_event',
        )]


class ProjectDelivery(models.Model):
    """Immutable evidence of a partial or integral commercial transfer."""

    DELIVERY_TYPES = [('parcial', 'Parcial'), ('integral', 'Integral')]

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='deliveries')
    recorded_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='project_deliveries_recorded',
    )
    preparation_authorization = models.ForeignKey(
        ProjectDeliveryAuthorization, on_delete=models.PROTECT, related_name='deliveries',
    )
    delivery_type = models.CharField(max_length=12, choices=DELIVERY_TYPES)
    scope = models.TextField()
    scope_within_authorization = models.BooleanField(default=False)
    covers_project_scope = models.BooleanField(default=False)
    version_reference = models.CharField(max_length=200)
    recipient = models.CharField(max_length=200)
    delivery_method = models.TextField()
    performed_by = models.CharField(max_length=200)
    evidence_reference = models.CharField(max_length=300)
    occurred_at = models.DateTimeField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_deliveries'
        ordering = ['occurred_at', 'id']
        constraints = [models.CheckConstraint(
            condition=models.Q(delivery_type__in=['parcial', 'integral']),
            name='project_delivery_type_valid',
        ), models.CheckConstraint(
            condition=models.Q(scope_within_authorization=True),
            name='project_delivery_scope_attested',
        ), models.CheckConstraint(
            condition=(
                models.Q(delivery_type='integral', covers_project_scope=True)
                | models.Q(delivery_type='parcial', covers_project_scope=False)
            ),
            name='project_delivery_coverage_kind_valid',
        )]


class ProjectDeliveryTechnicalReview(models.Model):
    """L3's technical enablement review for a version before its delivery."""

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='delivery_version_reviews')
    version_reference = models.CharField(max_length=200)
    technical_evaluation = models.ForeignKey(
        ProjectTechnicalEvaluation, on_delete=models.PROTECT, related_name='delivery_reviews',
    )
    actor = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='project_delivery_reviews',
    )
    satisfactory = models.BooleanField()
    technical_enablement_status = models.CharField(max_length=16, choices=[
        ('Vigente', 'Vigente'), ('En revisión', 'En revisión'), ('No vigente', 'No vigente'),
    ])
    result_summary = models.TextField()
    evidence = models.TextField()
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_delivery_technical_reviews'
        ordering = ['reviewed_at', 'id']
        constraints = [models.CheckConstraint(
            condition=models.Q(technical_enablement_status__in=['Vigente', 'En revisión', 'No vigente']),
            name='project_delivery_review_status_valid',
        )]


class ProjectDeliveryTransition(models.Model):
    """Relates each delivery record to the one transition it substantiates."""

    event = models.ForeignKey(ProjectEvent, on_delete=models.PROTECT, related_name='delivery_evidence_links')
    delivery = models.ForeignKey(ProjectDelivery, on_delete=models.PROTECT, related_name='transition_links')

    class Meta:
        db_table = 'project_delivery_transitions'
        constraints = [
            models.UniqueConstraint(fields=['event', 'delivery'], name='project_delivery_transition_pair_unique'),
            models.UniqueConstraint(fields=['delivery'], name='project_delivery_used_once'),
        ]


class TeamMembership(models.Model):
    """Explicit L4→L5 team membership, scoped to a project leadership."""

    leadership = models.ForeignKey(
        ProjectLeadership, on_delete=models.CASCADE, related_name='memberships',
    )
    developer = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='team_memberships',
    )
    added_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='team_memberships_added',
    )
    added_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    ended_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, null=True, blank=True, related_name='team_memberships_ended',
    )
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'team_memberships'
        constraints = [models.UniqueConstraint(
            fields=['leadership', 'developer'], condition=models.Q(is_active=True),
            name='leadership_developer_unique',
        )]


class Task(models.Model):
    STATUS_CHOICES = [
        ('Pendiente', 'Pendiente'), ('Asignada', 'Asignada'),
        ('En proceso', 'En proceso'), ('En revisión', 'En revisión'),
        ('Observada', 'Observada'), ('Finalizada', 'Finalizada'), ('Cancelada', 'Cancelada'),
    ]

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pendiente')
    created_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='tasks_created',
    )
    responsible = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='tasks_responsible',
    )
    assignee = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, null=True, blank=True, related_name='tasks_assigned',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_blocked = models.BooleanField(default=False)
    block_reason = models.TextField(blank=True, default='')
    block_evidence = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'tasks'
        ordering = ['-created_at', 'id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=[
                    'Pendiente', 'Asignada', 'En proceso', 'En revisión', 'Observada', 'Finalizada', 'Cancelada',
                ]),
                name='task_status_valid',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status__in=['Pendiente', 'Cancelada'], assignee__isnull=True, assigned_at__isnull=True)
                    | models.Q(status='Cancelada', assignee__isnull=False, assigned_at__isnull=False)
                    | models.Q(
                        status__in=['Asignada', 'En proceso', 'En revisión', 'Observada', 'Finalizada'],
                        assignee__isnull=False, assigned_at__isnull=False,
                    )
                ),
                name='task_assignment_matches_status',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(is_blocked=True) & ~models.Q(block_reason='')
                    | models.Q(is_blocked=False, block_reason='', block_evidence='')
                ),
                name='task_block_condition_consistent',
            ),
        ]


class TaskEvent(models.Model):
    EVENT_CHOICES = [
        ('creada', 'Creada'), ('asignada', 'Asignada'),
        ('comentario_agregado', 'Comentario agregado'),
        ('iniciada', 'Iniciada'), ('resultado_presentado', 'Resultado presentado'),
        ('observada', 'Observada'), ('aprobada_revision', 'Aprobada en revisión'),
        ('correccion_iniciada', 'Corrección iniciada'),
        ('ejecutor_reasignado', 'Ejecutor reasignado'),
        ('ejecutor_retirado', 'Ejecutor retirado'),
        ('bloqueo_declarado', 'Bloqueo declarado'),
        ('bloqueo_levantado', 'Bloqueo levantado'),
        ('incidencia_comunicada', 'Incidencia comunicada'),
        ('reapertura_autorizada', 'Reapertura autorizada'),
        ('cancelacion_propuesta', 'Cancelación propuesta'),
        ('cancelacion_pendiente', 'Evaluación de cancelación pendiente'),
        ('cancelacion_autorizada', 'Cancelación autorizada'),
        ('cancelacion_denegada', 'Cancelación denegada'),
        ('revision_comercial_pend', 'Revisión comercial pendiente'),
        ('revision_comercial_resuelta', 'Revisión comercial resuelta'),
        ('cancelacion_aplicada', 'Cancelación aplicada'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    actor = models.ForeignKey(Collaborator, on_delete=models.PROTECT, related_name='task_events')
    previous_status = models.CharField(max_length=20, blank=True, default='')
    new_status = models.CharField(max_length=20)
    assignee = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, null=True, blank=True, related_name='task_assignment_events',
    )
    previous_assignee = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, null=True, blank=True,
        related_name='task_previous_assignment_events',
    )
    responsible = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, null=True, blank=True,
        related_name='task_responsibility_events',
    )
    previous_responsible = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, null=True, blank=True,
        related_name='task_previous_responsibility_events',
    )
    is_blocked_before = models.BooleanField(default=False)
    is_blocked_after = models.BooleanField(default=False)
    evidence = models.TextField(blank=True, default='')
    result_text = models.TextField(blank=True, default='')
    reason = models.TextField(blank=True, default='')
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'task_events'
        ordering = ['occurred_at', 'id']


class TaskComment(models.Model):
    """Immutable comment attached to an authorized task event."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    event = models.OneToOneField(
        TaskEvent, on_delete=models.CASCADE, related_name='comment',
    )
    author = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='task_comments',
    )
    content = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'task_comments'
        ordering = ['created_at', 'id']


class InternalNotification(models.Model):
    """User-scoped internal notice generated from an approved task event."""

    event = models.ForeignKey(
        TaskEvent, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True,
    )
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name='internal_notifications', null=True, blank=True,
    )
    recipient = models.ForeignKey(
        Collaborator, on_delete=models.CASCADE, related_name='internal_notifications',
    )
    notice_type = models.CharField(max_length=30, default='event')
    source_key = models.CharField(max_length=160, null=True, blank=True, unique=True)
    title = models.CharField(max_length=100)
    message = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'internal_notifications'
        ordering = ['-created_at', '-id']
        constraints = [models.UniqueConstraint(
            fields=['event', 'recipient'], name='internal_notification_event_recipient_unique',
        )]


class TaskDeadlineNotificationConfig(models.Model):
    """Configuration for the existing internal task deadline reminder."""

    key = models.CharField(max_length=40, unique=True, default='task_deadline')
    days_before = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    updated_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, null=True, blank=True,
        related_name='task_deadline_notification_configs',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'task_deadline_notification_configs'
        constraints = [models.CheckConstraint(
            condition=models.Q(days_before__gte=1), name='task_deadline_days_before_positive',
        )]


class TaskDeadlineNotificationConfigEvent(models.Model):
    """Immutable audit entries for changes to reminder configuration."""

    config = models.ForeignKey(
        TaskDeadlineNotificationConfig, on_delete=models.PROTECT, related_name='history',
    )
    actor = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='task_deadline_notification_config_events',
    )
    previous_days_before = models.PositiveIntegerField()
    new_days_before = models.PositiveIntegerField()
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'task_deadline_notification_config_events'
        ordering = ['occurred_at', 'id']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('El historial de configuración de alertas es inmutable')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('El historial de configuración de alertas es inmutable')


# ------------------------------------------------------------------------------
# WEBFEATURE — Funcionalidades adicionales
#
# Catálogo de funcionalidades extra que se pueden agregar a clientes.
# Sin tipos asociados la funcionalidad es global; con asociaciones sólo
# aplica a los tipos de web seleccionados.
#
# Ejemplos: Sistema de citas, Carrito de compras, Pasarela de pagos
#
# ClientFeature registra las funcionalidades contratadas por cada cliente.
# ------------------------------------------------------------------------------
class WebFeature(models.Model):

    # Nombre de la funcionalidad
    name = models.CharField(max_length=100, unique=True)

    # Precio adicional al precio base del cliente
    extra_price = models.DecimalField(max_digits=8, decimal_places=2)

    # Si está disponible para asignar a clientes
    is_active = models.BooleanField(default=True)

    web_types = models.ManyToManyField(
        WebCatalog,
        blank=True,
        related_name='available_features',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'web_features'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (S/{self.extra_price})"


# ------------------------------------------------------------------------------
# CLIENTFEATURE — Funcionalidades contratadas por cada cliente
#
# Tabla intermedia que conecta clientes con sus funcionalidades extra.
# Un cliente puede tener varias funcionalidades y una funcionalidad
# puede estar en varios clientes.
# ------------------------------------------------------------------------------
class ClientFeature(models.Model):

    # Cliente que tiene esta funcionalidad
    # CASCADE → si se elimina el cliente, se eliminan sus funcionalidades
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='features'
    )

    # Funcionalidad contratada
    # PROTECT → no deja eliminar una funcionalidad si tiene clientes
    feature = models.ForeignKey(
        WebFeature,
        on_delete=models.PROTECT,
        related_name='client_features'
    )

    # Fecha en que se asignó esta funcionalidad al cliente
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'client_features'
        # Un cliente no puede tener la misma funcionalidad dos veces
        unique_together = ['client', 'feature']

    def __str__(self):
        return f"{self.client.cupe} — {self.feature.name}"


class ContractedService(models.Model):
    """Commercial service commitment recorded independently from its catalog offer."""

    FREQUENCY_CHOICES = [
        ('unica', 'Pago único'),
        ('mensual', 'Mensual'),
        ('anual', 'Anual'),
    ]

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='contracted_services')
    service_name = models.CharField(max_length=160)
    catalog_service = models.ForeignKey(
        WebCatalog, on_delete=models.PROTECT, null=True, blank=True, related_name='contracted_services',
    )
    commitment_reference = models.CharField(max_length=200)
    scope = models.TextField()
    agreed_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True, default='')
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    effective_start = models.DateField(null=True, blank=True)
    contracted_duration = models.CharField(max_length=120, blank=True, default='')
    documented_expiration = models.DateField(null=True, blank=True)
    terms = models.TextField(blank=True, default='')
    evidence_reference = models.CharField(max_length=300)
    recorded_by = models.ForeignKey(Collaborator, on_delete=models.PROTECT, related_name='contracted_services_recorded')
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contracted_services'
        ordering = ['client_id', 'id']
        constraints = [
            models.CheckConstraint(condition=models.Q(frequency__in=['unica', 'mensual', 'anual']), name='contracted_service_frequency_valid'),
            models.CheckConstraint(condition=models.Q(agreed_amount__isnull=True) | models.Q(agreed_amount__gte=0), name='contracted_service_amount_nonnegative'),
        ]


class ElomuxPlatform(models.Model):
    """Organizational marketing/acquisition platform, separate from service catalog."""

    name = models.CharField(max_length=120)
    url = models.URLField(max_length=500)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='elomux_platforms_created',
    )
    updated_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='elomux_platforms_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'elomux_platforms'
        ordering = ['name', 'id']
        constraints = [
            models.UniqueConstraint(Lower('name'), name='elomux_platform_name_case_insensitive_unique'),
        ]


class ElomuxPlatformEvent(models.Model):
    """Immutable change history for organizational platform records."""

    platform = models.ForeignKey(ElomuxPlatform, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(Collaborator, on_delete=models.PROTECT, related_name='elomux_platform_events')
    action = models.CharField(max_length=12, choices=[('created', 'Creada'), ('updated', 'Actualizada')])
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField()
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'elomux_platform_events'
        ordering = ['occurred_at', 'id']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('El historial de plataformas ELOMUX es inmutable')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('El historial de plataformas ELOMUX es inmutable')


class ContractedServiceHistory(models.Model):
    service = models.ForeignKey(ContractedService, on_delete=models.PROTECT, related_name='history')
    actor = models.ForeignKey(Collaborator, on_delete=models.PROTECT, related_name='contracted_service_history')
    action = models.CharField(max_length=16, choices=[('registro', 'Registro'), ('modificacion', 'Modificación')])
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField()
    reason = models.TextField(blank=True, default='')
    impact_assessment = models.TextField(blank=True, default='')
    evidence_reference = models.CharField(max_length=300)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contracted_service_history'
        ordering = ['occurred_at', 'id']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('El historial de servicios contratados es inmutable')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('El historial de servicios contratados es inmutable')


class ProjectContractedService(models.Model):
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name='contracted_service_links')
    service = models.ForeignKey(ContractedService, on_delete=models.PROTECT, related_name='project_links')
    linked_by = models.ForeignKey(Collaborator, on_delete=models.PROTECT, related_name='project_service_links')
    linked_at = models.DateTimeField(auto_now_add=True)
    link_reason = models.TextField()
    commitment_snapshot = models.JSONField(default=dict)
    unlinked_by = models.ForeignKey(Collaborator, on_delete=models.PROTECT, null=True, blank=True, related_name='project_service_unlinks')
    unlinked_at = models.DateTimeField(null=True, blank=True)
    unlink_reason = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'project_contracted_services'
        ordering = ['linked_at', 'id']
        constraints = [models.UniqueConstraint(
            fields=['service'], condition=models.Q(unlinked_at__isnull=True),
            name='contracted_service_single_active_project',
        )]


class CustomerPayment(models.Model):
    """A client receipt with separate registration and confirmation acts."""
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='payments')
    service = models.ForeignKey(ContractedService, on_delete=models.PROTECT, related_name='payments')
    reference = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    effective_date = models.DateField()
    evidence_reference = models.CharField(max_length=300)
    recorded_by = models.ForeignKey(Collaborator, on_delete=models.PROTECT, related_name='payments_recorded')
    recorded_at = models.DateTimeField(auto_now_add=True)
    confirmed_by = models.ForeignKey(Collaborator, on_delete=models.PROTECT, null=True, blank=True, related_name='payments_confirmed')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmation_evidence = models.CharField(max_length=300, blank=True, default='')

    class Meta:
        db_table = 'customer_payments'
        constraints = [
            models.UniqueConstraint(fields=['client', 'reference'], name='customer_payment_client_reference_unique'),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='customer_payment_amount_positive'),
            models.CheckConstraint(
                condition=(models.Q(confirmed_by__isnull=True, confirmed_at__isnull=True) |
                           models.Q(confirmed_by__isnull=False, confirmed_at__isnull=False)),
                name='customer_payment_confirmation_consistent',
            ),
        ]


class CustomerPaymentAdjustment(models.Model):
    """Append-only confirmed or pending adjustment linked to its original receipt."""
    payment = models.ForeignKey(CustomerPayment, on_delete=models.PROTECT, related_name='adjustments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    evidence_reference = models.CharField(max_length=300)
    recorded_by = models.ForeignKey(Collaborator, on_delete=models.PROTECT, related_name='payment_adjustments_recorded')
    recorded_at = models.DateTimeField(auto_now_add=True)
    confirmed_by = models.ForeignKey(Collaborator, on_delete=models.PROTECT, null=True, blank=True, related_name='payment_adjustments_confirmed')
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'customer_payment_adjustments'
        constraints = [
            models.CheckConstraint(condition=~models.Q(amount=0), name='customer_payment_adjustment_nonzero'),
            models.CheckConstraint(
                condition=(models.Q(confirmed_by__isnull=True, confirmed_at__isnull=True) |
                           models.Q(confirmed_by__isnull=False, confirmed_at__isnull=False)),
                name='customer_payment_adjustment_confirmation_consistent',
            ),
        ]


class CollaboratorPayment(models.Model):
    """Immutable record of a completed payment made to a collaborator."""
    collaborator = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='payments_received',
    )
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    concept = models.CharField(max_length=150)
    observation = models.CharField(max_length=300, blank=True, default='')
    reference = models.CharField(max_length=24, unique=True, null=True, blank=True)
    request_key = models.UUIDField(unique=True)
    registered_by = models.ForeignKey(
        Collaborator, on_delete=models.PROTECT, related_name='collaborator_payments_recorded',
    )
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'collaborator_payments'
        ordering = ['-payment_date', '-registered_at', '-id']
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='collaborator_payment_amount_positive'),
        ]


# ------------------------------------------------------------------------------
# CUPELOG — Historial de cambios de CUPE
#
# Registra cada vez que se cambia el CUPE de un cliente o colaborador.
# Solo el Superadmin (L1) puede autorizar estos cambios.
#
# entity_type indica si el cambio fue en un cliente o colaborador.
# entity_id es el ID del cliente o colaborador afectado.
# ------------------------------------------------------------------------------
class CupeLog(models.Model):

    ENTITY_TYPE_CHOICES = [
        ('client', 'Cliente'),
        ('collaborator', 'Colaborador'),
    ]

    REASON_CHOICES = [
        ('error_generacion', 'Error de generación'),
        ('reingreso', 'Reingreso'),
        ('correccion_admin', 'Corrección administrativa'),
        ('correccion_administrativa', 'Corrección administrativa'),
        ('solicitud_cliente', 'Solicitud del cliente'),
        ('migracion_sistema', 'Migración del sistema'),
        ('otro', 'Otro'),
    ]

    # Si el cambio fue en un cliente o colaborador
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPE_CHOICES)

    # ID del cliente o colaborador afectado
    entity_id = models.IntegerField()

    # CUPE anterior y nuevo
    old_cupe = models.CharField(max_length=15)
    new_cupe = models.CharField(max_length=15)

    # Motivo del cambio
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)

    # Observaciones adicionales (obligatorio si reason='otro')
    observations = models.TextField(blank=True, null=True)

    # Qué trabajador solicitó el cambio
    changed_by = models.ForeignKey(
        Collaborator,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cupe_changes'
    )

    # Qué Superadmin autorizó el cambio
    authorized_by = models.ForeignKey(
        Collaborator,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cupe_authorizations'
    )

    # Fecha y hora exacta del cambio
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cupe_logs'
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.old_cupe} → {self.new_cupe} ({self.changed_at.date()})"
