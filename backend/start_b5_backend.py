"""Inicio local B5: fija el destino antes de importar o inicializar Django."""

from __future__ import annotations

import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
PASSFILE = Path(os.environ.get("APPDATA", "")) / "postgresql" / "pgpass.conf"
EXPECTED = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "elisa_b5_demo_20261028",
    "USER": "postgres",
    "HOST": "127.0.0.1",
    "PORT": "5433",
    "PASSWORD": "",
}


def main() -> int:
    if not PASSFILE.is_file():
        raise SystemExit("No se encontró pgpass.conf en el perfil actual de Windows.")

    # Set the complete target before importing Django; load_dotenv() must not
    # replace it with backend/.env values (which may point to port 5432).
    os.environ["DJANGO_SETTINGS_MODULE"] = "core.settings"
    os.environ["DB_NAME"] = EXPECTED["NAME"]
    os.environ["DB_USER"] = EXPECTED["USER"]
    os.environ["DB_PASSWORD"] = EXPECTED["PASSWORD"]
    os.environ["DB_MASTER_HOST"] = EXPECTED["HOST"]
    os.environ["DB_MASTER_PORT"] = EXPECTED["PORT"]
    os.environ["DB_REPLICA_ENABLED"] = "False"
    os.environ["PGPASSFILE"] = str(PASSFILE)

    sys.path.insert(0, str(BACKEND_DIR))
    import django

    django.setup()

    from django.conf import settings
    from django.db import connections

    configured = settings.DATABASES["default"]
    for key, expected in EXPECTED.items():
        if str(configured.get(key, "")) != expected:
            raise SystemExit(f"Configuración de base inesperada en {key}; backend detenido.")
    if settings.DB_REPLICA_ENABLED:
        raise SystemExit("La réplica no está permitida para el arranque local B5.")

    connection = connections["default"]
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_database(), current_setting('server_version'), "
            "inet_server_addr()::text, inet_server_port(), current_user"
        )
        identity = cursor.fetchone()
    expected_identity = (EXPECTED["NAME"], "18.6", 5433, EXPECTED["USER"])
    if (
        identity[0], identity[1], identity[3], identity[4]
    ) != expected_identity or identity[2].split("/")[0] != EXPECTED["HOST"]:
        raise SystemExit("La identidad SQL no coincide con PostgreSQL B5 autorizado; backend detenido.")

    print(
        "PostgreSQL confirmado: "
        f"{identity[0]} | {identity[2].split('/')[0]}:{identity[3]} | "
        f"{identity[1]} | usuario {identity[4]}"
    )
    if "--check-only" in sys.argv:
        connection.close()
        print("Comprobación de conexión completada; no se inició el servidor.")
        return 0

    import uvicorn

    uvicorn.run("api.main:app", host="127.0.0.1", port=8001, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
