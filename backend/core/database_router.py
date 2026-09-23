"""Enrutamiento de Django ORM para PostgreSQL Primary / Read Replica.

Las escrituras, migraciones y lecturas consistentes se atienden en `default`
(el maestro). Las lecturas ordinarias van a `replica` únicamente cuando está
habilitada. Así el backend puede activarse por entorno sin duplicar routers
FastAPI ni introducir credenciales en el código.
"""

from django.conf import settings


class PrimaryReplicaRouter:
    """Envía SELECT a la réplica y cualquier mutación al maestro."""

    def db_for_read(self, model, **hints):
        # Una instancia recién guardada conserva _state.db='default'; respetarlo
        # evita leer datos que todavía no alcanzaron la réplica (read-your-writes).
        instance = hints.get('instance')
        if instance is not None and instance._state.db == 'default':
            return 'default'
        if settings.DB_REPLICA_ENABLED:
            return 'replica'
        return 'default'

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        # Maestro y réplica son copias físicas del mismo clúster lógico.
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Las migraciones DDL se ejecutan una sola vez, en el maestro, y WAL
        # las transmite a la réplica. Nunca ejecutar migrate en el esclavo.
        return db == 'default'
