# ==============================================================================
# SETTINGS.PY — Configuración central de Django para el proyecto ELISA
#
# Este archivo le dice a Django cómo comportarse: qué base de datos usar,
# qué apps están activas, qué URLs manejar, qué idioma/zona horaria usar, etc.
# Django lo lee automáticamente al arrancar. Nunca se llama manualmente.
# ==============================================================================

from pathlib import Path   # Para construir rutas de carpetas de forma segura
from dotenv import load_dotenv  # Para leer el archivo .env
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
SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-key-insegura')
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
# BASE DE DATOS — PostgreSQL
#
# Le decimos a Django que use PostgreSQL en lugar de SQLite (que es el default).
# Todos los valores vienen del .env para no hardcodear credenciales en el código.
#
# ENGINE: el conector de Django para PostgreSQL (usa psycopg2 internamente).
# NAME:   nombre de la base de datos → elisa_local_db
# USER:   usuario de PostgreSQL → elisa_user
# PASSWORD: contraseña → elisa_pass_local
# HOST:   dónde está el servidor de BD → localhost (en nuestra misma PC)
# PORT:   puerto de PostgreSQL → 5432 (el default)
# ------------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}


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
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')


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
JWT_SECRET_KEY = os.getenv('SECRET_KEY')
JWT_ALGORITHM = os.getenv('ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 30))
REFRESH_TOKEN_EXPIRE_HOURS = int(os.getenv('REFRESH_TOKEN_EXPIRE_HOURS', 24))


# ------------------------------------------------------------------------------
# ID AUTOMÁTICO POR DEFECTO
# Cuando Django crea una tabla sin especificar el tipo de ID,
# usa BigAutoField → un entero grande autoincremental (más seguro que el int normal).
# ------------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
