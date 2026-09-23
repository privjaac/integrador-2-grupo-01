"""Configuración aislada para pruebas; nunca utiliza la base PostgreSQL real."""

import os

os.environ.setdefault('SECRET_KEY', 'elisa-test-key-only')
os.environ.setdefault('CORS_ALLOWED_ORIGINS', 'http://localhost:5173')

from .settings import *  # noqa: F403,F401

SECRET_KEY = 'elisa-test-key-only'
JWT_SECRET_KEY = SECRET_KEY
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
}
DATABASE_ROUTERS = []
