# ==============================================================================
# MAIN.PY — Punto de entrada de FastAPI
#
# Este archivo crea la aplicación FastAPI y registra todos los routers.
# Un router es un grupo de endpoints relacionados — por ejemplo, todos
# los endpoints de clientes están en routers/clients.py
#
# Cuando uvicorn arranca, busca este archivo y la variable 'app' dentro.
# Comando: uvicorn api.main:app --reload --port 8001
#          significa: en api/main.py, usa la variable 'app'
#
# FastAPI genera documentación automática en:
#   http://localhost:8001/docs     → interfaz visual para probar endpoints
#   http://localhost:8001/redoc    → documentación más formal
# ==============================================================================

import django
import os

# ------------------------------------------------------------------------------
# INICIALIZAR DJANGO ANTES QUE TODO
#
# FastAPI necesita que Django esté inicializado para poder usar los modelos
# (Client, Collaborator, etc.) desde los routers.
#
# Si no hacemos esto, cuando un router intente hacer Client.objects.all()
# Django lanzará un error porque no sabe que fue configurado.
#
# DJANGO_SETTINGS_MODULE le dice a Django dónde está su settings.py
# 'core.settings' significa: carpeta core/, archivo settings.py
# ------------------------------------------------------------------------------
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from django.conf import settings

# ------------------------------------------------------------------------------
# IMPORTAR TODOS LOS ROUTERS
#
# Cada router maneja un grupo de endpoints relacionados.
# Los nuevos routers client_features y cupe_log se agregan aquí.
# ------------------------------------------------------------------------------
from api.routers import (
    auth,
    clients,
    users,
    roles,
    web_types,
    web_features,
    client_features,
    cupe_log,
)


# ------------------------------------------------------------------------------
# SEGURIDAD — HTTPBearer
#
# HTTPBearer le dice a FastAPI que esta API usa tokens Bearer.
# Habilita el botón 🔒 Authorize en /docs para pegar el token
# una sola vez y que todos los endpoints lo usen automáticamente.
# ------------------------------------------------------------------------------
security = HTTPBearer()


# ------------------------------------------------------------------------------
# CREAR LA APP FASTAPI
#
# title y description aparecen en la documentación automática /docs
# swagger_ui_parameters → persistAuthorization mantiene el token
# aunque recargues /docs
# ------------------------------------------------------------------------------
app = FastAPI(
    title='ELISA API',
    description='API del sistema ERP ELISA — Elomux',
    version='1.0.0',
    docs_url='/docs',
    redoc_url='/redoc',
    swagger_ui_parameters={"persistAuthorization": True},
)


# ------------------------------------------------------------------------------
# CORS MIDDLEWARE
#
# Le dice a FastAPI qué orígenes (dominios) pueden hacer peticiones a la API.
# Sin esto, React en localhost:5173 no podría hablar con el backend.
#
# allow_credentials=True  → permite enviar cookies y headers de autorización
# allow_methods=['*']     → acepta GET, POST, PUT, DELETE, etc.
# allow_headers=['*']     → acepta cualquier header HTTP
# ------------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


# ------------------------------------------------------------------------------
# REGISTRAR ROUTERS
#
# Cada router agrupa los endpoints de un módulo.
# prefix='/clients' → todos los endpoints empiezan con /clients
# tags=['Clientes']  → agrupa los endpoints en /docs
#
# URL completa: http://localhost:8001/auth/login
#               http://localhost:8001/clients/
# ------------------------------------------------------------------------------
app.include_router(
    auth.router,
    prefix='/auth',
    tags=['Autenticación']
)

app.include_router(
    clients.router,
    prefix='/clients',
    tags=['Clientes']
)

app.include_router(
    users.router,
    prefix='/users',
    tags=['Colaboradores']
)

app.include_router(
    roles.router,
    prefix='/roles',
    tags=['Roles']
)

app.include_router(
    web_types.router,
    prefix='/web-types',
    tags=['Tipos de Web']
)

app.include_router(
    web_features.router,
    prefix='/web-features',
    tags=['Funcionalidades']
)

app.include_router(
    client_features.router,
    prefix='/client-features',
    tags=['Funcionalidades de Clientes']
)

app.include_router(
    cupe_log.router,
    prefix='/cupe-log',
    tags=['Historial CUPE']
)


# ------------------------------------------------------------------------------
# ENDPOINT RAÍZ — Health check
#
# Endpoint simple para verificar que la API está corriendo.
# Útil para que el servidor sepa si el backend está vivo.
#
# GET http://localhost:8001/
# Respuesta: { "status": "ok", "message": "ELISA API corriendo" }
# ------------------------------------------------------------------------------
@app.get('/')
def root():
    return {
        'status': 'ok',
        'message': 'ELISA API corriendo',
        'version': '1.0.0'
    }