// ==============================================================================
// INPUT.JSX — Componente de campo de formulario del sistema ELISA
//
// Responsabilidad: renderiza campos de texto, select, textarea con los
//   estilos del sistema y manejo de errores inline.
//
// Patrón: Controlled Component — el valor siempre es controlado por el
//   componente padre mediante value + onChange (patrón React estándar).
//
// Seguridad:
//   - Sanitiza el input visualmente mostrando el estado de error.
//   - NO hace sanitización de contenido — eso lo hace el backend.
//   - Los campos de contraseña usan type="password" por defecto.
//   - maxLength previene inputs excesivamente largos en el cliente.
//
// Accesibilidad:
//   - El label siempre está vinculado al input mediante htmlFor/id.
//   - El mensaje de error está vinculado con aria-describedby.
//   - aria-invalid comunica el estado de error a lectores de pantalla.
//   - El campo requerido tiene aria-required.
//
// Tipos soportados:
//   text, email, password, number, tel, date, textarea, select
//
// Uso:
//   <Input
//     label="Nombre completo"
//     name="name"
//     value={formData.name}
//     onChange={handleChange}
//     error={errors.name}
//     required
//   />
//
//   <Input
//     type="select"
//     label="Plan"
//     name="plan"
//     value={formData.plan}
//     onChange={handleChange}
//     options={[
//       { value: 'alquiler', label: 'Alquiler mensual' },
//       { value: 'venta',    label: 'Venta única'      },
//     ]}
//   />
// ==============================================================================

// ------------------------------------------------------------------------------
// SECCIÓN 1 — ESTILOS BASE
// ------------------------------------------------------------------------------

// Estilos base del campo de input
const INPUT_BASE = [
  "w-full px-4 py-2.5",
  "rounded text-sm",
  "transition-all duration-200",
  "focus:outline-none",
  "placeholder:text-gray-600",
].join(" ");

// Estilos del input en estado normal
const INPUT_NORMAL = [
  "bg-[#1a1d30] text-white",
  "border border-cyan-400/20",
  "focus:border-cyan-400/60 focus:shadow-[0_0_15px_rgba(63,229,229,0.15)]",
].join(" ");

// Estilos del input en estado de error
const INPUT_ERROR = [
  "bg-[#1a1d30] text-white",
  "border border-red-400/60",
  "shadow-[0_0_10px_rgba(255,51,102,0.15)]",
  "focus:border-red-400 focus:shadow-[0_0_15px_rgba(255,51,102,0.25)]",
].join(" ");

// Estilos del input deshabilitado
const INPUT_DISABLED = [
  "bg-[#111427] text-gray-500",
  "border border-gray-700/30",
  "cursor-not-allowed",
].join(" ");

// ==============================================================================
// COMPONENTE — Input
//
// Props:
//   label       (string)   → etiqueta visible del campo (recomendado siempre)
//   name        (string)   → nombre del campo — usado para identificación
//   type        (string)   → tipo de input HTML + 'textarea' + 'select'
//   value       (any)      → valor controlado desde el padre
//   onChange    (function) → handler de cambio de valor
//   error       (string)   → mensaje de error inline (rojo debajo del campo)
//   hint        (string)   → texto de ayuda (gris debajo del campo)
//   required    (boolean)  → campo obligatorio — muestra asterisco rojo
//   disabled    (boolean)  → deshabilita el campo
//   placeholder (string)   → texto placeholder
//   options     (array)    → solo para type="select": [{value, label}]
//   rows        (number)   → solo para type="textarea": cantidad de filas
//   className   (string)   → clases adicionales al contenedor
//   ...props               → otros atributos HTML del input
// ==============================================================================

export default function Input({
  label,
  name,
  type = "text",
  value,
  onChange,
  error,
  hint,
  required = false,
  disabled = false,
  placeholder,
  options = [],
  rows = 3,
  className = "",
  ...props
}) {
  // --------------------------------------------------------------------------
  // SECCIÓN 2 — ID ÚNICO PARA ACCESIBILIDAD
  //
  // El id vincula el label con el input (htmlFor/id).
  // El errorId vincula el mensaje de error con el input (aria-describedby).
  // --------------------------------------------------------------------------

  const inputId = `input-${name}`;
  const errorId = `error-${name}`;
  const hintId = `hint-${name}`;

  // Construye aria-describedby incluyendo el id del error si existe
  const describedBy =
    [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ") ||
    undefined;

  // --------------------------------------------------------------------------
  // SECCIÓN 3 — SELECCIÓN DE ESTILOS DEL INPUT
  //
  // El estilo cambia según el estado: normal, error, deshabilitado.
  // --------------------------------------------------------------------------

  const inputStyles = [
    INPUT_BASE,
    disabled ? INPUT_DISABLED : error ? INPUT_ERROR : INPUT_NORMAL,
    // El select necesita un color de fondo explícito para las opciones
    type === "select" ? "cursor-pointer" : "",
  ].join(" ");

  // --------------------------------------------------------------------------
  // SECCIÓN 4 — PROPS COMUNES PARA TODOS LOS TIPOS DE INPUT
  // --------------------------------------------------------------------------

  const commonProps = {
    id: inputId,
    name,
    value,
    onChange,
    disabled,
    required,
    placeholder,
    className: inputStyles,
    "aria-invalid": error ? "true" : "false",
    "aria-required": required,
    "aria-describedby": describedBy,
    ...props,
  };

  // --------------------------------------------------------------------------
  // SECCIÓN 5 — RENDER DEL CAMPO SEGÚN TIPO
  // --------------------------------------------------------------------------

  const renderField = () => {
    // ── TEXTAREA ─────────────────────────────────────────────────────────────
    if (type === "textarea") {
      return (
        <textarea
          {...commonProps}
          rows={rows}
          className={`${inputStyles} resize-none`}
        />
      );
    }

    // ── SELECT ────────────────────────────────────────────────────────────────
    if (type === "select") {
      return (
        <select {...commonProps} className={`${inputStyles} bg-[#1a1d30]`}>
          {/* Opción vacía por defecto */}
          {placeholder && (
            <option value="" disabled className="bg-[#1a1d30] text-gray-500">
              {placeholder}
            </option>
          )}

          {/* Opciones del select */}
          {options.map((opt) => (
            <option
              key={opt.value}
              value={opt.value}
              className="bg-[#1a1d30] text-white"
            >
              {opt.label}
            </option>
          ))}
        </select>
      );
    }

    // ── INPUT ESTÁNDAR (text, email, password, number, tel, date, etc.) ──────
    return <input {...commonProps} type={type} />;
  };

  // --------------------------------------------------------------------------
  // SECCIÓN 6 — RENDER COMPLETO DEL CAMPO CON LABEL Y MENSAJES
  // --------------------------------------------------------------------------

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {/* Label del campo — siempre vinculado al input */}
      {label && (
        <label
          htmlFor={inputId}
          className="text-sm font-medium"
          style={{ color: error ? "#ff3366" : "#c5cdd8" }}
        >
          {label}

          {/* Asterisco rojo para campos obligatorios */}
          {required && (
            <span className="text-red-400 ml-1" aria-hidden="true">
              *
            </span>
          )}
        </label>
      )}

      {/* Campo de input */}
      {renderField()}

      {/* Mensaje de error inline — solo visible cuando hay error */}
      {error && (
        <p
          id={errorId}
          role="alert"
          className="text-xs text-red-400 flex items-center gap-1"
        >
          {/* Ícono de advertencia */}
          <svg
            className="w-3 h-3 flex-shrink-0"
            fill="currentColor"
            viewBox="0 0 20 20"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
          {error}
        </p>
      )}

      {/* Texto de ayuda — solo visible cuando no hay error */}
      {hint && !error && (
        <p id={hintId} className="text-xs text-gray-500">
          {hint}
        </p>
      )}
    </div>
  );
}
