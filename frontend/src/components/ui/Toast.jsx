// ==============================================================================
// TOAST.JSX — Sistema de notificaciones toast del sistema ELISA
//
// Responsabilidad: muestra notificaciones flotantes en la esquina inferior
//   derecha con animación de entrada, barra de progreso y cierre automático.
//
// Diseño según mockup HTML:
//   - Animación slideIn desde la derecha con efecto bounce
//   - Barra inferior que se va reduciendo (4 segundos)
//   - Se cierra automáticamente al terminar la barra
//   - Se puede cerrar manualmente haciendo click en la X
//   - Estilos por tipo: success, error, warning, info
//
// Patrón: Context + Hook
//   ToastProvider  → envuelve la app, renderiza los toasts
//   useToast       → hook para disparar toasts desde cualquier componente
//
// Uso:
//   const { showToast } = useToast()
//   showToast('success', 'CLIENTE REGISTRADO', 'Pollería El Carbón fue registrado.')
//   showToast('error',   'ERROR DE SERVIDOR',  'No se pudo completar la operación.')
//   showToast('warning', 'PAGO PRÓXIMO',        'El cliente vence en 3 días.')
//   showToast('info',    'SESIÓN RENOVADA',     'Tu sesión fue renovada automáticamente.')
// ==============================================================================

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
} from "react";

// ── CONTEXTO ───────────────────────────────────────────────────────────────────

const ToastContext = createContext(null);

// ── CONFIGURACIÓN POR TIPO ─────────────────────────────────────────────────────

const TOAST_CONFIG = {
  success: {
    background: "rgba(0,255,136,0.08)",
    border: "1px solid rgba(0,255,136,0.25)",
    boxShadow: "0 0 30px rgba(0,255,136,0.1), 0 8px 32px rgba(0,0,0,0.4)",
    iconBg: "rgba(0,255,136,0.15)",
    iconColor: "#00ff88",
    titleColor: "#00ff88",
    barColor: "#00ff88",
    icon: "✓",
  },
  error: {
    background: "rgba(255,51,102,0.08)",
    border: "1px solid rgba(255,51,102,0.25)",
    boxShadow: "0 0 30px rgba(255,51,102,0.1), 0 8px 32px rgba(0,0,0,0.4)",
    iconBg: "rgba(255,51,102,0.15)",
    iconColor: "#ff3366",
    titleColor: "#ff3366",
    barColor: "#ff3366",
    icon: "✕",
  },
  warning: {
    background: "rgba(255,184,0,0.08)",
    border: "1px solid rgba(255,184,0,0.25)",
    boxShadow: "0 0 30px rgba(255,184,0,0.1), 0 8px 32px rgba(0,0,0,0.4)",
    iconBg: "rgba(255,184,0,0.15)",
    iconColor: "#ffb800",
    titleColor: "#ffb800",
    barColor: "#ffb800",
    icon: "⚠",
  },
  info: {
    background: "rgba(0,200,255,0.08)",
    border: "1px solid rgba(0,200,255,0.25)",
    boxShadow: "0 0 30px rgba(0,200,255,0.1), 0 8px 32px rgba(0,0,0,0.4)",
    iconBg: "rgba(0,200,255,0.15)",
    iconColor: "#00c8ff",
    titleColor: "#00c8ff",
    barColor: "#00c8ff",
    icon: "i",
  },
};

const DURATION = 4000; // ms antes de cerrarse automáticamente

// ── COMPONENTE INDIVIDUAL DE TOAST ─────────────────────────────────────────────

function ToastItem({ toast, onRemove }) {
  const config = TOAST_CONFIG[toast.type] || TOAST_CONFIG.info;
  const barRef = useRef(null);

  // Inicia la barra de progreso y el cierre automático
  useEffect(() => {
    // Animación de la barra — de 100% a 0% en DURATION ms
    if (barRef.current) {
      barRef.current.style.width = "100%";
      barRef.current.style.transition = `width ${DURATION}ms linear`;
      // Pequeño delay para que el navegador registre el estado inicial
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (barRef.current) barRef.current.style.width = "0%";
        });
      });
    }

    // Cierre automático
    const timer = setTimeout(() => onRemove(toast.id), DURATION);
    return () => clearTimeout(timer);
  }, [toast.id, onRemove]);

  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        alignItems: "flex-start",
        gap: "14px",
        padding: "16px 20px",
        paddingBottom: "20px", // espacio para la barra
        borderRadius: "12px",
        minWidth: "320px",
        maxWidth: "400px",
        backdropFilter: "blur(20px)",
        background: config.background,
        border: config.border,
        boxShadow: config.boxShadow,
        overflow: "hidden",
        // Animación de entrada — slideIn con bounce desde la derecha
        animation: "elisaToastIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)",
        pointerEvents: "all",
      }}
    >
      {/* Ícono */}
      <div
        style={{
          width: "36px",
          height: "36px",
          borderRadius: "8px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          fontSize: "16px",
          fontWeight: 700,
          backgroundColor: config.iconBg,
          color: config.iconColor,
        }}
      >
        {config.icon}
      </div>

      {/* Contenido */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p
          style={{
            fontFamily: "'Orbitron', monospace",
            fontSize: "12px",
            fontWeight: 700,
            letterSpacing: "1px",
            color: config.titleColor,
            margin: "0 0 4px 0",
          }}
        >
          {toast.title}
        </p>
        <p
          style={{
            fontFamily: "'Rajdhani', sans-serif",
            fontSize: "13px",
            fontWeight: 500,
            color: "#c5cdd8",
            lineHeight: 1.4,
            margin: 0,
          }}
        >
          {toast.message}
        </p>
      </div>

      {/* Botón cerrar */}
      <button
        onClick={() => onRemove(toast.id)}
        style={{
          background: "transparent",
          border: "none",
          color: "#8892a4",
          cursor: "pointer",
          fontSize: "16px",
          lineHeight: 1,
          padding: "0",
          flexShrink: 0,
          marginTop: "2px",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.color = "white")}
        onMouseLeave={(e) => (e.currentTarget.style.color = "#8892a4")}
      >
        ✕
      </button>

      {/* Barra de progreso — se reduce de derecha a izquierda */}
      <div
        ref={barRef}
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          height: "2px",
          width: "100%",
          borderRadius: "0 0 0 12px",
          backgroundColor: config.barColor,
        }}
      />
    </div>
  );
}

// ── PROVIDER ───────────────────────────────────────────────────────────────────

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  // Agrega un nuevo toast
  const showToast = useCallback((type, title, message) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, type, title, message }]);
  }, []);

  // Elimina un toast por id
  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}

      {/* Contenedor de toasts — esquina inferior derecha */}
      <div
        style={{
          position: "fixed",
          bottom: "28px",
          right: "28px",
          zIndex: 9998,
          display: "flex",
          flexDirection: "column",
          gap: "10px",
          pointerEvents: "none",
        }}
      >
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onRemove={removeToast} />
        ))}
      </div>

      {/* Keyframes para la animación de entrada */}
      <style>{`
        @keyframes elisaToastIn {
          from { opacity: 0; transform: translateX(60px) scale(0.9); }
          to   { opacity: 1; transform: translateX(0) scale(1); }
        }
      `}</style>
    </ToastContext.Provider>
  );
}

// ── HOOK ───────────────────────────────────────────────────────────────────────

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast debe usarse dentro de ToastProvider");
  return ctx;
}
