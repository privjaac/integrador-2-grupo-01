from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from core.db_router import PrimaryReplicaRouter


class PrimaryReplicaRouterTests(SimpleTestCase):
    @override_settings(DATABASES={"default": {}, "replica": {}})
    def test_routes_reads_to_replica_and_writes_to_primary(self):
        router = PrimaryReplicaRouter()

        self.assertEqual(router.db_for_read(object), "replica")
        self.assertEqual(router.db_for_write(object), "default")
        self.assertTrue(router.allow_migrate("default", "clients"))
        self.assertFalse(router.allow_migrate("replica", "clients"))

    @override_settings(DATABASES={"default": {}})
    def test_falls_back_to_primary_without_replica(self):
        self.assertEqual(PrimaryReplicaRouter().db_for_read(object), "default")

    def test_allows_relations_inside_primary_replica_pool(self):
        primary = SimpleNamespace(_state=SimpleNamespace(db="default"))
        replica = SimpleNamespace(_state=SimpleNamespace(db="replica"))

        self.assertTrue(PrimaryReplicaRouter().allow_relation(primary, replica))
