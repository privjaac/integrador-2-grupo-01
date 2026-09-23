"""Return Django ORM connections to psycopg's pool after FastAPI work."""

from functools import wraps
from inspect import iscoroutinefunction

from django.db import connections
from fastapi import APIRouter as FastAPIRouter
from fastapi.routing import APIRoute


class DatabaseCleanupRoute(APIRoute):
    def __init__(self, path, endpoint, **kwargs):
        if iscoroutinefunction(endpoint):
            @wraps(endpoint)
            async def wrapped(*args, **route_kwargs):
                try:
                    return await endpoint(*args, **route_kwargs)
                finally:
                    connections.close_all()
        else:
            @wraps(endpoint)
            def wrapped(*args, **route_kwargs):
                try:
                    return endpoint(*args, **route_kwargs)
                finally:
                    connections.close_all()

        super().__init__(path, wrapped, **kwargs)


class APIRouter(FastAPIRouter):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('route_class', DatabaseCleanupRoute)
        super().__init__(*args, **kwargs)
