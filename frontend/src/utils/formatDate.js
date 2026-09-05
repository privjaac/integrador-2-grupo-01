// ==============================================================================
// FORMATDATE.JS — Funciones utilitarias para formateo de fechas
//
// Responsabilidad: centraliza TODA la lógica de formateo de fechas del sistema.
//   Evita que cada componente implemente su propio formato de fecha,
//   garantizando consistencia visual en toda la aplicación.
//
// Patrón: Utility Module — funciones puras sin estado ni efectos secundarios.
//   Entrada → transformación → salida. Fáciles de testear y reutilizar.
//
// Zona horaria: Perú (America/Lima, UTC-5).
//   Todas las fechas se muestran en hora peruana independientemente
//   de la zona horaria del servidor o del navegador del usuario.
//
// Seguridad:
//   Todas las funciones validan su input antes de procesarlo.
//   Si reciben un valor inválido, retornan un string seguro ('—')
//   en lugar de lanzar un error que rompa la UI.
//
// Uso en cualquier componente:
//   import { formatDate, formatDateTime, formatDateRelative } from '../../utils/formatDate'
//
//   formatDate('2026-03-15')           → '15/03/2026'
//   formatDateTime('2026-03-15T10:30') → '15/03/2026, 10:30'
//   formatDateRelative('2026-03-10')   → 'hace 5 días'
//
// NOTA PARA EL EQUIPO:
//   Nunca formatear fechas directamente en los componentes.
//   Siempre usar las funciones de este archivo.
// ==============================================================================

// ------------------------------------------------------------------------------
// SECCIÓN 1 — CONSTANTES DE CONFIGURACIÓN
//
// Centralizadas aquí para facilitar cambios futuros.
// Si el sistema se expande a otros países, solo se modifica aquí.
// ------------------------------------------------------------------------------

// Zona horaria oficial del sistema — Perú
const TIMEZONE = "America/Lima";

// Locale para formateo de texto — español de Perú
const LOCALE = "es-PE";

// ------------------------------------------------------------------------------
// SECCIÓN 2 — FUNCIÓN AUXILIAR INTERNA
//
// Convierte cualquier tipo de input de fecha en un objeto Date válido.
// Se usa internamente por todas las funciones públicas del módulo.
//
// Parámetros:
//   value (string|Date|number) → la fecha en cualquier formato
//
// Retorna:
//   Date válido, o null si el input es inválido
// ------------------------------------------------------------------------------

function parseDate(value) {
  // Si el valor es nulo, undefined o string vacío, retorna null
  if (!value) return null;

  // Si ya es un objeto Date válido, lo retorna directamente
  if (value instanceof Date) {
    return isNaN(value.getTime()) ? null : value;
  }

  // Si es string o número, intenta convertirlo a Date
  const parsed = new Date(value);

  // Verifica que la conversión resultó en una fecha válida
  // isNaN(date.getTime()) devuelve true si la fecha es inválida
  return isNaN(parsed.getTime()) ? null : parsed;
}

// ==============================================================================
// SECCIÓN 3 — FUNCIONES PÚBLICAS DE FORMATEO
// ==============================================================================

// ------------------------------------------------------------------------------
// formatDate — Formatea una fecha al formato dd/mm/aaaa
//
// Es el formato estándar de fecha en ELISA para mostrar fechas
// simples como fechas de pago, vencimiento y registro.
//
// Parámetros:
//   value (string|Date|number) → la fecha a formatear
//
// Retorna:
//   string → '15/03/2026'
//   '—'    → si el valor es inválido o nulo
//
// Ejemplos:
//   formatDate('2026-03-15')        → '15/03/2026'
//   formatDate('2026-03-15T10:30')  → '15/03/2026'
//   formatDate(null)                → '—'
//   formatDate('fecha-invalida')    → '—'
// ------------------------------------------------------------------------------

export function formatDate(value) {
  const date = parseDate(value);

  // Si la fecha es inválida, retorna el placeholder de dato vacío
  if (!date) return "—";

  return date.toLocaleDateString(LOCALE, {
    day: "2-digit", // día con cero a la izquierda: 01, 15, 31
    month: "2-digit", // mes con cero a la izquierda: 01, 03, 12
    year: "numeric", // año completo: 2026
    timeZone: TIMEZONE, // siempre en hora peruana
  });
}

// ------------------------------------------------------------------------------
// formatDateTime — Formatea fecha y hora al formato dd/mm/aaaa, hh:mm
//
// Usado para mostrar timestamps como fechas de creación,
// modificación y logs del sistema.
//
// Parámetros:
//   value (string|Date|number) → la fecha y hora a formatear
//
// Retorna:
//   string → '15/03/2026, 10:30'
//   '—'    → si el valor es inválido o nulo
//
// Ejemplos:
//   formatDateTime('2026-03-15T15:30:00Z') → '15/03/2026, 10:30'  (UTC-5)
//   formatDateTime(null)                   → '—'
// ------------------------------------------------------------------------------

export function formatDateTime(value) {
  const date = parseDate(value);

  if (!date) return "—";

  return date.toLocaleString(LOCALE, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false, // formato 24 horas (10:30, no 10:30 AM)
    timeZone: TIMEZONE,
  });
}

// ------------------------------------------------------------------------------
// formatDateShort — Formatea fecha en formato corto: dd mmm aaaa
//
// Usado en tablas donde el espacio es limitado pero queremos
// que la fecha sea legible sin ambigüedad.
//
// Parámetros:
//   value (string|Date|number) → la fecha a formatear
//
// Retorna:
//   string → '15 mar 2026'
//   '—'    → si el valor es inválido o nulo
//
// Ejemplos:
//   formatDateShort('2026-03-15') → '15 mar 2026'
//   formatDateShort('2026-12-01') → '01 dic 2026'
// ------------------------------------------------------------------------------

export function formatDateShort(value) {
  const date = parseDate(value);

  if (!date) return "—";

  return date.toLocaleDateString(LOCALE, {
    day: "2-digit",
    month: "short", // nombre corto del mes: ene, feb, mar...
    year: "numeric",
    timeZone: TIMEZONE,
  });
}

// ------------------------------------------------------------------------------
// formatDateRelative — Formatea la fecha de forma relativa al día de hoy
//
// Usado para mostrar qué tan reciente o lejana es una fecha,
// como 'hace 3 días', 'en 5 días', 'hoy', 'ayer'.
// Útil para mostrar fechas de próximo pago de forma amigable.
//
// Parámetros:
//   value (string|Date|number) → la fecha a comparar con hoy
//
// Retorna:
//   string → 'hoy', 'ayer', 'mañana', 'hace 5 días', 'en 10 días'
//   '—'    → si el valor es inválido o nulo
//
// Ejemplos:
//   formatDateRelative(hoy)         → 'hoy'
//   formatDateRelative(ayer)        → 'ayer'
//   formatDateRelative(hace 5 días) → 'hace 5 días'
//   formatDateRelative(en 10 días)  → 'en 10 días'
// ------------------------------------------------------------------------------

export function formatDateRelative(value) {
  const date = parseDate(value);

  if (!date) return "—";

  // Intl.RelativeTimeFormat formatea tiempos relativos en español
  const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });

  // Calcula la diferencia en días entre la fecha y hoy
  // Math.round para evitar errores por cambios de horario
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

  // Decide la unidad de tiempo más apropiada según la diferencia
  if (Math.abs(diffDays) < 1) return rtf.format(0, "day"); // hoy
  if (Math.abs(diffDays) < 7) return rtf.format(diffDays, "day"); // días
  if (Math.abs(diffDays) < 30)
    return rtf.format(Math.round(diffDays / 7), "week"); // semanas
  if (Math.abs(diffDays) < 365)
    return rtf.format(Math.round(diffDays / 30), "month"); // meses
  return rtf.format(Math.round(diffDays / 365), "year"); // años
}

// ------------------------------------------------------------------------------
// isExpired — Verifica si una fecha ya pasó (está vencida)
//
// Usado para determinar el estado visual de fechas de pago
// o vencimiento — si ya pasó, se muestra en rojo.
//
// Parámetros:
//   value (string|Date|number) → la fecha a verificar
//
// Retorna:
//   boolean → true si la fecha ya pasó, false si es futura o inválida
//
// Ejemplos:
//   isExpired('2025-01-01') → true  (ya pasó)
//   isExpired('2030-01-01') → false (futura)
//   isExpired(null)         → false (inválido, se considera seguro)
// ------------------------------------------------------------------------------

export function isExpired(value) {
  const date = parseDate(value);

  // Si la fecha es inválida, se considera no vencida (caso seguro)
  if (!date) return false;

  return date.getTime() < Date.now();
}

// ------------------------------------------------------------------------------
// daysUntil — Calcula cuántos días faltan para una fecha
//
// Usado para mostrar alertas de próximo vencimiento.
// Retorna negativo si la fecha ya pasó.
//
// Parámetros:
//   value (string|Date|number) → la fecha objetivo
//
// Retorna:
//   number → días hasta la fecha (negativo si ya pasó)
//   null   → si la fecha es inválida
//
// Ejemplos:
//   daysUntil('2026-03-20') → 3   (faltan 3 días)
//   daysUntil('2026-03-10') → -7  (hace 7 días)
//   daysUntil(null)         → null
// ------------------------------------------------------------------------------

export function daysUntil(value) {
  const date = parseDate(value);

  if (!date) return null;

  const diffMs = date.getTime() - Date.now();
  return Math.round(diffMs / (1000 * 60 * 60 * 24));
}
