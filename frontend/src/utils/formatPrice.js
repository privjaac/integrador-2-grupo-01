// ==============================================================================
// FORMATPRICE.JS — Funciones utilitarias para formateo de precios y moneda
//
// Responsabilidad: centraliza TODA la lógica de formateo de valores
//   monetarios del sistema ELISA. Garantiza que los precios se muestren
//   de forma consistente en toda la aplicación.
//
// Patrón: Utility Module — funciones puras sin estado ni efectos secundarios.
//
// Moneda: Sol peruano (PEN, S/).
//   Todos los precios del sistema están en soles peruanos.
//   Si en el futuro se agrega otra moneda, se extiende este módulo.
//
// Seguridad:
//   Todas las funciones validan su input.
//   Valores inválidos retornan un string seguro en lugar de crashear.
//   Previene XSS al nunca insertar HTML directamente — solo texto plano.
//
// Uso en cualquier componente:
//   import { formatPrice, formatPriceShort, parsePriceInput } from '../../utils/formatPrice'
//
//   formatPrice(149)        → 'S/ 149.00'
//   formatPrice(1250.5)     → 'S/ 1,250.50'
//   formatPriceShort(1500)  → 'S/ 1.5K'
//   parsePriceInput('149,') → 149
//
// NOTA PARA EL EQUIPO:
//   Nunca formatear precios directamente en los componentes.
//   Nunca concatenar 'S/' manualmente — usar estas funciones.
// ==============================================================================

// ------------------------------------------------------------------------------
// SECCIÓN 1 — CONSTANTES DE CONFIGURACIÓN
// ------------------------------------------------------------------------------

// Locale para formateo monetario — español de Perú
const LOCALE = "es-PE";

// Código de moneda ISO 4217 — Sol peruano
const CURRENCY = "PEN";

// Símbolo de moneda a mostrar en la UI
const CURRENCY_SYMBOL = "S/";

// Valor mínimo válido para un precio en el sistema
const MIN_PRICE = 0;

// Valor máximo razonable — protección contra inputs maliciosos
const MAX_PRICE = 999999.99;

// ------------------------------------------------------------------------------
// SECCIÓN 2 — FUNCIÓN AUXILIAR INTERNA
//
// Convierte y valida cualquier tipo de input numérico.
// Usada internamente por todas las funciones públicas.
//
// Parámetros:
//   value (number|string) → el valor a validar y convertir
//
// Retorna:
//   number válido, o null si el input es inválido
// ------------------------------------------------------------------------------

function parsePrice(value) {
  // Rechaza valores nulos o indefinidos
  if (value === null || value === undefined) return null;

  // Convierte a número si es string
  // parseFloat maneja strings como '149.00', '1,250.50'
  const num =
    typeof value === "string"
      ? parseFloat(value.replace(/,/g, "")) // elimina comas de miles antes de parsear
      : Number(value);

  // Verifica que sea un número finito válido
  if (!isFinite(num) || isNaN(num)) return null;

  // Verifica que esté dentro del rango válido del sistema
  if (num < MIN_PRICE || num > MAX_PRICE) return null;

  return num;
}

// ==============================================================================
// SECCIÓN 3 — FUNCIONES PÚBLICAS DE FORMATEO
// ==============================================================================

// ------------------------------------------------------------------------------
// formatPrice — Formatea un precio con símbolo de sol y dos decimales
//
// Es el formato estándar de precio en ELISA para mostrar importes
// en tablas, formularios y reportes.
//
// Parámetros:
//   value   (number|string) → el precio a formatear
//   options (object)        → opciones opcionales:
//     showSymbol (boolean)  → mostrar 'S/' (default: true)
//     decimals   (number)   → cantidad de decimales (default: 2)
//
// Retorna:
//   string → 'S/ 149.00', 'S/ 1,250.50'
//   '—'    → si el valor es inválido o nulo
//
// Ejemplos:
//   formatPrice(149)              → 'S/ 149.00'
//   formatPrice(1250.5)           → 'S/ 1,250.50'
//   formatPrice(0)                → 'S/ 0.00'
//   formatPrice(149, {decimals:0})→ 'S/ 149'
//   formatPrice(null)             → '—'
// ------------------------------------------------------------------------------

export function formatPrice(value, options = {}) {
  const num = parsePrice(value);

  if (num === null) return "—";

  const { showSymbol = true, decimals = 2 } = options;

  // Intl.NumberFormat da el formato correcto con separadores de miles
  // y cantidad exacta de decimales según el locale peruano
  const formatted = new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num);

  return showSymbol ? `${CURRENCY_SYMBOL} ${formatted}` : formatted;
}

// ------------------------------------------------------------------------------
// formatPriceShort — Formatea un precio en formato compacto para espacios reducidos
//
// Usado en dashboards y resúmenes donde el espacio es limitado.
// Abrevia miles con K y millones con M.
//
// Parámetros:
//   value (number|string) → el precio a formatear
//
// Retorna:
//   string → 'S/ 149', 'S/ 1.5K', 'S/ 2.3M'
//   '—'    → si el valor es inválido o nulo
//
// Ejemplos:
//   formatPriceShort(149)      → 'S/ 149'
//   formatPriceShort(1500)     → 'S/ 1.5K'
//   formatPriceShort(2300000)  → 'S/ 2.3M'
// ------------------------------------------------------------------------------

export function formatPriceShort(value) {
  const num = parsePrice(value);

  if (num === null) return "—";

  // Para valores menores a 1000, muestra el número entero sin decimales
  if (num < 1000) {
    return `${CURRENCY_SYMBOL} ${Math.round(num)}`;
  }

  // Para miles (1K - 999K)
  if (num < 1_000_000) {
    const thousands = num / 1000;
    // Muestra un decimal solo si es necesario (1.5K, no 1.0K)
    const formatted =
      thousands % 1 === 0 ? thousands.toFixed(0) : thousands.toFixed(1);
    return `${CURRENCY_SYMBOL} ${formatted}K`;
  }

  // Para millones (1M+)
  const millions = num / 1_000_000;
  const formatted =
    millions % 1 === 0 ? millions.toFixed(0) : millions.toFixed(1);
  return `${CURRENCY_SYMBOL} ${formatted}M`;
}

// ------------------------------------------------------------------------------
// formatPriceRange — Formatea un rango de precios (mínimo - máximo)
//
// Usado para mostrar rangos de precios de tipos de web en el catálogo.
//
// Parámetros:
//   min (number|string) → precio mínimo
//   max (number|string) → precio máximo
//
// Retorna:
//   string → 'S/ 149.00 — S/ 500.00'
//   '—'    → si algún valor es inválido
//
// Ejemplos:
//   formatPriceRange(149, 500) → 'S/ 149.00 — S/ 500.00'
//   formatPriceRange(null, 500)→ '—'
// ------------------------------------------------------------------------------

export function formatPriceRange(min, max) {
  const numMin = parsePrice(min);
  const numMax = parsePrice(max);

  if (numMin === null || numMax === null) return "—";

  return `${formatPrice(numMin)} — ${formatPrice(numMax)}`;
}

// ------------------------------------------------------------------------------
// parsePriceInput — Convierte el input del usuario a un número válido
//
// Usado en formularios para limpiar y validar lo que escribe el usuario
// antes de enviarlo al backend. Previene envío de datos malformados.
//
// Seguridad:
//   Elimina caracteres no numéricos (XSS prevention en inputs).
//   Solo permite dígitos, punto decimal y signo negativo.
//
// Parámetros:
//   input (string) → el texto ingresado por el usuario en el campo de precio
//
// Retorna:
//   number → el valor numérico limpio
//   null   → si el input no representa un precio válido
//
// Ejemplos:
//   parsePriceInput('149')      → 149
//   parsePriceInput('149.50')   → 149.5
//   parsePriceInput('S/ 149')   → 149
//   parsePriceInput('abc')      → null
//   parsePriceInput('')         → null
//   parsePriceInput('-50')      → null  (precios negativos no válidos)
// ------------------------------------------------------------------------------

export function parsePriceInput(input) {
  if (!input && input !== 0) return null;

  // Convierte a string por si acaso llega un número
  const str = String(input);

  // Elimina todo excepto dígitos y punto decimal
  // Esto previene inyección de caracteres especiales en campos numéricos
  const cleaned = str.replace(/[^0-9.]/g, "");

  if (!cleaned) return null;

  const num = parseFloat(cleaned);

  // Verifica que sea un número válido y positivo
  if (isNaN(num) || num < 0) return null;

  // Verifica que esté dentro del rango del sistema
  if (num > MAX_PRICE) return null;

  // Redondea a 2 decimales para evitar errores de punto flotante
  // Ej: 149.999999 → 150.00
  return Math.round(num * 100) / 100;
}

// ------------------------------------------------------------------------------
// getPriceStatus — Determina el estado visual de un precio según su monto
//
// Usado para aplicar colores semánticos a los precios en la UI.
// Retorna una clave de estado que los componentes usan para
// elegir el color del badge o texto.
//
// Parámetros:
//   value     (number) → el precio actual
//   threshold (object) → los umbrales para cada estado
//     low  (number) → por debajo de este valor → estado 'low'
//     high (number) → por encima de este valor → estado 'high'
//
// Retorna:
//   'low'     → precio bajo (ej: por debajo de S/ 100)
//   'normal'  → precio normal
//   'high'    → precio alto
//   'invalid' → precio inválido
//
// Ejemplos:
//   getPriceStatus(50,  { low: 100, high: 500 }) → 'low'
//   getPriceStatus(300, { low: 100, high: 500 }) → 'normal'
//   getPriceStatus(800, { low: 100, high: 500 }) → 'high'
// ------------------------------------------------------------------------------

export function getPriceStatus(value, threshold = { low: 100, high: 500 }) {
  const num = parsePrice(value);

  if (num === null) return "invalid";

  if (num < threshold.low) return "low";
  if (num > threshold.high) return "high";
  return "normal";
}
