from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test.runner import DiscoverRunner


def validate_database_mapping(databases):
    """Only permit disposable SQLite memory databases for Django tests."""
    unsafe = []
    if not databases:
        unsafe.append('sin alias de base configurado')
    for alias, config in databases.items():
        if config.get('ENGINE') != 'django.db.backends.sqlite3':
            unsafe.append(f'{alias}: motor no aislado')
            continue
        if config.get('NAME') != ':memory:':
            unsafe.append(f'{alias}: la base SQLite no es en memoria')
            continue
        test_options = config.get('TEST') or {}
        if test_options.get('NAME') not in (None, ':memory:') or test_options.get('MIRROR'):
            unsafe.append(f'{alias}: destino de prueba no aislado')
    if unsafe:
        raise ImproperlyConfigured(
            'Pruebas bloqueadas antes de crear bases: se requiere SQLite en memoria '
            'en todos los alias. Para PostgreSQL use una validación de integración '
            'explícita, no el ejecutor Django que crea/elimina bases de prueba. '
            f'Alias no seguros: {", ".join(unsafe)}.'
        )


def validate_test_databases():
    """Fail closed before test discovery or setup can create a database."""
    validate_database_mapping(connections.databases)
    unsafe = []
    for alias in connections:
        connection = connections[alias]
        effective = connection.settings_dict
        configured = connections.databases[alias]
        validate_database_mapping({alias: effective})

        if (
            effective.get('ENGINE') != configured.get('ENGINE')
            or effective.get('NAME') != configured.get('NAME')
        ):
            unsafe.append(f'{alias}: configuración de conexión desactualizada')
            continue

    if unsafe:
        raise ImproperlyConfigured(
            'Pruebas bloqueadas antes de crear bases: la conexión ya inicializada '
            'no coincide con la configuración de prueba actual. '
            f'Alias no seguros: {", ".join(unsafe)}.'
        )


class SafeDiscoverRunner(DiscoverRunner):
    def run_tests(self, test_labels, **kwargs):
        validate_test_databases()
        return super().run_tests(test_labels, **kwargs)
