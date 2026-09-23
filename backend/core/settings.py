# ==============================================================================
# SETTINGS.PY — Configuración central de Django para el proyecto ELISA
#
# Este archivo le dice a Django cómo comportarse: qué base de datos usar,
# qué apps están activas, qué URLs manejar, qué idioma/zona horaria usar, etc.
# Django lo lee automáticamente al arrancar. Nunca se llama manualmente.
# ==============================================================================

from pathlib import Path   # Para construir rutas de carpetas de forma segura
from dotenv import load_dotenv  # Para leer el archivo .env
from django.core.exceptions import ImproperlyConfigured
import os  # Para acceder a las variables de entorno del sistema


# ------------------------------------------------------------------------------
# RUTAS BASE
# BASE_DIR apunta a la carpeta /backend (donde está manage.py).
# Se usa como punto de partida para encontrar otros archivos del proyecto.
# Ejemplo: BASE_DIR / '.env' → /backend/.env
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------------------
# CARGAR EL ARCHIVO .env
# Sin esto, os.getenv() no encontraría las variables que definiste en .env.
# load_dotenv() las carga en memoria al iniciar Django.
# ------------------------------------------------------------------------------
load_dotenv(BASE_DIR / '.env')


# ------------------------------------------------------------------------------
# SEGURIDAD BÁSICA
#
# SECRET_KEY: Clave interna que Django usa para firmar cookies, tokens CSRF, etc.
#   - En local usamos la del .env (simple).
#   - En producción debe ser larga, aleatoria y secreta.
#   - El 'fallback-key-insegura' es solo por si alguien olvida el .env en local.
#
# DEBUG: En True, Django muestra errores detallados en el navegador.
#   - Siempre False en producción (expone código interno).
#   - El .env dice DEBUG=True → esta línea lo convierte de string a booleano.
#
# ALLOWED_HOSTS: Lista de dominios desde los que se puede acceder al backend.
#   - En local: localhost y 127.0.0.1.
#   - En producción se agrega: elisa.elomux.com
#   - El .env lo guarda como string separado por comas → .split(',') lo convierte a lista.
# ------------------------------------------------------------------------------
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY es obligatoria; configúrala en backend/.env.')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')


# ------------------------------------------------------------------------------
# APPS INSTALADAS
# Django necesita saber qué aplicaciones están activas en el proyecto.
# Las primeras 6 son de Django mismo (admin, autenticación, sesiones, etc).
# 'clients' es nuestra app propia — la carpeta /backend/clients/ que creamos.
# Si no la registramos aquí, Django ignora sus modelos y no crea sus tablas.
# ------------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',        # Panel de administración en /admin/
    'django.contrib.auth',         # Sistema de usuarios y permisos de Django
    'django.contrib.contenttypes', # Necesario para relaciones entre modelos
    'django.contrib.sessions',     # Manejo de sesiones en base de datos
    'django.contrib.messages',     # Sistema de mensajes flash (alertas)
    'django.contrib.staticfiles',  # Servir archivos estáticos (CSS, JS, imágenes)
    'clients',                     # Nuestra app: modelos de clientes y colaboradores
]


# ------------------------------------------------------------------------------
# MIDDLEWARE
# Son capas que procesan cada request HTTP antes de llegar a la vista
# y cada response antes de salir. Se ejecutan en orden, de arriba a abajo.
# No los tocamos por ahora — son los estándar de Django.
# ------------------------------------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ------------------------------------------------------------------------------
# URLS RAÍZ
# Le dice a Django dónde está el archivo principal de rutas (urls.py).
# 'core.urls' significa: la carpeta core/, el archivo urls.py.
# ------------------------------------------------------------------------------
ROOT_URLCONF = 'core.urls'


# ------------------------------------------------------------------------------
# TEMPLATES (plantillas HTML)
# Django puede renderizar HTML con su motor de plantillas.
# En ELISA no usamos templates de Django (React maneja el frontend),
# pero esta config es necesaria para que el panel /admin/ funcione.
# ------------------------------------------------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# ------------------------------------------------------------------------------
# WSGI
# Punto de entrada para servidores de producción (como Passenger en cPanel).
# Passenger busca este archivo para saber cómo arrancar Django.
# En local usamos uvicorn, pero esta config igual debe estar.
# ------------------------------------------------------------------------------
WSGI_APPLICATION = 'core.wsgi.application'


# ------------------------------------------------------------------------------
# BASE DE DATOS — PostgreSQL con maestro y réplica de lectura
#
# `default` es siempre el nodo maestro: Django y las migraciones escriben allí.
# `replica` representa la Read Replica. El router de `core.database_router`
# envía los SELECT a ese alias solo cuando DB_REPLICA_ENABLED=True.
#
# La auditoría inicial detectó PostgreSQL y Django ORM, por eso esta separación
# se implementa en DATABASES (sin cambiar los routers FastAPI existentes).
# El pool es nativo de Django + psycopg 3; cada alias tiene su propio pool.
# ------------------------------------------------------------------------------
def _env_int(name, default, minimum=0):
    """Lee enteros de entorno y falla temprano ante una configuración inválida."""
    try:
        value = int(os.getenv(name, default))
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(f'{name} debe ser un entero.') from exc
    if value < minimum:
        raise ImproperlyConfigured(f'{name} debe ser mayor o igual a {minimum}.')
    return value


DB_REPLICA_ENABLED = os.getenv('DB_REPLICA_ENABLED', 'False').lower() == 'true'
DB_POOL_TIMEOUT = _env_int('DB_POOL_TIMEOUT', 10, 1)


def _pool_options(prefix, default_min_size, default_max_size):
    """Construye el pool psycopg para un alias de base de datos."""
    min_size = _env_int(f'{prefix}_POOL_MIN_SIZE', default_min_size, 0)
    max_size = _env_int(f'{prefix}_POOL_MAX_SIZE', default_max_size, 1)
    if min_size > max_size:
        raise ImproperlyConfigured(
            f'{prefix}_POOL_MIN_SIZE no puede superar {prefix}_POOL_MAX_SIZE.'
        )
    return {
        'pool': {
            'min_size': min_size,
            'max_size': max_size,
            'timeout': DB_POOL_TIMEOUT,
        },
    }


def _postgres_database(host, port, pool_prefix, min_size, max_size):
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': host,
        'PORT': port,
        # ASGI no debe conservar conexiones por request: psycopg administra el pool.
        'CONN_MAX_AGE': 0,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': _pool_options(pool_prefix, min_size, max_size),
    }


DB_MASTER_HOST = os.getenv('DB_MASTER_HOST', os.getenv('DB_HOST', 'localhost'))
DB_MASTER_PORT = os.getenv('DB_MASTER_PORT', os.getenv('DB_PORT', '5432'))
DB_REPLICA_HOST = os.getenv('DB_REPLICA_HOST', '')
DB_REPLICA_PORT = os.getenv('DB_REPLICA_PORT', DB_MASTER_PORT)

if DB_REPLICA_ENABLED and not DB_REPLICA_HOST:
    raise ImproperlyConfigured(
        'DB_REPLICA_HOST es obligatorio cuando DB_REPLICA_ENABLED=True.'
    )

DATABASES = {
    # Alias obligatorio de Django: canal exclusivo de escritura (maestro).
    'default': _postgres_database(
        DB_MASTER_HOST, DB_MASTER_PORT, 'DB_WRITE', 1, 5
    ),
    # El alias se declara también en local para mantener una configuración uniforme.
    # Con la réplica desactivada, el router no lo utiliza.
    'replica': _postgres_database(
        DB_REPLICA_HOST or DB_MASTER_HOST, DB_REPLICA_PORT, 'DB_READ', 2, 10
    ),
}

DATABASE_ROUTERS = ['core.database_router.PrimaryReplicaRouter']


# ------------------------------------------------------------------------------
# VALIDACIÓN DE CONTRASEÑAS
# Reglas que aplica Django cuando alguien crea o cambia una contraseña
# a través del panel admin o del sistema de auth de Django.
# FastAPI tiene su propio manejo de contraseñas con bcrypt (lo veremos después).
# ------------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ------------------------------------------------------------------------------
# IDIOMA Y ZONA HORARIA
#
# LANGUAGE_CODE: Django muestra el panel admin en español de Perú.
# TIME_ZONE: Todas las fechas y horas se guardan en hora de Lima (UTC-5).
# USE_TZ: True → Django guarda fechas en UTC internamente y convierte al mostrar.
#   Esto es importante para no tener problemas con cambios de horario.
# ------------------------------------------------------------------------------
LANGUAGE_CODE = 'es-pe'
TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True


# ------------------------------------------------------------------------------
# ARCHIVOS ESTÁTICOS
# URL desde donde se sirven CSS, JS e imágenes del panel admin.
# En producción, Apache/cPanel los sirve directamente.
# ------------------------------------------------------------------------------
STATIC_URL = 'static/'


# ------------------------------------------------------------------------------
# CORS — Cross-Origin Resource Sharing
#
# El navegador, por seguridad, bloquea requests entre dominios diferentes.
# React corre en localhost:5173 y el backend en localhost:8000 → dominios distintos.
# CORS_ALLOWED_ORIGINS le dice al backend qué orígenes puede aceptar.
#
# En local: http://localhost:5173 y http://127.0.0.1:5173 (el dev de React con Vite).
# En producción se cambia a: https://elisa.elomux.com
#
# Nota: corsheaders se agrega más adelante cuando instalemos django-cors-headers.
# Por ahora dejamos la variable lista para cuando la necesitemos.
# ------------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
    if origin.strip()
]
if '*' in CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured('CORS_ALLOWED_ORIGINS requiere orígenes explícitos, no *.')


# ------------------------------------------------------------------------------
# CONFIGURACIÓN JWT — JSON Web Tokens
#
# Estas variables las leerá FastAPI (desde api/main.py y api/routers/auth.py)
# para crear y validar los tokens de sesión.
#
# JWT_SECRET_KEY:  La misma SECRET_KEY del .env — firma los tokens.
# JWT_ALGORITHM:   HS256 → algoritmo de firma (estándar para JWT).
# ACCESS_TOKEN_EXPIRE_MINUTES:  El token de acceso dura 30 minutos.
#   Se renueva con cada acción del usuario (el frontend lo gestiona).
# REFRESH_TOKEN_EXPIRE_HOURS: El token de refresco dura 24 horas.
#   Si el usuario no hace nada en 24h, cierra sesión automáticamente.
# ------------------------------------------------------------------------------
JWT_SECRET_KEY = SECRET_KEY
JWT_ALGORITHM = os.getenv('ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 30))
REFRESH_TOKEN_EXPIRE_HOURS = int(os.getenv('REFRESH_TOKEN_EXPIRE_HOURS', 24))


# ------------------------------------------------------------------------------
# ID AUTOMÁTICO POR DEFECTO
# Cuando Django crea una tabla sin especificar el tipo de ID,
# usa BigAutoField → un entero grande autoincremental (más seguro que el int normal).
# ------------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
