// ==============================================================================
// LOADINGSPINNER.JSX — Componente de indicador de carga
//
// Responsabilidad: muestra una animación de carga mientras se espera
//   una respuesta del servidor o se procesa una operación.
//   Se usa en botones, páginas completas y secciones de contenido.
//
// Patrón: Presentational Component — sin estado ni lógica de negocio.
//   Solo recibe props y renderiza la animación correspondiente.
//
// Tamaños disponibles:
//   sm  → 16px — dentro de botones
//   md  → 32px — dentro de secciones de contenido
//   lg  → 48px — pantalla completa de carga
//
// Colores disponibles:
//   cyan    → color primario del sistema (default)
//   white   → para fondos oscuros y botones de color
//   current → hereda el color del elemento padre (para uso en botones)
//
// Accesibilidad:
//   role="status" comunica a lectores de pantalla que hay contenido cargando.
//   aria-label provee descripción textual de la animación.
//
// Uso:
//   <LoadingSpinner />                           → mediano, cyan
//   <LoadingSpinner size="lg" />                 → grande, pantalla completa
//   <LoadingSpinner size="sm" color="current" /> → dentro de un botón
// ==============================================================================

// ------------------------------------------------------------------------------
// SECCIÓN 1 — MAPAS DE ESTILOS
// ------------------------------------------------------------------------------

// Tamaños del spinner en píxeles
const SIZE_STYLES = {
  sm: "w-4 h-4 border-2",
  md: "w-8 h-8 border-2",
  lg: "w-12 h-12 border-3",
};

// Colores del spinner
const COLOR_STYLES = {
  cyan: "border-cyan-400/30 border-t-cyan-400",
  white: "border-white/30 border-t-white",
  current: "border-current/30 border-t-current",
};

// ==============================================================================
// COMPONENTE — LoadingSpinner
//
// Props:
//   size      (string)  → 'sm' | 'md' | 'lg'
//   color     (string)  → 'cyan' | 'white' | 'current'
//   fullPage  (boolean) → si true, centra el spinner en toda la pantalla
//   label     (string)  → texto descriptivo para accesibilidad
//   className (string)  → clases adicionales
// ==============================================================================

export default function LoadingSpinner({
  size = "md",
  color = "cyan",
  fullPage = false,
  label = "Cargando...",
  className = "",
}) {
  // --------------------------------------------------------------------------
  // SECCIÓN 2 — CONSTRUCCIÓN DEL SPINNER
  //
  // El spinner es un div circular con un borde que rota.
  // La magia está en que solo el borde superior (border-t) tiene color sólido,
  // mientras los demás lados son transparentes — eso crea el efecto de "arco".
  // --------------------------------------------------------------------------

  const sizeStyle = SIZE_STYLES[size] || SIZE_STYLES.md;
  const colorStyle = COLOR_STYLES[color] || COLOR_STYLES.cyan;

  const spinnerClasses = [
    "rounded-full animate-spin",
    sizeStyle,
    colorStyle,
    className,
  ].join(" ");

  const spinner = (
    <div role="status" aria-label={label} className={spinnerClasses}>
      {/* Texto oculto para lectores de pantalla — no visible en pantalla */}
      <span className="sr-only">{label}</span>
    </div>
  );

  // --------------------------------------------------------------------------
  // SECCIÓN 3 — MODO PANTALLA COMPLETA
  //
  // Cuando fullPage=true, centra el spinner en toda la pantalla.
  // Usado durante la carga inicial de páginas completas.
  // --------------------------------------------------------------------------

  if (fullPage) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-[#05060f]/80 z-50">
        <div className="flex flex-col items-center gap-4">
          {/* Spinner grande centrado */}
          <div className="w-12 h-12 rounded-full animate-spin border-2 border-cyan-400/30 border-t-cyan-400" />

          {/* Texto de carga con tipografía del sistema */}
          <p
            className="text-sm tracking-widest uppercase"
            style={{
              fontFamily: "'Rajdhani', sans-serif",
              color: "#8892a4",
              letterSpacing: "0.2em",
            }}
          >
            {label}
          </p>
        </div>
      </div>
    );
  }

  return spinner;
}
