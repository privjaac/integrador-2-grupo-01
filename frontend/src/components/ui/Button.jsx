// ==============================================================================
// BUTTON.JSX v3 — Estilos inline, sin dependencia de Tailwind
// ==============================================================================

import LoadingSpinner from "./LoadingSpinner";

// Estilos base comunes
const BASE = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "0.5rem",
  fontFamily: "'Rajdhani', sans-serif",
  fontWeight: 600,
  letterSpacing: "0.04em",
  borderRadius: "0.5rem",
  cursor: "pointer",
  transition: "all 0.2s",
  border: "1px solid transparent",
  outline: "none",
  whiteSpace: "nowrap",
};

// Estilos por variante
const VARIANTS = {
  primary: {
    backgroundColor: "#3fe5e5",
    color: "#05060f",
    border: "1px solid transparent",
  },
  secondary: {
    backgroundColor: "transparent",
    color: "#3fe5e5",
    border: "1px solid rgba(63,229,229,0.4)",
  },
  danger: {
    backgroundColor: "transparent",
    color: "#ff3366",
    border: "1px solid rgba(255,51,102,0.4)",
  },
  ghost: {
    backgroundColor: "transparent",
    color: "#8892a4",
    border: "1px solid transparent",
  },
};

// Estilos por tamaño — padding generoso
const SIZES = {
  sm: { padding: "0.5rem 1rem", fontSize: "12px" },
  md: { padding: "0.625rem 1.25rem", fontSize: "14px" },
  lg: { padding: "0.875rem 1.75rem", fontSize: "14px" },
};

// Estilos hover por variante
const HOVER_VARIANTS = {
  primary: {
    backgroundColor: "#5aeaea",
    boxShadow: "0 0 20px rgba(63,229,229,0.5)",
  },
  secondary: {
    backgroundColor: "rgba(63,229,229,0.1)",
    border: "1px solid rgba(63,229,229,0.8)",
    boxShadow: "0 0 15px rgba(63,229,229,0.3)",
  },
  danger: {
    backgroundColor: "rgba(255,51,102,0.1)",
    border: "1px solid rgba(255,51,102,0.8)",
    boxShadow: "0 0 15px rgba(255,51,102,0.3)",
  },
  ghost: { backgroundColor: "rgba(255,255,255,0.05)", color: "#3fe5e5" },
};

export default function Button({
  children,
  variant = "primary",
  size = "md",
  isLoading = false,
  disabled = false,
  type = "button",
  className = "",
  style = {},
  onClick,
  ...props
}) {
  const variantStyle = VARIANTS[variant] || VARIANTS.primary;
  const sizeStyle = SIZES[size] || SIZES.md;

  const combinedStyle = {
    ...BASE,
    ...variantStyle,
    ...sizeStyle,
    opacity: disabled || isLoading ? 0.5 : 1,
    cursor: disabled || isLoading ? "not-allowed" : "pointer",
    pointerEvents: disabled || isLoading ? "none" : "auto",
    ...style,
  };

  return (
    <button
      type={type}
      disabled={disabled || isLoading}
      aria-disabled={disabled || isLoading}
      style={combinedStyle}
      className={className}
      onClick={onClick}
      onMouseEnter={(e) => {
        if (disabled || isLoading) return;
        const hover = HOVER_VARIANTS[variant] || {};
        Object.assign(e.currentTarget.style, hover);
      }}
      onMouseLeave={(e) => {
        if (disabled || isLoading) return;
        Object.assign(e.currentTarget.style, variantStyle);
      }}
      {...props}
    >
      {isLoading && <LoadingSpinner size="sm" color="current" />}
      {children}
    </button>
  );
}
