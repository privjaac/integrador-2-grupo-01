# APF3 — Sesión 22: CI y control de cambios (ELISA)

## Fuente y alcance
Ficha original: «Semana 11, Sesión 22 — Control de Cambios e Integración Continua».
Este cambio **solo propone** CI y una plantilla RFC sobre la base técnica de `release/apf2`.
No modifica aplicación, esquema de datos, credenciales, servicios o despliegues.

## Pipeline
Archivo: `.github/workflows/ci-elisa-apf3.yml`.
- Disparador: push y pull request hacia `main` o `release/apf2`.
- Backend: Python 3.13; instalación de `backend/requirements.txt`; pruebas Django
  mediante `core.test_settings` con SQLite en memoria. No requiere secretos.
- Frontend: Node.js 22; `npm ci`, `npm run test:error-message` y `npm run build`.
- Sin deploy automático, sin modificación de BD ni credenciales.
- `npm run lint` no es bloqueo de CI en esta intervención porque hay deuda histórica
  reportada; su integración debe acordarse tras corregir los errores existentes.

La creación del YAML **no demuestra** una ejecución exitosa: enlazar run, commit y
captura de los jobs antes de presentar el entregable.

## RFC y clasificación
Plantilla reutilizable en `.github/ISSUE_TEMPLATE/RFC_solicitud_cambio.md`.
Clasificar cada RFC antes de aprobar: estándar (repetitivo y preautorizado),
normal (revisión y autorización específica) o emergencia (urgente, revisión
acelerada y regularización posterior). No atribuir aprobaciones por defecto.
La incorporación inicial de CI es un **cambio normal propuesto**, no de emergencia.

## Reversión (Backout Plan) del cambio de CI
1. **Antes de integrar:** si fallan los jobs, no fusionar el PR; corregir en la
   rama de trabajo o cerrar el PR sin integrar.
2. **Si el CI integrado bloquea indebidamente:** registrar incidente/RFC y
   revertir el commit concreto del workflow mediante un PR revisado. Conservar
   YAML, logs y referencias para trazabilidad; no forzar historial de Git.
3. **Si existe un despliegue APF3 independiente:** antes de desplegar, registrar
   el SHA de aplicación que funciona y las migraciones asociadas. Una reversión
   de aplicación/datos debe tener un plan específico, validación y autorización.
   Este documento **no autoriza** cambios ni rollback en Render o PostgreSQL.
4. Verificar tras la reversión los controles CI y el comportamiento que cambió,
   anotar responsables, resultado y fecha en el RFC.

## Verificaciones manuales pendientes
- Confirmar en GitHub Settings → Branches / Rulesets protección real de la rama
  principal, revisores y checks requeridos; la disponibilidad de GitHub no los prueba.
- Confirmar SoD de accesos/revisiones por el equipo, sin publicar credenciales.
- Vincular RFC con PR, SHAs y captura auténtica de GitHub Actions.
- El historial conocido de `main` y `release/apf2` es divergente; la
  existencia de disparadores para ambas ramas no autoriza un merge.
