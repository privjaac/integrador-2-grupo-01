# ELISA — Estructura Lógica de Información y Servicios Administrativos

## De qué se trata

Elomux es una empresa que desarrolla sitios web para otros negocios. Hoy la información de sus clientes, colaboradores y cobros está repartida entre hojas de cálculo, chats y lo que cada persona recuerda del caso que lleva. Eso genera errores, plata que se pierde de vista, demoras para saber en qué situación está cada cliente y ningún registro claro de quién cambió qué y por qué.

ELISA junta todo eso en un solo sistema: quién es cada cliente, qué servicio le vendimos, cuánto y cuándo debe pagar, qué colaborador lo atiende, con qué permisos trabaja cada persona del equipo, y un registro de cualquier cambio sensible para poder revisarlo después. El objetivo es que la empresa deje de operar "a memoria" y tenga un solo lugar confiable donde mirar.

## Cómo está organizado

El sistema tiene dos partes que se hablan entre sí:

- **Una pantalla web** donde el equipo de Elomux trabaja el día a día: registra clientes, da de alta colaboradores, administra el catálogo de servicios y revisa el dashboard del negocio.
- **Un motor detrás** que guarda toda la información, aplica las reglas del negocio (por ejemplo, calcular cuándo vence un pago, o que un colaborador no pueda ver ni tocar lo que no le corresponde según su rol) y deja constancia de los cambios importantes.

Las dos partes viven en este mismo repositorio, en carpetas separadas (`frontend/` y `backend/`), y se despliegan de forma independiente.

## Por dentro (sección técnica)

**Frontend** (`frontend/`) — React 19 + Vite, React Router para la navegación, Axios para hablar con la API, Tailwind CSS para los estilos.

**Backend** (`backend/`) — Python. Usa Django y FastAPI juntos, pero no como dos backends separados: Django solo define los modelos de datos, corre las migraciones y da acceso al panel `/admin`; toda la API que consume el frontend (login, clientes, colaboradores, roles, catálogo, CUPE) la sirve FastAPI, que al arrancar inicializa Django por debajo para poder usar esos mismos modelos. En una frase: Django guarda y ordena los datos, FastAPI es la puerta por la que entra y sale la información.

**Base de datos** — PostgreSQL, con el ORM propio de Django (no se usa SQLAlchemy ni Alembic en ningún punto del backend; las migraciones se manejan con `manage.py`).

Estructura de carpetas:

```
backend/
  core/         configuracion de Django (settings, urls, asgi/wsgi)
  clients/      modelos, migraciones y admin de Django
  api/
    main.py     app de FastAPI y registro de routers
    routers/    endpoints por modulo (auth, clients, users, roles, catalogo, cupe)
    schemas/    esquemas Pydantic de request y response
frontend/
  src/
    pages/      vistas por modulo (auth, clients, users, roles, catalog, dashboard)
    components/ componentes reutilizables (ui/, layout/)
    context/    contexto de autenticacion
    hooks/      hooks compartidos
    mocks/      datos de ejemplo para desarrollar sin backend
```

## Levantar el proyecto en local

Backend:
```
cd backend
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
python manage.py migrate
uvicorn api.main:app --reload --port 8001
```
Necesita un archivo `.env` propio, no versionado, con `SECRET_KEY`, los datos de conexión a PostgreSQL y `CORS_ALLOWED_ORIGINS`.

Frontend:
```
cd frontend
npm install
npm run dev
```
También necesita su propio `.env` con `VITE_API_URL` (y `VITE_USE_MOCK` para trabajar contra los datos de ejemplo de `src/mocks` sin levantar el backend).

Ningún `.env` se sube al repositorio, ni siquiera como ejemplo. Revisar `.gitignore` antes de hacer commit.

## Flujo de trabajo del equipo

- `main` se mantiene estable. Los cambios entran por Pull Request, nunca directo.
- Para una HU nueva del Project: rama `feature/HU<numero>` (ej. `feature/HU23`, usando el número del issue).
- Para un ajuste sobre algo que ya existe: rama `hotfix/<palabra-corta>` (ej. `hotfix/login-token`).
- Todo Pull Request necesita al menos una aprobación antes de mergearse a `main`.
- El seguimiento de las historias de usuario está en el Project del repositorio, organizado por módulo y por sprint.

## Tecnologías utilizadas

**Frontend**
- React 19.2.4
- Vite 8.0.0
- React Router 7.13.1
- Axios 1.13.6
- Tailwind CSS 4.2.1
- ESLint

**Backend**
- Python
- Django 6.0.2 - FastAPI 0.133.1
- Uvicorn 0.41.0
- Pydantic 2.12.5
- python-jose (JWT)
- Passlib / Bcrypt (hash de contraseñas)

**Base de datos y persistencia**
- PostgreSQL
- ORM de Django (migraciones con `manage.py`)
