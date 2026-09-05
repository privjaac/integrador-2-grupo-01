// ==============================================================================
// LOGINPAGE.JSX v2 — Página de login con llamada real al backend
//
// Cambios respecto a v1:
//   - Llama a loginApi() que devuelve { access_token, refresh_token, user }
//   - Pasa refresh_token al AuthContext (login ahora acepta 3 parámetros)
//   - Muestra toast de error si las credenciales son incorrectas
// ==============================================================================

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../../components/ui/Toast";
import { loginApi } from "../../api/auth";

export default function LoginPage() {
  const { login } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showPass, setShowPass] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      showToast(
        "warning",
        "CAMPOS REQUERIDOS",
        "Ingresá tu usuario y contraseña.",
      );
      return;
    }
    setIsLoading(true);
    try {
      const { access_token, refresh_token, user } = await loginApi(
        username,
        password,
      );
      // login() ahora acepta 3 parámetros: accessToken, refreshToken, userData
      login(access_token, refresh_token, user);
      navigate("/clientes", { replace: true });
    } catch (err) {
      showToast(
        "error",
        "ERROR DE ACCESO",
        err.userMessage || "Usuario o contraseña incorrectos.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        backgroundColor: "#05060f",
      }}
    >
      {/* Panel izquierdo — branding */}
      <div
        style={{
          flex: 1,
          background: "linear-gradient(135deg, #0b0d1a 0%, #0d0e2a 100%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "60px 50px",
          position: "relative",
          overflow: "hidden",
          borderRight: "1px solid rgba(63,229,229,0.15)",
        }}
      >
        {/* Grilla de fondo */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage:
              "linear-gradient(rgba(63,229,229,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(63,229,229,0.04) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(ellipse at 30% 50%, rgba(69,64,217,0.15) 0%, transparent 60%), radial-gradient(ellipse at 70% 20%, rgba(130,53,242,0.1) 0%, transparent 50%)",
          }}
        />

        <div
          style={{
            position: "relative",
            zIndex: 1,
            textAlign: "center",
            maxWidth: "400px",
          }}
        >
          {/* Logo */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "16px",
              marginBottom: "40px",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                width: "64px",
                height: "64px",
                background: "linear-gradient(135deg, #3fe5e5, #4540d9)",
                clipPath:
                  "polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: "'Orbitron', monospace",
                fontSize: "20px",
                fontWeight: 900,
                color: "#05060f",
                boxShadow: "0 0 30px rgba(63,229,229,0.5)",
              }}
            >
              EL
            </div>
            <span
              style={{
                fontFamily: "'Orbitron', monospace",
                fontSize: "28px",
                fontWeight: 700,
                background: "linear-gradient(135deg, #3fe5e5, #4540d9)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                letterSpacing: "3px",
              }}
            >
              ELomux
            </span>
          </div>

          <h1
            style={{
              fontFamily: "'Orbitron', monospace",
              fontSize: "42px",
              fontWeight: 900,
              background:
                "linear-gradient(135deg, #3fe5e5 0%, #4540d9 50%, #8235f2 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              letterSpacing: "8px",
              marginBottom: "12px",
            }}
          >
            ELISA
          </h1>
          <p
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: "11px",
              color: "#8892a4",
              letterSpacing: "2px",
              textTransform: "uppercase",
              marginBottom: "50px",
            }}
          >
            Estructura Lógica de Información y Servicios Administrativos
          </p>

          {/* Features */}
          {[
            { color: "#3fe5e5", text: "Gestión de clientes y contratos" },
            { color: "#8235f2", text: "Control de colaboradores y roles" },
            { color: "#4540d9", text: "Alertas de pagos y vencimientos" },
            { color: "#00ff88", text: "Dashboards e informes en tiempo real" },
          ].map((f, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "14px",
                padding: "12px 16px",
                background: "rgba(63,229,229,0.04)",
                border: "1px solid rgba(63,229,229,0.1)",
                borderRadius: "8px",
                marginBottom: "10px",
                textAlign: "left",
              }}
            >
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  background: f.color,
                  boxShadow: `0 0 8px ${f.color}`,
                  flexShrink: 0,
                }}
              />
              <span
                style={{ fontSize: "13px", color: "#c5cdd8", fontWeight: 500 }}
              >
                {f.text}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Panel derecho — formulario */}
      <div
        style={{
          width: "460px",
          backgroundColor: "#0b0d1a",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "60px 50px",
          position: "relative",
        }}
      >
        <h2
          style={{
            fontFamily: "'Orbitron', monospace",
            fontSize: "18px",
            fontWeight: 700,
            color: "white",
            letterSpacing: "2px",
            marginBottom: "6px",
          }}
        >
          INICIAR SESIÓN
        </h2>
        <p
          style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: "11px",
            color: "#8892a4",
            letterSpacing: "1px",
            marginBottom: "40px",
          }}
        >
          // Acceso al sistema ELISA v1.0
        </p>

        {/* Indicador dev */}
        {USE_MOCK && (
          <div
            style={{
              width: "100%",
              padding: "8px 14px",
              marginBottom: "24px",
              borderRadius: "6px",
              backgroundColor: "rgba(255,184,0,0.06)",
              border: "1px solid rgba(255,184,0,0.3)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "10px",
                color: "#ffb800",
                letterSpacing: "1px",
              }}
            >
              ⚡ MODO DEV — MOCK ACTIVO
            </span>
            <span
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "10px",
                color: "#3fe5e5",
              }}
            >
              elomux / elomux123
            </span>
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          noValidate
          style={{
            width: "100%",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          {/* Usuario */}
          <div>
            <label
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "11px",
                fontWeight: 700,
                letterSpacing: "2px",
                textTransform: "uppercase",
                color: "#3fe5e5",
                display: "block",
                marginBottom: "8px",
              }}
            >
              Usuario
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="nombre_usuario"
              autoComplete="username"
              style={{
                width: "100%",
                padding: "14px 18px",
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(63,229,229,0.2)",
                borderRadius: "8px",
                color: "white",
                fontFamily: "'Rajdhani', sans-serif",
                fontSize: "15px",
                outline: "none",
                transition: "all 0.3s",
                boxSizing: "border-box",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "#3fe5e5";
                e.target.style.backgroundColor = "rgba(63,229,229,0.05)";
                e.target.style.boxShadow = "0 0 0 3px rgba(63,229,229,0.1)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "rgba(63,229,229,0.2)";
                e.target.style.backgroundColor = "rgba(255,255,255,0.04)";
                e.target.style.boxShadow = "none";
              }}
            />
          </div>

          {/* Contraseña */}
          <div>
            <label
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "11px",
                fontWeight: 700,
                letterSpacing: "2px",
                textTransform: "uppercase",
                color: "#3fe5e5",
                display: "block",
                marginBottom: "8px",
              }}
            >
              Contraseña
            </label>
            <div style={{ position: "relative" }}>
              <input
                type={showPass ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                autoComplete="current-password"
                style={{
                  width: "100%",
                  padding: "14px 48px 14px 18px",
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(63,229,229,0.2)",
                  borderRadius: "8px",
                  color: "white",
                  fontFamily: "'Rajdhani', sans-serif",
                  fontSize: "15px",
                  outline: "none",
                  transition: "all 0.3s",
                  boxSizing: "border-box",
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = "#3fe5e5";
                  e.target.style.backgroundColor = "rgba(63,229,229,0.05)";
                  e.target.style.boxShadow = "0 0 0 3px rgba(63,229,229,0.1)";
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = "rgba(63,229,229,0.2)";
                  e.target.style.backgroundColor = "rgba(255,255,255,0.04)";
                  e.target.style.boxShadow = "none";
                }}
              />
              <button
                type="button"
                onClick={() => setShowPass((p) => !p)}
                style={{
                  position: "absolute",
                  right: "14px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "transparent",
                  border: "none",
                  color: "#8892a4",
                  cursor: "pointer",
                  padding: "4px",
                }}
              >
                {showPass ? "🙈" : "👁"}
              </button>
            </div>
          </div>

          {/* Botón submit */}
          <button
            type="submit"
            disabled={isLoading}
            style={{
              padding: "16px",
              background: isLoading
                ? "rgba(63,229,229,0.3)"
                : "linear-gradient(135deg, #3fe5e5, #4540d9)",
              border: "none",
              borderRadius: "8px",
              color: "#05060f",
              fontFamily: "'Orbitron', monospace",
              fontSize: "13px",
              fontWeight: 700,
              letterSpacing: "3px",
              cursor: isLoading ? "not-allowed" : "pointer",
              transition: "all 0.3s",
              marginTop: "10px",
            }}
            onMouseEnter={(e) => {
              if (!isLoading)
                e.currentTarget.style.boxShadow =
                  "0 0 30px rgba(63,229,229,0.5)";
            }}
            onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "none")}
          >
            {isLoading ? "VERIFICANDO..." : "INGRESAR AL SISTEMA"}
          </button>
        </form>

        {/* Badge SSL */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            marginTop: "24px",
            padding: "8px 16px",
            background: "rgba(0,255,136,0.06)",
            border: "1px solid rgba(0,255,136,0.2)",
            borderRadius: "20px",
            fontSize: "11px",
            color: "#00ff88",
            fontFamily: "'Share Tech Mono', monospace",
            letterSpacing: "1px",
          }}
        >
          <div
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: "#00ff88",
              animation: "pulse 2s infinite",
            }}
          />
          CONEXIÓN SEGURA SSL/TLS
        </div>

        <style>{`@keyframes pulse { 0%, 100% { opacity: 1 } 50% { opacity: 0.3 } }`}</style>
      </div>
    </div>
  );
}
