# ELISA — Technical State

## 1. Source of truth

- Repositorio canónico: `integrador-2-grupo-01`
- Rama técnica: `feature/seguridad-semana8`
- HEAD: `9eba1f5`
- Working tree al crear este documento: limpio
- `SOFTWARE`: copia histórica/complementaria; no usar como baseline de código.

## 2. Checkpoint Git

- `417be55 test(auth): add refresh and logout regression coverage`
- `f89ea7c fix(api): stabilize validation and web feature type associations`
- `9eba1f5 fix(frontend): stabilize API errors catalog and logout`

Baseline anterior: `ce293da feat(backend): implement ELISA API and session 13 security`

## 3. Arquitectura comprobada

```text
React / Vite
     ↓
Axios
     ↓
/api/*
     ↓
FastAPI
     ↓
Django ORM
     ↓
PostgreSQL
```

Django también se utiliza para modelos, migraciones, configuración y administración. No existe una capa `services` formal; los routers FastAPI acceden directamente al ORM.

## 4. Estado E2E

Clasificación: **E2E NÚCLEO ESTABLE**.

Se verificaron en ejecución real y sin mocks: React→FastAPI, FastAPI→Django ORM, Django ORM→PostgreSQL, login, `/users/me`, refresh, logout cliente, usuarios, roles, clientes, catálogo, features, CUPE, datasets del dashboard y CORS. Se utilizó PostgreSQL temporal y la BD temporal fue eliminada posteriormente.

## 5. Tests

Estado tras Estabilización 1:

- Backend: 29 tests, 29 PASS.
- Frontend: 5 tests del normalizador de errores, 5 PASS.
- Django check: PASS.
- FastAPI inicializa correctamente.
- OpenAPI genera correctamente.
- Frontend build: PASS.

Deuda conocida: lint con 10 errores y 9 warnings preexistentes; bundle principal aproximadamente 509 kB; `caniuse-lite` desactualizado. No tratarlos automáticamente como prioridad alta.

## 6. Módulos actuales

Implementados: autenticación/JWT, usuarios/colaboradores, roles, clientes, catálogo de tipos web, funcionalidades, asociación cliente-feature y CUPE directo + historial.

Parciales: pagos/cobranza, auditoría general, replicación y dashboard.

No implementados como integración real: WhatsApp Business API, SMTP, scheduler de notificaciones, backend completo de alertas/notificaciones y workflow CUPE solicitud/aprobación/rechazo/reversión.

## 7. Decisiones vigentes

### JWT

Se mantiene stateless. Logout elimina usuario/token/refresh/timers en frontend, pero no revoca inmediatamente el JWT emitido. No implementar blacklist salvo requisito explícito.

### WebFeature ↔ WebType

Relación M:N opcional entre `WebFeature` y `WebCatalog`:

- `web_type_ids=[]` → global;
- IDs presentes → aplicable a esos tipos;
- el filtro por tipo devuelve globales y asociadas al tipo.

Migración: `0007_webfeature_web_types.py`.

### API errors

Los errores frontend se normalizan siempre a `string`; los arrays Pydantic 422 no llegan directamente a React.

### Error Boundary

Pendiente como endurecimiento separado; no sustituye el manejo correcto de errores API.

## 8. Estado funcional relevante

CUPE actual:

```text
cambio directo autorizado
        ↓
persistencia del nuevo CUPE
        ↓
CupeLog
```

No existe aún solicitud→aprobación/rechazo→ejecución→reversión.

Dashboard: no tiene endpoint propio; agrega clientes y colaboradores en frontend. Las métricas de ingresos aún no equivalen a contabilidad/cobros reales.

Pagos: existen campos y cálculos en `Client`, pero no un libro/transacción de pagos completo.

## 9. Documentación vs implementación

La baseline documental previa tiene un alcance mayor: pagos/cobranza completos, alertas, WhatsApp, SMTP, scheduler, dashboard más completo, auditoría y workflow CUPE. No asumir que documentación antigua está implementada ni que describe correctamente el código actual.

## 10. Python / Java

Backend real: Python + FastAPI + Django. Existe una observación académica sobre Java/Spring, pero no una decisión aprobada de migración completa. Mantener contratos HTTP y dominio claros para permitir migración parcial o futura sin reescribir innecesariamente el frontend.

## 11. Rama main

`main` no está reconciliada con seguridad. Referencia conocida: `main` → `07a23e6`. Se encontró trabajo exclusivo allí, incluidos DDL, replicación PostgreSQL y database router/tests/scripts relacionados. No hacer merge automáticamente.

La siguiente auditoría debe comparar semánticamente `main` vs `feature/seguridad-semana8` y determinar qué conservar.

## 12. Pendientes principales

Orden general sujeto a revisión:

1. reconciliar `main` ↔ seguridad;
2. revisar modelo/BD consolidado;
3. arquitectura/modularidad;
4. seguridad final;
5. pagos;
6. workflow CUPE;
7. alertas/notificaciones;
8. WhatsApp/SMTP;
9. escalabilidad;
10. decisión Python↔Java;
11. deployment;
12. documentación académica final.

No convertir esta lista automáticamente en orden de implementación sin análisis.

## 13. Uso eficiente de Codex

- Preferir preguntas concretas.
- No repetir auditorías ya completadas.
- Leer este archivo primero.
- Ejecutar tests focalizados durante desarrollo.
- Ejecutar E2E completo sólo en checkpoints.
- Actualizar este archivo sólo cuando cambie una decisión o estado importante.
