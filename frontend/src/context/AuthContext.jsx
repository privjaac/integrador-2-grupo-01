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

import { useState, useEffect, useCallback, useRef } from "react";
import axiosInstance from "../api/axios";
import { AuthContext } from "./AuthContextInstance";
import { isDefinitiveSessionFailure, withCoordinatedRefresh } from "../utils/sessionRefresh";

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

function safeUserSummary(data) {
  return {
    id: data.id, cupe: data.cupe, username: data.username,
    first_name: data.first_name, last_name: data.last_name, email: data.email,
    role: data.role, role_name: data.role_name, role_id: data.role_id,
    role_active: data.role_active, is_active: data.is_active,
    permissions: data.permissions,
  };
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sessionRestoreError, setSessionRestoreError] = useState(false);
  const [restoreAttempt, setRestoreAttempt] = useState(0);

  const refreshIntervalRef = useRef(null);
  const checkIntervalRef = useRef(null);

  const isAuthenticated = token !== null;
  const retrySessionRestore = useCallback(() => {
    setRestoreAttempt((attempt) => attempt + 1);
  }, []);

  // ── LOGOUT ────────────────────────────────────────────────────────────────

  const clearLocalSession = useCallback(() => {
    setToken(null);
    setUser(null);
    window.__elisa_token__ = null;
    localStorage.removeItem(KEY_USER);
    localStorage.removeItem(KEY_REFRESH);
    localStorage.removeItem(KEY_LAST_CLICK);
    localStorage.removeItem(KEY_TIMER2_START);
    setSessionRestoreError(false);
    clearInterval(refreshIntervalRef.current);
    clearInterval(checkIntervalRef.current);
  }, []);

  const logout = useCallback(async ({ localOnly = false } = {}) => {
    const savedRefresh = localStorage.getItem(KEY_REFRESH);
    if (!USE_MOCK && !localOnly && savedRefresh) {
      try {
        await axiosInstance.post("/api/auth/logout", { refresh_token: savedRefresh });
      } catch {
        return false;
      }
    }
    clearLocalSession();
    return true;
  }, [clearLocalSession]);

  // ── RENOVAR ACCESS TOKEN ───────────────────────────────────────────────────

  const refreshAccessToken = useCallback(async () => {
    // En modo mock — no hay backend, devuelve el token actual
    if (USE_MOCK) {
      return token;
    }

    if (!localStorage.getItem(KEY_REFRESH)) {
      await logout({ localOnly: true });
      return null;
    }

    try {
      const restored = await withCoordinatedRefresh(
        () => localStorage.getItem(KEY_REFRESH),
        async (savedRefresh) => {
          if (!savedRefresh) return null;
          const res = await axiosInstance.post("/api/auth/refresh", {
            refresh_token: savedRefresh,
          }, { skipAuthRefresh: true });
          const { access_token, refresh_token: newRefresh } = res.data;
          if (newRefresh) localStorage.setItem(KEY_REFRESH, newRefresh);
          const profile = await axiosInstance.get("/api/users/me", {
            headers: { Authorization: `Bearer ${access_token}` },
            skipAuthRefresh: true,
          });
          return { accessToken: access_token, user: safeUserSummary(profile.data) };
        },
      );
      if (!restored) {
        await logout({ localOnly: true });
        return null;
      }
      setToken(restored.accessToken);
      setUser(restored.user);
      setSessionRestoreError(false);
      window.__elisa_token__ = restored.accessToken;
      localStorage.setItem(KEY_USER, JSON.stringify(restored.user));
      return restored.accessToken;
    } catch (error) {
      if (isDefinitiveSessionFailure(error)) {
        await logout({ localOnly: true });
      }
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
  }, []);

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
      setSessionRestoreError(false);
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
            role_id: userData.role_id,
            permissions: userData.permissions,
          }),
        );
      } catch {
        // Local storage may be unavailable in restricted browser contexts.
      }

      startCycles();
    },
    [startCycles],
  );

  // ── INICIALIZACIÓN ────────────────────────────────────────────────────────

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      setSessionRestoreError(false);
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
          logout({ localOnly: true });
          setIsLoading(false);
          return;
        }
      } else if (lastClick > 0) {
        const elapsed1 = now - lastClick;
        if (elapsed1 >= TIMER1_DURATION) {
          const timer2StartTime = lastClick + TIMER1_DURATION;
          const elapsed2 = now - timer2StartTime;
          if (elapsed2 >= TIMER2_DURATION) {
            logout({ localOnly: true });
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
          logout({ localOnly: true });
        }
        setIsLoading(false);
        return;
      }

      // ── REAL: renueva el access_token con el refresh_token ───────────────
      const savedRefresh = localStorage.getItem(KEY_REFRESH);
      if (!savedRefresh) {
        logout({ localOnly: true });
        setIsLoading(false);
        return;
      }

      try {
        const restored = await withCoordinatedRefresh(
          () => localStorage.getItem(KEY_REFRESH),
          async (currentRefresh) => {
            if (!currentRefresh) {
              const missingRefresh = new Error("Missing refresh token");
              missingRefresh.response = { status: 401 };
              throw missingRefresh;
            }
            const res = await axiosInstance.post("/api/auth/refresh", {
              refresh_token: currentRefresh,
            }, { skipAuthRefresh: true });
            const { access_token, refresh_token: newRefresh } = res.data;
            if (newRefresh) localStorage.setItem(KEY_REFRESH, newRefresh);
            const profile = await axiosInstance.get("/api/users/me", {
              headers: { Authorization: `Bearer ${access_token}` },
              skipAuthRefresh: true,
            });
            const parsedUser = JSON.parse(savedUser);
            return {
              accessToken: access_token,
              user: { ...parsedUser, ...safeUserSummary(profile.data) },
            };
          },
        );
        if (!restored) {
          logout({ localOnly: true });
          setIsLoading(false);
          return;
        }
        setToken(restored.accessToken);
        setUser(restored.user);
        window.__elisa_token__ = restored.accessToken;
        localStorage.setItem(KEY_USER, JSON.stringify(restored.user));
        startCycles();
      } catch (error) {
        if (isDefinitiveSessionFailure(error)) {
          logout({ localOnly: true });
        } else {
          setSessionRestoreError(true);
        }
      }

      setIsLoading(false);
    };

    init();
  }, [restoreAttempt]); // eslint-disable-line react-hooks/exhaustive-deps

  // Si una solicitud normal recibe 401, intenta una única rotación y repite
  // esa solicitud. Los 403 y los endpoints de autenticación no se reintentan.
  useEffect(() => {
    const interceptorId = axiosInstance.interceptors.response.use(
      (response) => response,
      async (error) => {
        const request = error.config;
        const isAuthEndpoint = request?.url?.startsWith("/api/auth/");
        if (
          error.response?.status !== 401
          || !request
          || request.skipAuthRefresh
          || request.__elisaAuthRetried
          || isAuthEndpoint
        ) {
          return Promise.reject(error);
        }

        request.__elisaAuthRetried = true;
        const newAccessToken = await refreshAccessToken();
        if (newAccessToken) {
          request.headers = request.headers || {};
          request.headers.Authorization = `Bearer ${newAccessToken}`;
          return axiosInstance(request);
        }
        if (!localStorage.getItem(KEY_REFRESH)) {
          window.dispatchEvent(new CustomEvent("elisa:session-expired", {
            detail: { reason: "invalid" },
          }));
        }
        return Promise.reject(error);
      },
    );
    return () => axiosInstance.interceptors.response.eject(interceptorId);
  }, [refreshAccessToken]);

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
        logout({ localOnly: true });
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
        sessionRestoreError,
        login,
        logout,
        retrySessionRestore,
        refreshAccessToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// Necesario para Vite Fast Refresh
export default AuthProvider;
