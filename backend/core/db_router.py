"""Enrutamiento de ORM para una topología PostgreSQL primary/read replica."""

from django.conf import settings


class PrimaryReplicaRouter:
    """Envía escrituras y migraciones al primario, y lecturas a la réplica."""

    primary_alias = "default"
    replica_alias = "replica"

    def _replica_enabled(self):
        return self.replica_alias in settings.DATABASES

    def db_for_read(self, model, **hints):
        if self._replica_enabled():
            return self.replica_alias
        return self.primary_alias

    def db_for_write(self, model, **hints):
        return self.primary_alias

    def allow_relation(self, obj1, obj2, **hints):
        database_pool = {self.primary_alias, self.replica_alias}
        if obj1._state.db in database_pool and obj2._state.db in database_pool:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # La réplica física recibe el esquema mediante WAL; nunca se migra allí.
        return db == self.primary_alias
