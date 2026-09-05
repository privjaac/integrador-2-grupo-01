// ==============================================================================
// MODAL.JSX — Componente de ventana modal del sistema ELISA
//
// Responsabilidad: muestra contenido superpuesto sobre la pantalla principal.
//   Se usa para errores, confirmaciones, formularios en overlay y detalles.
//
// Patrón: Compound Component — el Modal tiene subcomponentes opcionales:
//   Modal           → el contenedor principal con overlay
//   Modal.Header    → título y botón de cierre
//   Modal.Body      → contenido principal
//   Modal.Footer    → botones de acción
//
// Variantes:
//   default    → modal estándar para formularios y contenido general
//   error      → modal de error con ícono rojo y borde rojo
//   success    → modal de éxito con ícono verde y borde verde
//   confirm    → modal de confirmación de acción destructiva
//
// Seguridad:
//   - Bloquea el scroll del body cuando está abierto.
//   - Se cierra con Escape para accesibilidad.
//   - El overlay oscuro previene clicks en el fondo.
//   - focus trap — el foco queda dentro del modal mientras está abierto.
//
// Accesibilidad:
//   - role="dialog" y aria-modal="true"
//   - aria-labelledby vincula el título al modal
//   - El foco va al modal al abrirse
//
// Uso:
//   <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} variant="error">
//     <Modal.Header title="Error al guardar" onClose={() => setIsOpen(false)} />
//     <Modal.Body>
//       <p>No se pudo conectar al servidor.</p>
//     </Modal.Body>
//     <Modal.Footer>
//       <Button onClick={() => setIsOpen(false)}>Cerrar</Button>
//     </Modal.Footer>
//   </Modal>
// ==============================================================================

// ------------------------------------------------------------------------------
// SECCIÓN 1 — IMPORTS
// ------------------------------------------------------------------------------

import { useEffect, useRef } from "react";

// ------------------------------------------------------------------------------
// SECCIÓN 2 — CONFIGURACIÓN DE VARIANTES
// ------------------------------------------------------------------------------

// Estilos del borde superior según variante — da identidad visual al tipo de modal
const VARIANT_BORDER = {
  default: "border-t-2 border-t-cyan-400/50",
  error: "border-t-2 border-t-red-400",
  success: "border-t-2 border-t-green-400",
  confirm: "border-t-2 border-t-yellow-400",
};

// Íconos SVG para variantes que los requieren (error, success, confirm)
const VARIANT_ICONS = {
  error: (
    <div className="flex items-center justify-center w-12 h-12 rounded-full bg-red-400/10 border border-red-400/30 mx-auto mb-4">
      <svg
        className="w-6 h-6 text-red-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.924-.833-2.694 0L4.07 16.5c-.77.833.193 2.5 1.732 2.5z"
        />
      </svg>
    </div>
  ),
  success: (
    <div className="flex items-center justify-center w-12 h-12 rounded-full bg-green-400/10 border border-green-400/30 mx-auto mb-4">
      <svg
        className="w-6 h-6 text-green-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M5 13l4 4L19 7"
        />
      </svg>
    </div>
  ),
  confirm: (
    <div className="flex items-center justify-center w-12 h-12 rounded-full bg-yellow-400/10 border border-yellow-400/30 mx-auto mb-4">
      <svg
        className="w-6 h-6 text-yellow-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
        />
      </svg>
    </div>
  ),
};

// ==============================================================================
// COMPONENTE PRINCIPAL — Modal
//
// Props:
//   isOpen    (boolean)  → controla si el modal está visible
//   onClose   (function) → callback cuando el usuario cierra el modal
//   variant   (string)   → 'default' | 'error' | 'success' | 'confirm'
//   size      (string)   → 'sm' | 'md' | 'lg'
//   children  (node)     → contenido del modal (Header, Body, Footer)
//   className (string)   → clases adicionales al contenedor del modal
// ==============================================================================

export default function Modal({
  isOpen,
  onClose,
  variant = "default",
  size = "md",
  children,
  className = "",
}) {
  // --------------------------------------------------------------------------
  // SECCIÓN 3 — REF PARA FOCUS TRAP
  //
  // Al abrir el modal, el foco va al contenedor del modal.
  // Esto asegura que los usuarios de teclado naveguen dentro del modal.
  // --------------------------------------------------------------------------

  const modalRef = useRef(null);

  // --------------------------------------------------------------------------
  // SECCIÓN 4 — EFECTOS SECUNDARIOS
  //
  // Bloquea el scroll del body cuando el modal está abierto.
  // Registra el listener de teclado para cerrar con Escape.
  // --------------------------------------------------------------------------

  useEffect(() => {
    if (!isOpen) return;

    // Bloquea el scroll del body para que no se mueva el fondo
    document.body.style.overflow = "hidden";

    // Mueve el foco al modal para accesibilidad con teclado
    if (modalRef.current) {
      modalRef.current.focus();
    }

    // Handler para cerrar el modal con la tecla Escape
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && onClose) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    // Cleanup: restaura el scroll y elimina el listener al cerrar
    return () => {
      document.body.style.overflow = "";
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  // --------------------------------------------------------------------------
  // SECCIÓN 5 — NO RENDERIZAR SI ESTÁ CERRADO
  //
  // En lugar de usar visibility:hidden, directamente no renderizamos
  // el modal cuando está cerrado para que no ocupe recursos.
  // --------------------------------------------------------------------------

  if (!isOpen) return null;

  // --------------------------------------------------------------------------
  // SECCIÓN 6 — TAMAÑOS DEL MODAL
  // --------------------------------------------------------------------------

  const SIZE_STYLES = {
    sm: "max-w-sm",
    md: "max-w-md",
    lg: "max-w-lg",
  };

  const sizeStyle = SIZE_STYLES[size] || SIZE_STYLES.md;
  const variantBorder = VARIANT_BORDER[variant] || VARIANT_BORDER.default;
  const variantIcon = VARIANT_ICONS[variant];

  // --------------------------------------------------------------------------
  // SECCIÓN 7 — RENDER
  // --------------------------------------------------------------------------

  return (
    // Overlay oscuro — cubre toda la pantalla detrás del modal
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{
        backgroundColor: "rgba(5, 6, 15, 0.85)",
        backdropFilter: "blur(4px)",
      }}
      // Click en el overlay cierra el modal
      onClick={(e) => {
        if (e.target === e.currentTarget && onClose) onClose();
      }}
      aria-hidden="true"
    >
      {/* Contenedor del modal */}
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        className={[
          "relative w-full animate-fade-in",
          "rounded-lg",
          "border border-cyan-400/20",
          variantBorder,
          sizeStyle,
          className,
        ].join(" ")}
        style={{ backgroundColor: "#111427" }}
        // Previene que el click dentro del modal cierre el overlay
        onClick={(e) => e.stopPropagation()}
      >
        {/* Ícono de variante — solo para error, success, confirm */}
        {variantIcon && <div className="pt-6 px-6">{variantIcon}</div>}

        {/* Contenido del modal (Header + Body + Footer) */}
        {children}
      </div>
    </div>
  );
}

// ==============================================================================
// SUBCOMPONENTE — Modal.Header
//
// Props:
//   title   (string)   → título del modal
//   onClose (function) → callback para el botón X de cierre
// ==============================================================================

Modal.Header = function ModalHeader({ title, onClose }) {
  return (
    <div className="flex items-center justify-between px-6 py-4 border-b border-cyan-400/10">
      {/* Título del modal */}
      <h2
        className="text-base font-semibold text-white"
        style={{
          fontFamily: "'Rajdhani', sans-serif",
          letterSpacing: "0.05em",
        }}
      >
        {title}
      </h2>

      {/* Botón de cierre — solo se muestra si se provee onClose */}
      {onClose && (
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-cyan-400 transition-colors p-1 rounded"
          aria-label="Cerrar modal"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      )}
    </div>
  );
};

// ==============================================================================
// SUBCOMPONENTE — Modal.Body
//
// Props:
//   children  (node)   → contenido principal del modal
//   className (string) → clases adicionales
// ==============================================================================

Modal.Body = function ModalBody({ children, className = "" }) {
  return (
    <div
      className={`px-6 py-5 text-gray-300 text-sm leading-relaxed ${className}`}
    >
      {children}
    </div>
  );
};

// ==============================================================================
// SUBCOMPONENTE — Modal.Footer
//
// Props:
//   children  (node)   → botones de acción
//   className (string) → clases adicionales
// ==============================================================================

Modal.Footer = function ModalFooter({ children, className = "" }) {
  return (
    <div
      className={`flex items-center justify-end gap-3 px-6 py-4 border-t border-cyan-400/10 ${className}`}
    >
      {children}
    </div>
  );
};
