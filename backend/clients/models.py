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

    # Nivel del rol (L1 a L5)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES, unique=True)

    # Fecha de creación — automática
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'roles'
        ordering = ['level']

    def __str__(self):
        return f"{self.level} - {self.name}"


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
#   3. Cliente paga cada mes/año → next_payment_date avanza
#   4. Si no paga → status = 'inactivo'
#
# Lógica de next_payment_date:
#   - Plan alquiler (mensual) → mismo día del mes siguiente a delivery_date
#   - Plan venta (anual) → mismo día y mes del año siguiente a registration_date
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
    # next_payment_date  → calculado automáticamente por FastAPI
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


# ------------------------------------------------------------------------------
# WEBFEATURE — Funcionalidades adicionales
#
# Catálogo independiente de funcionalidades extra que se pueden agregar
# a cualquier cliente por un precio adicional.
#
# Ejemplos: Sistema de citas, Carrito de compras, Pasarela de pagos
#
# No depende de ningún tipo de web — cualquier funcionalidad se puede
# agregar a cualquier cliente. La relación va en ClientFeature.
# ------------------------------------------------------------------------------
class WebFeature(models.Model):

    # Nombre de la funcionalidad
    name = models.CharField(max_length=100, unique=True)

    # Precio adicional al precio base del cliente
    extra_price = models.DecimalField(max_digits=8, decimal_places=2)

    # Si está disponible para asignar a clientes
    is_active = models.BooleanField(default=True)

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