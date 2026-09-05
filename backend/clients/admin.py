# ==============================================================================
# ADMIN.PY — Registro de modelos en el panel de administración de Django
#
# Django trae un panel web en /admin/ donde puedes ver, crear, editar
# y eliminar registros directamente en la base de datos, sin tocar código.
# Es como un gestor visual de PostgreSQL pero más amigable.
#
# Para que un modelo aparezca en ese panel, hay que registrarlo aquí.
# Si no lo registras, el modelo existe en la BD pero no aparece en /admin/.
#
# Acceso: http://localhost:8000/admin/
# Usuario: el que crees con → python manage.py createsuperuser
# ==============================================================================

from django.contrib import admin

# Importamos todos los modelos — incluyendo ClientFeature que es nuevo
from .models import Role, Collaborator, Client, WebCatalog, CupeLog, WebFeature, ClientFeature


# ------------------------------------------------------------------------------
# ROLE — Registro simple
# Solo hay 5 roles en el sistema, no necesitan configuración especial.
# ------------------------------------------------------------------------------
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):

    # Columnas visibles en la lista del panel
    list_display = ['level', 'name', 'created_at']

    # Búsqueda por nombre y nivel
    search_fields = ['name', 'level']

    # Orden por nivel (L1 primero)
    ordering = ['level']


# ------------------------------------------------------------------------------
# COLLABORATOR — Registro con configuración detallada
# ------------------------------------------------------------------------------
@admin.register(Collaborator)
class CollaboratorAdmin(admin.ModelAdmin):

    # Columnas visibles en la lista
    list_display = ['cupe', 'first_name', 'last_name', 'role', 'city', 'is_active']

    # Filtros en el panel derecho
    list_filter = ['is_active', 'role', 'city']

    # Búsqueda por estos campos
    search_fields = ['cupe', 'first_name', 'last_name', 'username', 'email']

    # Campos de solo lectura — no se pueden editar desde el panel
    readonly_fields = ['cupe', 'created_at', 'updated_at']

    # Orden: alfabético por apellido
    ordering = ['last_name', 'first_name']


# ------------------------------------------------------------------------------
# CLIENT — Registro con configuración detallada
#
# Campos actualizados según el nuevo modelo:
#   - document_number (antes document_num)
#   - next_payment_date (antes next_payment)
#   - registration_date y delivery_date son nuevos
# ------------------------------------------------------------------------------
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):

    # Columnas visibles en la lista — campos actualizados
    list_display = ['cupe', 'name', 'document_type', 'document_number', 'plan', 'status', 'next_payment_date', 'delivery_date']

    # Filtros por estado, plan y tipo de web
    list_filter = ['status', 'plan', 'web_type']

    # Búsqueda por estos campos — document_number actualizado
    search_fields = ['cupe', 'name', 'document_number', 'email']

    # Campos de solo lectura
    readonly_fields = ['cupe', 'created_at', 'updated_at']

    # Orden: los más recientes primero
    ordering = ['-created_at']


# ------------------------------------------------------------------------------
# WEBCATALOG — Catálogo de tipos de web
#
# Campos actualizados:
#   - base_price_rent (antes monthly_price)
#   - base_price_sale (antes sale_price)
#   - is_active es nuevo
# ------------------------------------------------------------------------------
@admin.register(WebCatalog)
class WebCatalogAdmin(admin.ModelAdmin):

    # Columnas visibles — nombres de campos actualizados
    list_display = ['name', 'base_price_rent', 'base_price_sale', 'is_active']

    # Filtro por is_active — útil para ver solo los disponibles
    list_filter = ['is_active']

    # Búsqueda por nombre
    search_fields = ['name']

    # Orden alfabético
    ordering = ['name']


# ------------------------------------------------------------------------------
# CUPELOG — Historial de cambios de CUPE
# Solo lectura — los logs nunca se editan manualmente.
# ------------------------------------------------------------------------------
@admin.register(CupeLog)
class CupeLogAdmin(admin.ModelAdmin):

    list_display = ['old_cupe', 'new_cupe', 'reason', 'authorized_by', 'changed_at']

    list_filter = ['reason']

    search_fields = ['old_cupe', 'new_cupe']

    readonly_fields = ['entity_type', 'entity_id', 'old_cupe', 'new_cupe', 'reason', 'observations', 'changed_by', 'authorized_by', 'changed_at']

    ordering = ['-changed_at']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

# ------------------------------------------------------------------------------
# WEBFEATURE — Funcionalidades adicionales
#
# Catálogo independiente de funcionalidades extra.
# Campos actualizados: extra_price e is_active (antes tenía web_type)
# ------------------------------------------------------------------------------
@admin.register(WebFeature)
class WebFeatureAdmin(admin.ModelAdmin):

    # Muestra nombre, precio extra y si está activa
    list_display = ['name', 'extra_price', 'is_active', 'created_at']

    # Filtro por is_active
    list_filter = ['is_active']

    # Búsqueda por nombre
    search_fields = ['name']

    # Orden alfabético
    ordering = ['name']


# ------------------------------------------------------------------------------
# CLIENTFEATURE — Funcionalidades contratadas por cada cliente
#
# Tabla intermedia cliente ↔ funcionalidades.
# Solo lectura desde el panel — se gestiona desde FastAPI.
# ------------------------------------------------------------------------------
@admin.register(ClientFeature)
class ClientFeatureAdmin(admin.ModelAdmin):

    # Muestra el cliente, la funcionalidad y cuándo se asignó
    list_display = ['client', 'feature', 'added_at']

    # Filtro por funcionalidad
    list_filter = ['feature']

    # Búsqueda por CUPE del cliente o nombre de la funcionalidad
    search_fields = ['client__cupe', 'client__name', 'feature__name']

    # Orden: los más recientes primero
    ordering = ['-added_at']

    # Los registros solo se crean desde FastAPI — no manualmente
    def has_add_permission(self, request):
        return False