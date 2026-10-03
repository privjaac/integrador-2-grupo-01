# ELISA — guía breve de trabajo

## Proyecto

- ELISA es un ERP web interno.
- Repositorio canónico: `integrador-2-grupo-01`.
- `SOFTWARE` es histórico/complementario; no es fuente canónica de código.
- Stack: React/Vite/Axios, FastAPI, Django/Django ORM y PostgreSQL.

## Antes de modificar código

Leer `docs/ELISA_STATE.md`. No redescubrir lo confirmado allí salvo cambio de código, contradicción o verificación específica requerida.

## Reglas

- Mantener el alcance solicitado, evitar refactors no relacionados y justificar cambios de contrato API.
- Mantener compatibilidad frontend/backend y opciones futuras Python→Java.
- No introducir Repository/Service Pattern sólo por anticipación.
- Ejecutar tests focalizados; E2E completo sólo en checkpoints o cuando el cambio lo justifique.
- Usar PostgreSQL temporal para pruebas destructivas/E2E cuando sea posible y no escribir auditoría en la BD normal.
- No revelar secretos de `.env`.
- No hacer merge con `main` sin plan explícito de reconciliación.

## Git

- Rama técnica: `feature/seguridad-semana8`.
- Checkpoint estable: `9eba1f5`.
- No asumir que `main` contiene el trabajo más reciente.

## Decisiones actuales

- JWT stateless; no hay blacklist de tokens.
- `WebFeature ↔ WebCatalog` es M:N opcional; `web_type_ids=[]` significa global.
- Error Boundary está pendiente y no sustituye la normalización de errores.
- CUPE es cambio directo autorizado + historial; aún no existe workflow de aprobación/rechazo.
