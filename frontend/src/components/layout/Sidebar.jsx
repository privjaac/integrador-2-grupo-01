// ==============================================================================
// SIDEBAR.JSX — Navegación lateral del sistema ELISA
//
// Muestra solo los módulos a los que el usuario tiene acceso según su rol.
// ==============================================================================

import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";

const NAV_ITEMS = [
  {
    section: "Principal",
    items: [
      {
        path: "/dashboard",
        label: "Dashboard",
        module: null, // visible para todos
        icon: (
          <svg
            width="18"
            height="18"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="3" y="3" width="7" height="7" />
            <rect x="14" y="3" width="7" height="7" />
            <rect x="14" y="14" width="7" height="7" />
            <rect x="3" y="14" width="7" height="7" />
          </svg>
        ),
      },
      {
        path: "/clientes",
        label: "Clientes",
        module: "clients",
        icon: (
          <svg
            width="18"
            height="18"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        ),
      },
    ],
  },
  {
    section: "Gestión",
    items: [
      {
        path: "/usuarios",
        label: "Colaboradores",
        module: "users",
        icon: (
          <svg
            width="18"
            height="18"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        ),
      },
      {
        path: "/roles",
        label: "Roles",
        module: "roles",
        icon: (
          <svg
            width="18"
            height="18"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        ),
      },
      {
        path: "/catalogo",
        label: "Catálogos",
        module: "catalog",
        icon: (
          <svg
            width="18"
            height="18"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        ),
      },
    ],
  },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const initials = user
    ? `${user.first_name?.[0] || ""}${user.last_name?.[0] || ""}`.toUpperCase()
    : "EL";

  return (
    <div
      style={{
        width: "256px",
        minHeight: "100vh",
        backgroundColor: "#0b0d1a",
        borderRight: "1px solid rgba(63,229,229,0.1)",
        display: "flex",
        flexDirection: "column",
        flexShrink: 0,
        position: "relative",
      }}
    >
      {/* Línea superior decorativa */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: "1px",
          background:
            "linear-gradient(90deg, transparent, #3fe5e5, transparent)",
        }}
      />

      {/* Header — logo */}
      <div
        style={{
          padding: "24px 20px 20px",
          borderBottom: "1px solid rgba(63,229,229,0.08)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            marginBottom: "4px",
          }}
        >
          <div
            style={{
              width: "38px",
              height: "38px",
              background: "linear-gradient(135deg, #3fe5e5, #4540d9)",
              clipPath:
                "polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "'Orbitron', monospace",
              fontSize: "11px",
              fontWeight: 900,
              color: "#05060f",
              flexShrink: 0,
            }}
          >
            EL
          </div>
          <span
            style={{
              fontFamily: "'Orbitron', monospace",
              fontSize: "16px",
              fontWeight: 700,
              color: "white",
              letterSpacing: "2px",
            }}
          >
            ELomux
          </span>
        </div>
        <p
          style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: "10px",
            color: "#3fe5e5",
            letterSpacing: "3px",
            textTransform: "uppercase",
            paddingLeft: "50px",
            margin: 0,
          }}
        >
          ELISA v1.0
        </p>
      </div>

      {/* Navegación */}
      <nav style={{ flex: 1, paddingBottom: "1rem", overflowY: "auto" }}>
        {NAV_ITEMS.map((section) => {
          // Filtra los items según permisos del usuario
          const visibleItems = section.items.filter((item) => {
            if (!item.module) return true; // Dashboard visible para todos
            return can(user, item.module, "view");
          });
          if (visibleItems.length === 0) return null;

          return (
            <div key={section.section}>
              <p
                style={{
                  fontFamily: "'Share Tech Mono', monospace",
                  fontSize: "9px",
                  letterSpacing: "3px",
                  textTransform: "uppercase",
                  color: "rgba(136,146,164,0.4)",
                  padding: "20px 20px 8px",
                  margin: 0,
                }}
              >
                {section.section}
              </p>
              {visibleItems.map((item) => {
                const isActive =
                  location.pathname === item.path ||
                  (item.path !== "/dashboard" &&
                    location.pathname.startsWith(item.path));

                return (
                  <button
                    key={item.path}
                    onClick={() => navigate(item.path)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      padding: "10px 20px",
                      width: "100%",
                      cursor: "pointer",
                      border: "none",
                      borderLeft: `2px solid ${isActive ? "#3fe5e5" : "transparent"}`,
                      backgroundColor: isActive
                        ? "rgba(63,229,229,0.08)"
                        : "transparent",
                      color: isActive ? "#3fe5e5" : "#8892a4",
                      fontSize: "14px",
                      fontWeight: 500,
                      fontFamily: "'Rajdhani', sans-serif",
                      textAlign: "left",
                      transition: "all 0.2s",
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.color = "white";
                        e.currentTarget.style.backgroundColor =
                          "rgba(63,229,229,0.04)";
                        e.currentTarget.style.borderLeftColor =
                          "rgba(63,229,229,0.3)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.color = "#8892a4";
                        e.currentTarget.style.backgroundColor = "transparent";
                        e.currentTarget.style.borderLeftColor = "transparent";
                      }
                    }}
                  >
                    <span
                      style={{
                        width: "20px",
                        height: "20px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      {item.icon}
                    </span>
                    {item.label}
                  </button>
                );
              })}
            </div>
          );
        })}
      </nav>

      {/* Footer — usuario + logout */}
      <div
        style={{
          padding: "16px 20px",
          borderTop: "1px solid rgba(63,229,229,0.08)",
          display: "flex",
          alignItems: "center",
          gap: "12px",
        }}
      >
        <div
          style={{
            width: "34px",
            height: "34px",
            borderRadius: "50%",
            background: "linear-gradient(135deg, #4540d9, #8235f2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "'Orbitron', monospace",
            fontSize: "12px",
            fontWeight: 700,
            flexShrink: 0,
            border: "1px solid rgba(63,229,229,0.2)",
          }}
        >
          {initials}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p
            style={{
              fontSize: "13px",
              fontWeight: 600,
              color: "white",
              margin: 0,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {user?.first_name} {user?.last_name}
          </p>
          <p
            style={{
              fontSize: "10px",
              color: "#3fe5e5",
              fontFamily: "'Share Tech Mono', monospace",
              letterSpacing: "1px",
              margin: 0,
            }}
          >
            {user?.role_name?.toUpperCase() || user?.role}
          </p>
        </div>
        <button
          onClick={handleLogout}
          title="Cerrar sesión"
          style={{
            padding: "0.375rem",
            borderRadius: "0.375rem",
            background: "transparent",
            border: "none",
            color: "#8892a4",
            cursor: "pointer",
            flexShrink: 0,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = "rgba(255,51,102,0.1)";
            e.currentTarget.style.color = "#ff3366";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = "transparent";
            e.currentTarget.style.color = "#8892a4";
          }}
        >
          <svg
            width="16"
            height="16"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
