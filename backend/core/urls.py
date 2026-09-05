# ==============================================================================
# URLS.PY — Archivo central de rutas del proyecto ELISA
#
# Este archivo es el punto de entrada de todas las URLs.
# Cuando llega una petición HTTP, Django la lee y decide a dónde mandarla.
#
# En ELISA tenemos dos sistemas conviviendo:
#   - Django  → maneja /admin/ (panel de administración)
#   - FastAPI → maneja /api/  (todos los endpoints que consume React)
#
# Django y FastAPI son dos aplicaciones separadas, pero las unimos aquí
# para que corran juntas en el mismo servidor y puerto.
#
# ¿Cómo funciona la unión?
# Django tiene un sistema ASGI (interfaz para servidores async).
# FastAPI también es ASGI. Django puede "montar" otra app ASGI dentro suyo
# usando el paquete 'django-asgi-lifespan' o simplemente con el router de rutas.
# En este caso usamos WSGIMiddleware de Starlette para montar FastAPI dentro
# del sistema de URLs de Django de forma simple.
# ==============================================================================

from django.contrib import admin
from django.urls import path

# ------------------------------------------------------------------------------
# RUTAS DE DJANGO
# Solo maneja /admin/ — todo lo demás va a FastAPI
# ------------------------------------------------------------------------------

urlpatterns = [
    path('admin/', admin.site.urls),
]
