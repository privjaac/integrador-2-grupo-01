// ==============================================================================
// TOPBAR.JSX v4 — Sin position fixed, funciona con el layout sticky
// ==============================================================================

import { useLocation } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

const ROUTE_TITLES = {
  "/dashboard": "Dashboard",
  "/clientes": "Clientes",
  "/usuarios": "Colaboradores",
  "/roles": "Roles y Jerarquías",
  "/catalogo": "Catálogo de Servicios",
};

export default function Topbar() {
  const { user } = useAuth();
  const location = useLocation();

  const getPageTitle = () => {
    const path = location.pathname;
    if (ROUTE_TITLES[path]) return ROUTE_TITLES[path];
    const basePath = "/" + path.split("/")[1];
    const baseTitle = ROUTE_TITLES[basePath];
    if (baseTitle) {
      if (path.includes("/nuevo")) return `${baseTitle} / Nuevo`;
      if (path.includes("/editar")) return `${baseTitle} / Editar`;
      return baseTitle;
    }
    return "ELISA";
  };

  return (
    <header
      style={{
        height: "56px",
        width: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        paddingLeft: "1.5rem",
        paddingRight: "1.5rem",
        backgroundColor: "rgba(11,13,26,0.97)",
        borderBottom: "1px solid rgba(63,229,229,0.10)",
        backdropFilter: "blur(10px)",
        flexShrink: 0,
      }}
    >
      {/* Título */}
      <h1
        style={{
          fontFamily: "'Rajdhani', sans-serif",
          fontSize: "1rem",
          fontWeight: 600,
          color: "white",
          letterSpacing: "0.05em",
          margin: 0,
        }}
      >
        {getPageTitle()}
      </h1>

      {/* Info del usuario */}
      {user && (
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-end",
            }}
          >
            <span
              style={{
                fontFamily: "'Rajdhani', sans-serif",
                fontSize: "12px",
                fontWeight: 600,
                color: "white",
              }}
            >
              {user.first_name} {user.last_name}
            </span>
            <span
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                color: "#8892a4",
                fontSize: "10px",
              }}
            >
              {user.role_name}
            </span>
          </div>
          <div style={{ position: "relative" }}>
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background:
                  "linear-gradient(135deg, rgba(63,229,229,0.2), rgba(69,64,217,0.2))",
                border: "1px solid rgba(63,229,229,0.3)",
                color: "#3fe5e5",
                fontFamily: "'Orbitron', monospace",
                fontSize: "11px",
                fontWeight: 700,
              }}
            >
              {user.first_name?.[0]}
              {user.last_name?.[0]}
            </div>
            <span
              style={{
                position: "absolute",
                bottom: 0,
                right: 0,
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                backgroundColor: "#00ff88",
                border: "2px solid #0b0d1a",
              }}
            />
          </div>
        </div>
      )}
    </header>
  );
}
