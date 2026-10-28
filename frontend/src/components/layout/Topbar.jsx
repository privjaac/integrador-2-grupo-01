// ==============================================================================
// TOPBAR.JSX v4 — Sin position fixed, funciona con el layout sticky
// ==============================================================================

import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../ui/Toast";
import { getInternalNotifications, markInternalNotificationRead } from "../../api/notifications";

const ROUTE_TITLES = {
  "/dashboard": "Dashboard",
  "/clientes": "Clientes",
  "/usuarios": "Colaboradores",
  "/roles": "Roles y Jerarquías",
  "/catalogo": "Catálogo de Servicios",
  "/tareas": "Tareas",
};

export default function Topbar() {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const seenNotificationIds = useRef(null);
  const [notificationState, setNotificationState] = useState({ items: [], unread_count: 0 });
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notificationsError, setNotificationsError] = useState(false);

  useEffect(() => {
    if (!user) return undefined;
    let active = true;
    seenNotificationIds.current = null;
    const load = async () => {
      try {
        const result = await getInternalNotifications();
        if (active) {
          const nextIds = new Set(result.items.map((item) => item.id));
          if (seenNotificationIds.current) {
            result.items.filter((item) => !seenNotificationIds.current.has(item.id))
              .reverse().forEach((item) => showToast("info", item.title, item.message));
          }
          seenNotificationIds.current = nextIds;
          setNotificationState(result);
          setNotificationsError(false);
        }
      } catch {
        if (active) setNotificationsError(true);
      }
    };
    load();
    const interval = window.setInterval(load, 15000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [user, showToast]);

  async function openNotification(item) {
    if (!item.read_at) {
      try {
        await markInternalNotificationRead(item.id);
        setNotificationState((current) => ({
          ...current,
          unread_count: Math.max(0, current.unread_count - 1),
          items: current.items.map((notice) => notice.id === item.id
            ? { ...notice, read_at: new Date().toISOString() }
            : notice),
        }));
      } catch {
        setNotificationsError(true);
        return;
      }
    }
    setNotificationsOpen(false);
    navigate(`/tareas/detalle/${item.task_id}`);
  }

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
          <div style={{ position: "relative" }}>
            <button type="button" aria-label={`Notificaciones, ${notificationState.unread_count} sin leer`}
              aria-expanded={notificationsOpen} onClick={() => setNotificationsOpen((open) => !open)}
              style={{ position: "relative", border: "1px solid rgba(63,229,229,0.3)", borderRadius: 8, background: "#111427", color: "#3fe5e5", padding: "8px 10px", cursor: "pointer" }}>
              🔔
              {notificationState.unread_count > 0 && <span style={{ position: "absolute", top: -7, right: -7, minWidth: 18, height: 18, borderRadius: 10, background: "#ef4444", color: "white", fontSize: 11, lineHeight: "18px" }}>{notificationState.unread_count}</span>}
            </button>
            {notificationsOpen && <section aria-label="Notificaciones internas" style={{ position: "absolute", zIndex: 40, top: 42, right: 0, width: 340, maxHeight: 420, overflowY: "auto", background: "#111427", border: "1px solid rgba(63,229,229,0.25)", borderRadius: 10, boxShadow: "0 12px 32px #0009", padding: 12 }}>
              <strong style={{ color: "white" }}>Notificaciones</strong>
              {notificationsError && <p role="alert" style={{ color: "#fca5a5", fontSize: 13 }}>No fue posible cargar las notificaciones.</p>}
              {!notificationsError && notificationState.items.length === 0 && <p style={{ color: "#8892a4", fontSize: 13 }}>No tienes notificaciones.</p>}
              {notificationState.items.map((item) => <button key={item.id} type="button" onClick={() => openNotification(item)} style={{ width: "100%", textAlign: "left", marginTop: 8, padding: 10, border: 0, borderRadius: 7, cursor: "pointer", color: "#dbe4f0", background: item.read_at ? "#171b2e" : "rgba(63,229,229,0.12)" }}>
                <span style={{ display: "block", fontWeight: 600 }}>{item.title}</span>
                <span style={{ display: "block", color: "#aab2c5", fontSize: 12, marginTop: 3 }}>{item.message}</span>
                <time style={{ display: "block", color: "#778196", fontSize: 11, marginTop: 5 }}>{new Date(item.created_at).toLocaleString()}</time>
              </button>)}
            </section>}
          </div>
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
