// ==============================================================================
// BADGE.JSX — Componente de etiqueta de estado del sistema ELISA
//
// Responsabilidad: muestra etiquetas visuales de estado con colores semánticos.
//   Se usa para indicar el estado de clientes, colaboradores, tipos de web, etc.
//
// Patrón: Presentational Component con mapa de variantes.
//
// Variantes disponibles:
//   success  → verde  — activo, exitoso, completado
//   warning  → amarillo — en desarrollo, pendiente, proceso
//   danger   → rojo   — inactivo, error, vencido
//   info     → azul   — informativo, neutral
//   cyan     → cyan   — destacado, primario
//   gray     → gris   — desactivado, sin estado
//
// Variantes semánticas de negocio (mapean a colores automáticamente):
//   activo      → success
//   desarrollo  → warning
//   inactivo    → danger
//   alquiler    → info
//   venta       → cyan
//   mensual     → info
//   anual       → cyan
//
// Uso:
//   <Badge variant="success">Activo</Badge>
//   <Badge status="activo" />          → usa el texto y color automático
//   <Badge status="desarrollo" />      → usa el texto y color automático
// ==============================================================================

// ------------------------------------------------------------------------------
// SECCIÓN 1 — MAPAS DE ESTILOS Y TEXTO
// ------------------------------------------------------------------------------

// Estilos base comunes a todos los badges
const BASE_STYLES = [
  "inline-flex items-center gap-1.5",
  "px-2.5 py-0.5 rounded-full",
  "text-xs font-semibold tracking-wide uppercase",
  "border",
].join(" ");

// Estilos por variante de color
const VARIANT_STYLES = {
  success: "bg-green-400/10 text-green-400 border-green-400/30",
  warning: "bg-yellow-400/10 text-yellow-400 border-yellow-400/30",
  danger: "bg-red-400/10 text-red-400 border-red-400/30",
  info: "bg-blue-400/10 text-blue-400 border-blue-400/30",
  cyan: "bg-cyan-400/10 text-cyan-400 border-cyan-400/30",
  gray: "bg-gray-400/10 text-gray-400 border-gray-400/30",
};

// Mapa de estados de negocio → variante de color + texto por defecto
// Permite usar <Badge status="activo" /> sin especificar variante ni children
const STATUS_MAP = {
  // Estados de clientes
  activo: { variant: "success", label: "Activo" },
  desarrollo: { variant: "warning", label: "Desarrollo" },
  inactivo: { variant: "danger", label: "Inactivo" },

  // Planes de clientes
  alquiler: { variant: "info", label: "Alquiler" },
  venta: { variant: "cyan", label: "Venta" },

  // Frecuencias de pago
  mensual: { variant: "info", label: "Mensual" },
  anual: { variant: "cyan", label: "Anual" },

  // Estados de colaboradores
  true: { variant: "success", label: "Activo" },
  false: { variant: "danger", label: "Inactivo" },

  // Estados de catálogo
  disponible: { variant: "success", label: "Disponible" },
  nodisponible: { variant: "gray", label: "No disponible" },
};

// ==============================================================================
// COMPONENTE — Badge
//
// Props:
//   children  (node)   → texto del badge (si no se usa status)
//   variant   (string) → 'success' | 'warning' | 'danger' | 'info' | 'cyan' | 'gray'
//   status    (string) → estado de negocio — mapea automáticamente a variante y texto
//   dot       (boolean)→ si true, muestra un punto de color antes del texto
//   className (string) → clases adicionales
// ==============================================================================

export default function Badge({
  children,
  variant = "gray",
  status,
  dot = true,
  className = "",
}) {
  // --------------------------------------------------------------------------
  // SECCIÓN 2 — RESOLUCIÓN DE VARIANTE Y TEXTO
  //
  // Si se recibe status, se busca en el mapa de estados de negocio.
  // Si no hay match, usa los valores por defecto.
  // Si se reciben children, tienen prioridad sobre el texto del mapa.
  // --------------------------------------------------------------------------

  let resolvedVariant = variant;
  let resolvedLabel = children;

  if (status !== undefined) {
    const statusKey = String(status).toLowerCase();
    const mapped = STATUS_MAP[statusKey];

    if (mapped) {
      resolvedVariant = mapped.variant;
      // Los children tienen prioridad — permiten texto custom con color automático
      resolvedLabel = children || mapped.label;
    }
  }

  const variantStyle = VARIANT_STYLES[resolvedVariant] || VARIANT_STYLES.gray;

  const classes = [BASE_STYLES, variantStyle, className].join(" ");

  // --------------------------------------------------------------------------
  // SECCIÓN 3 — COLOR DEL PUNTO
  //
  // El punto de estado tiene el mismo color que el texto del badge.
  // Se extrae del mapa de variantes para mantener consistencia.
  // --------------------------------------------------------------------------

  const dotColorMap = {
    success: "bg-green-400",
    warning: "bg-yellow-400",
    danger: "bg-red-400",
    info: "bg-blue-400",
    cyan: "bg-cyan-400",
    gray: "bg-gray-400",
  };

  const dotColor = dotColorMap[resolvedVariant] || dotColorMap.gray;

  // --------------------------------------------------------------------------
  // SECCIÓN 4 — RENDER
  // --------------------------------------------------------------------------

  return (
    <span className={classes}>
      {/* Punto indicador de estado — solo si dot=true */}
      {dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full ${dotColor}`}
          aria-hidden="true"
        />
      )}

      {resolvedLabel}
    </span>
  );
}
