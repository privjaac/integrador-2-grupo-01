// ==============================================================================
// AUTHCONTEXT.JSX v3 — Con sistema de timers dual y soporte mock
//
// LÓGICA DE TIMERS:
//   Timer 1 (30 min) → cuenta desde el último click
//   Timer 2 (24h)    → se activa cuando Timer 1 llega a 30 min sin click
//   Cualquier click dentro de las 24h resetea ambos timers
//
// MOCK vs REAL:
//   VITE_USE_MOCK=true  → no llama al backend, usa tokens mock en memoria
//   VITE_USE_MOCK=false → llama a /api/auth/refresh para renovar tokens
// ==============================================================================

import { createContext, useState, useEffect, useCallback, useRef } from "react";
import axiosInstance from "../api/axios";

export const AuthContext = createContext(null);

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

// ── CLAVES DE STORAGE ─────────────────────────────────────────────────────────
const KEY_USER = "elisa_user_data";
const KEY_REFRESH = "elisa_refresh_token";
const KEY_LAST_CLICK = "elisa_last_click";
const KEY_TIMER2_START = "elisa_timer2_start";

// ── CONSTANTES DE TIEMPO ──────────────────────────────────────────────────────
const TIMER1_DURATION = 30 * 60 * 1000;
const TIMER2_DURATION = 24 * 60 * 60 * 1000;
const TOKEN_REFRESH_MS = 25 * 60 * 1000;
const CHECK_INTERVAL = 60 * 1000;

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshIntervalRef = useRef(null);
  const checkIntervalRef = useRef(null);

  const isAuthenticated = token !== null;

  // ── LOGOUT ────────────────────────────────────────────────────────────────

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem(KEY_USER);
    localStorage.removeItem(KEY_REFRESH);
    localStorage.removeItem(KEY_LAST_CLICK);
    localStorage.removeItem(KEY_TIMER2_START);
    clearInterval(refreshIntervalRef.current);
    clearInterval(checkIntervalRef.current);
    // Solo llama al backend si no estamos en modo mock
    if (!USE_MOCK) {
      axiosInstance.post("/api/auth/logout").catch(() => {});
    }
  }, []);

  // ── RENOVAR ACCESS TOKEN ───────────────────────────────────────────────────

  const refreshAccessToken = useCallback(async () => {
    // En modo mock — no hay backend, devuelve el token actual
    if (USE_MOCK) {
      return token;
    }

    const savedRefresh = localStorage.getItem(KEY_REFRESH);
    if (!savedRefresh) {
      logout();
      return null;
    }

    try {
      const res = await axiosInstance.post("/api/auth/refresh", {
        refresh_token: savedRefresh,
      });
      const { access_token, refresh_token: newRefresh } = res.data;
      setToken(access_token);
      window.__elisa_token__ = access_token;
      if (newRefresh) localStorage.setItem(KEY_REFRESH, newRefresh);
      return access_token;
    } catch {
      logout();
      return null;
    }
  }, [token, logout]);

  // ── VERIFICAR TIMERS ───────────────────────────────────────────────────────

  const checkTimers = useCallback(() => {
    const now = Date.now();
    const lastClick = parseInt(localStorage.getItem(KEY_LAST_CLICK) || "0");
    const timer2Start = parseInt(localStorage.getItem(KEY_TIMER2_START) || "0");

    if (timer2Start > 0) {
      const elapsed2 = now - timer2Start;
      if (elapsed2 >= TIMER2_DURATION) {
        window.dispatchEvent(new CustomEvent("elisa:session-expired"));
        logout();
        return;
      }
      const remaining = TIMER2_DURATION - elapsed2;
      if (remaining <= 30 * 60 * 1000 && remaining > 29 * 60 * 1000) {
        window.dispatchEvent(
          new CustomEvent("elisa:session-warning", {
            detail: { minutes: Math.ceil(remaining / 60000) },
          }),
        );
      }
      return;
    }

    if (lastClick > 0) {
      const elapsed1 = now - lastClick;
      if (elapsed1 >= TIMER1_DURATION) {
        localStorage.setItem(KEY_TIMER2_START, String(now));
        window.dispatchEvent(
          new CustomEvent("elisa:session-warning", {
            detail: { minutes: Math.ceil(TIMER2_DURATION / 60000) },
          }),
        );
      }
    }
  }, [logout]);

  // ── REGISTRAR ACTIVIDAD ───────────────────────────────────────────────────

  const registerActivity = useCallback(() => {
    const now = Date.now();
    const timer2Start = parseInt(localStorage.getItem(KEY_TIMER2_START) || "0");
    localStorage.setItem(KEY_LAST_CLICK, String(now));
    if (timer2Start > 0) localStorage.removeItem(KEY_TIMER2_START);
  }, []);

  // ── INICIAR CICLOS ────────────────────────────────────────────────────────

  const startCycles = useCallback(() => {
    clearInterval(refreshIntervalRef.current);
    clearInterval(checkIntervalRef.current);

    // En mock no necesita renovar tokens con el backend
    if (!USE_MOCK) {
      refreshIntervalRef.current = setInterval(
        refreshAccessToken,
        TOKEN_REFRESH_MS,
      );
    }

    checkIntervalRef.current = setInterval(checkTimers, CHECK_INTERVAL);
  }, [refreshAccessToken, checkTimers]);

  // ── LOGIN ─────────────────────────────────────────────────────────────────

  const login = useCallback(
    (accessToken, refreshToken, userData) => {
      const now = Date.now();

      setToken(accessToken);
      setUser(userData);
      window.__elisa_token__ = accessToken;

      // Solo guarda refresh token si no es mock (en mock es un string fake)
      if (!USE_MOCK) {
        localStorage.setItem(KEY_REFRESH, refreshToken);
      }

      localStorage.setItem(KEY_LAST_CLICK, String(now));
      localStorage.removeItem(KEY_TIMER2_START);

      try {
        localStorage.setItem(
          KEY_USER,
          JSON.stringify({
            id: userData.id,
            cupe: userData.cupe,
            username: userData.username,
            first_name: userData.first_name,
            last_name: userData.last_name,
            email: userData.email,
            role: userData.role,
            role_name: userData.role_name,
            is_active: userData.is_active,
          }),
        );
      } catch {}

      startCycles();
    },
    [startCycles],
  );

  // ── INICIALIZACIÓN ────────────────────────────────────────────────────────

  useEffect(() => {
    const init = async () => {
      const savedUser = localStorage.getItem(KEY_USER);
      const lastClick = parseInt(localStorage.getItem(KEY_LAST_CLICK) || "0");
      const timer2Start = parseInt(
        localStorage.getItem(KEY_TIMER2_START) || "0",
      );
      const now = Date.now();

      if (!savedUser) {
        setIsLoading(false);
        return;
      }

      // Verifica timers antes de restaurar la sesión
      if (timer2Start > 0) {
        const elapsed2 = now - timer2Start;
        if (elapsed2 >= TIMER2_DURATION) {
          logout();
          setIsLoading(false);
          return;
        }
      } else if (lastClick > 0) {
        const elapsed1 = now - lastClick;
        if (elapsed1 >= TIMER1_DURATION) {
          const timer2StartTime = lastClick + TIMER1_DURATION;
          const elapsed2 = now - timer2StartTime;
          if (elapsed2 >= TIMER2_DURATION) {
            logout();
            setIsLoading(false);
            return;
          }
          localStorage.setItem(KEY_TIMER2_START, String(timer2StartTime));
        }
      }

      // ── MOCK: restaura sesión directamente sin llamar al backend ─────────
      if (USE_MOCK) {
        try {
          const parsedUser = JSON.parse(savedUser);
          const mockToken = "mock_access_token_restored_" + Date.now();
          setToken(mockToken);
          setUser(parsedUser);
          window.__elisa_token__ = mockToken;
          startCycles();
        } catch {
          logout();
        }
        setIsLoading(false);
        return;
      }

      // ── REAL: renueva el access_token con el refresh_token ───────────────
      const savedRefresh = localStorage.getItem(KEY_REFRESH);
      if (!savedRefresh) {
        logout();
        setIsLoading(false);
        return;
      }

      try {
        const parsedUser = JSON.parse(savedUser);
        const res = await axiosInstance.post("/api/auth/refresh", {
          refresh_token: savedRefresh,
        });
        const { access_token, refresh_token: newRefresh } = res.data;
        setToken(access_token);
        setUser(parsedUser);
        window.__elisa_token__ = access_token;
        if (newRefresh) localStorage.setItem(KEY_REFRESH, newRefresh);
        startCycles();
      } catch {
        logout();
      }

      setIsLoading(false);
    };

    init();
  }, []); // eslint-disable-line

  // ── ESCUCHAR CLICKS ───────────────────────────────────────────────────────

  useEffect(() => {
    if (!isAuthenticated) return;
    window.addEventListener("click", registerActivity);
    window.addEventListener("keydown", registerActivity);
    window.addEventListener("touchstart", registerActivity, { passive: true });
    return () => {
      window.removeEventListener("click", registerActivity);
      window.removeEventListener("keydown", registerActivity);
      window.removeEventListener("touchstart", registerActivity);
    };
  }, [isAuthenticated, registerActivity]);

  // ── SINCRONIZAR ENTRE PESTAÑAS ────────────────────────────────────────────

  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === KEY_LAST_CLICK && isAuthenticated) {
        localStorage.removeItem(KEY_TIMER2_START);
      }
      if (e.key === KEY_USER && !e.newValue && isAuthenticated) {
        logout();
      }
    };
    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, [isAuthenticated, logout]);

  // ── LIMPIAR AL DESMONTAR ──────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      clearInterval(refreshIntervalRef.current);
      clearInterval(checkIntervalRef.current);
    };
  }, []);

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isAuthenticated,
        isLoading,
        login,
        logout,
        refreshAccessToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// Necesario para Vite Fast Refresh
export default AuthProvider;
