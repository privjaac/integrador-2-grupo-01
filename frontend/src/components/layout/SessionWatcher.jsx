// ==============================================================================
// SESSIONWATCHER.JSX — Escucha eventos de sesión y sincroniza el token
//
// Responsabilidad:
//   - Sincroniza window.__elisa_token__ con el token del AuthContext
//   - Escucha 'elisa:session-warning' → toast de aviso con tiempo restante
//   - Escucha 'elisa:session-expired' → toast de error + logout + redirect
// ==============================================================================

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../ui/Toast";

export default function SessionWatcher() {
  const { token, logout, isAuthenticated } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  // Sincroniza el token con window para que axios lo pueda leer
  useEffect(() => {
    window.__elisa_token__ = token || null;
  }, [token]);

  useEffect(() => {
    const handleWarning = (e) => {
      const minutes = e.detail?.minutes;
      const msg = minutes
        ? `Tu sesión cerrará en ${minutes} minutos por inactividad.`
        : "Tu sesión cerrará pronto por inactividad. Hacé click para continuar.";
      showToast("warning", "SESIÓN POR VENCER", msg);
    };

    const handleExpired = () => {
      showToast(
        "error",
        "SESIÓN EXPIRADA",
        "Tu sesión se cerró por 24h de inactividad. Iniciá sesión nuevamente.",
      );
      logout();
      navigate("/login", { replace: true });
    };

    window.addEventListener("elisa:session-warning", handleWarning);
    window.addEventListener("elisa:session-expired", handleExpired);
    return () => {
      window.removeEventListener("elisa:session-warning", handleWarning);
      window.removeEventListener("elisa:session-expired", handleExpired);
    };
  }, [logout, navigate, showToast]);

  return null;
}
