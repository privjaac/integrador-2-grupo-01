# ELISA

Sistema interno de ELOMUX para administrar colaboradores, roles, clientes, tipos de web, funcionalidades y cambios de CUPE. El frontend es React/Vite; el backend usa FastAPI, Django ORM y PostgreSQL.

## Iniciar el backend

Se necesita Python 3.13 y PostgreSQL. Desde `backend/`:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Completar `backend/.env` con una `SECRET_KEY` aleatoria y los datos de PostgreSQL. El archivo `.env` está ignorado por Git. Después:

```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py bootstrap_elisa --username admin --email admin@tu-dominio.com --document-number TU_DOCUMENTO
.\venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8001
```

El comando inicial solicita la contraseña del Superadmin sin imprimirla. Crea los cinco niveles L1–L5; solo debe ejecutarse una vez. La API queda en `http://localhost:8001/api/` y su documentación en `http://localhost:8001/docs`.

## Conectar el frontend

Desde `frontend/`, instalar dependencias con `npm install`. En `frontend/.env`, definir `VITE_USE_MOCK=false` y `VITE_API_BASE_URL=http://localhost:8001`. Ejecutar `npm run dev`. En modo mock, los cambios son temporales y no llegan a PostgreSQL.

Los niveles L1–L5 son fijos. El Superadmin puede editar el nombre y la descripción de L2–L5. Las reglas de acceso siguen ligadas a cada nivel; crear niveles adicionales requiere un modelo de permisos dinámico.

## Pruebas

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe manage.py test clients --settings=core.test_settings
```

Las pruebas usan SQLite en memoria y no tocan PostgreSQL. La conexión a PostgreSQL se verificó localmente; aún faltan pruebas de integración y de despliegue en el entorno del equipo.

## Seguridad de la sesión 13

El registro y cambio de contraseña guardan únicamente un hash bcrypt. Las rutas privadas validan el JWT Bearer y los permisos del rol. Los DTO de escritura rechazan etiquetas HTML, las respuestas JSON codifican caracteres peligrosos y CORS acepta solo los orígenes configurados en `backend/.env`. Las búsquedas usan filtros del ORM, sin concatenar SQL.

Las verificaciones automatizadas de hash, XSS, CORS, autenticación, permisos y búsqueda contra inyección SQL están en `backend/clients/tests.py`. El informe para la entrega está en `output/pdf/elisa_evidencia_sesion_13.pdf` y puede regenerarse con `backend/scripts/build_session13_report.py` después de instalar `requirements-dev.txt`. No publiques capturas que muestren contraseñas, hashes completos o JWT.

