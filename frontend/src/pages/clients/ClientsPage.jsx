// ==============================================================================
// CLIENTSPAGE.JSX v6 — Columnas configurables con filtros dinámicos
//
// Novedades v6:
//   - Fila 2 de filtros dinámicos: aparece cuando hay columnas extra activas
//   - Cada columna extra activa genera su propio filtro
//   - Filtros de texto → input de búsqueda por contenido
//   - Filtros de select → dropdown (dominio, plan, frecuencia)
//   - Los filtros extra se aplican localmente sobre los datos ya cargados
// ==============================================================================

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";
import { getClients, deactivateClient } from "../../api/clients";
import {
  formatDate,
  formatDateRelative,
  isExpired,
} from "../../utils/formatDate";
import { formatPrice } from "../../utils/formatPrice";
import Table from "../../components/ui/Table";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import LoadingSpinner from "../../components/ui/LoadingSpinner";

const ITEMS_PER_PAGE = 10;

// Definición de columnas extra con su tipo de filtro
const EXTRA_COLUMNS = [
  {
    key: "document_type",
    label: "Tipo de documento",
    filter: "select",
    options: ["DNI", "RUC", "CE", "Pasaporte"],
  },
  { key: "document_number", label: "Nº de documento", filter: "text" },
  { key: "email", label: "Correo electrónico", filter: "text" },
  { key: "phone", label: "Teléfono", filter: "text" },
  { key: "base_price", label: "Precio base", filter: "none" },
  { key: "extra_price", label: "Precio extra", filter: "none" },
  { key: "features", label: "Características", filter: "text" },
  {
    key: "domain",
    label: "Dominio",
    filter: "select",
    options: ["Con dominio", "Sin dominio"],
  },
  { key: "domain_price", label: "Precio de dominio", filter: "none" },
  {
    key: "payment_frequency",
    label: "Frecuencia de pago",
    filter: "select",
    options: ["Mensual", "Anual"],
  },
  { key: "registration_date", label: "Fecha de registro", filter: "text" },
  { key: "delivery_date", label: "Fecha de entrega", filter: "text" },
  { key: "notes", label: "Notas / Comentarios", filter: "text" },
];

// KPI Card
function KpiCard({ label, value, color, icon, isLoading }) {
  return (
    <div
      style={{
        backgroundColor: "#0b0d1a",
        border: `1px solid ${color}30`,
        borderRadius: "0.75rem",
        padding: "1.25rem 1.5rem",
        position: "relative",
        overflow: "hidden",
        borderTop: `2px solid ${color}`,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: "1rem",
          right: "1rem",
          width: "36px",
          height: "36px",
          borderRadius: "0.5rem",
          backgroundColor: `${color}18`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color,
        }}
      >
        {icon}
      </div>
      <p
        style={{
          fontFamily: "'Share Tech Mono', monospace",
          fontSize: "9px",
          color: "#8892a4",
          letterSpacing: "0.15em",
          textTransform: "uppercase",
          margin: "0 0 0.5rem 0",
        }}
      >
        {label}
      </p>
      {isLoading ? (
        <div
          style={{
            height: "32px",
            width: "48px",
            borderRadius: "0.375rem",
            backgroundColor: `${color}18`,
            animation: "kpiPulse 1s ease-in-out infinite",
          }}
        />
      ) : (
        <p
          style={{
            fontFamily: "'Orbitron', monospace",
            fontSize: "26px",
            fontWeight: 700,
            color,
            margin: 0,
            lineHeight: 1,
            transition: "opacity 0.2s",
          }}
        >
          {value}
        </p>
      )}
      <style>{`@keyframes kpiPulse { 0%,100%{opacity:0.4} 50%{opacity:1} }`}</style>
    </div>
  );
}

export default function ClientsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [allClients, setAllClients] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);

  // Filtros base
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [plan, setPlan] = useState("");

  // Columnas extra activas
  const [visibleExtras, setVisibleExtras] = useState([]);
  const [showColumnPanel, setShowColumnPanel] = useState(false);

  // Filtros dinámicos de columnas extra — objeto { columnKey: valor }
  const [extraFilters, setExtraFilters] = useState({});

  // Modales
  const [bajaModal, setBajaModal] = useState({
    isOpen: false,
    clientId: null,
    clientName: "",
  });
  const [isDeactivating, setIsDeactivating] = useState(false);
  const [errorModal, setErrorModal] = useState({ isOpen: false, message: "" });
  const [successModal, setSuccessModal] = useState({
    isOpen: false,
    message: "",
  });

  // ── CARGA ──────────────────────────────────────────────────────────────────

  // Carga clientes con filtros
  const loadClients = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await getClients({
        search: search || undefined,
        status: status || undefined,
        plan: plan || undefined,
      });
      setAllClients(result.clients || result);
      setCurrentPage(1);
    } catch (err) {
      setErrorModal({
        isOpen: true,
        message: err.userMessage || "Error al cargar los clientes.",
      });
    } finally {
      setIsLoading(false);
    }
  }, [search, status, plan]);

  useEffect(() => {
    loadClients();
  }, [loadClients]);

  // ── FILTROS EXTRA — se aplican localmente ──────────────────────────────────

  const filteredClients = allClients.filter((client) => {
    for (const [key, value] of Object.entries(extraFilters)) {
      if (!value) continue;
      const val = value.toLowerCase();

      switch (key) {
        case "document_type":
          if (client.document_type?.toLowerCase() !== val) return false;
          break;
        case "document_number":
          if (!client.document_number?.toLowerCase().includes(val))
            return false;
          break;
        case "email":
          if (!client.email?.toLowerCase().includes(val)) return false;
          break;
        case "phone":
          if (!client.phone?.toLowerCase().includes(val)) return false;
          break;
        case "features":
          if (!client.features?.some((f) => f.name.toLowerCase().includes(val)))
            return false;
          break;
        case "domain":
          const hasDomain =
            client.domain_price_type && client.domain_price_type !== "ninguno";
          if (val === "con dominio" && !hasDomain) return false;
          if (val === "sin dominio" && hasDomain) return false;
          break;
        case "payment_frequency":
          if (client.payment_frequency?.toLowerCase() !== val) return false;
          break;
        case "registration_date":
          if (
            !formatDate(client.registration_date)?.toLowerCase().includes(val)
          )
            return false;
          break;
        case "delivery_date":
          if (!formatDate(client.delivery_date)?.toLowerCase().includes(val))
            return false;
          break;
        case "notes":
          if (!client.notes?.toLowerCase().includes(val)) return false;
          break;
        default:
          break;
      }
    }
    return true;
  });

  // ── KPIs ───────────────────────────────────────────────────────────────────

  // KPIs calculados desde los datos filtrados actuales
  const kpis = {
    total: allClients.length,
    activos: allClients.filter((c) => c.status === "activo").length,
    desarrollo: allClients.filter((c) => c.status === "desarrollo").length,
    inactivos: allClients.filter((c) => c.status === "inactivo").length,
    alquiler: allClients.filter((c) => c.plan === "alquiler").length,
    venta: allClients.filter((c) => c.plan === "venta").length,
  };

  // ── PAGINACIÓN (sobre filteredClients) ────────────────────────────────────

  const totalItems = filteredClients.length;
  const totalPages = Math.ceil(totalItems / ITEMS_PER_PAGE);
  const startIdx = (currentPage - 1) * ITEMS_PER_PAGE;
  const clients = filteredClients.slice(startIdx, startIdx + ITEMS_PER_PAGE);

  // ── HANDLERS ───────────────────────────────────────────────────────────────

  const toggleColumn = (key) => {
    setVisibleExtras((prev) => {
      const next = prev.includes(key)
        ? prev.filter((k) => k !== key)
        : [...prev, key];
      // Si se desactiva una columna → limpia su filtro
      if (prev.includes(key)) {
        setExtraFilters((f) => {
          const nf = { ...f };
          delete nf[key];
          return nf;
        });
      }
      return next;
    });
  };

  const setExtraFilter = (key, value) => {
    setExtraFilters((prev) => ({ ...prev, [key]: value }));
    setCurrentPage(1);
  };

  const clearAllFilters = () => {
    setSearch("");
    setStatus("");
    setPlan("");
    setExtraFilters({});
  };

  const hasExtraFilters = Object.values(extraFilters).some((v) => v);
  const hasAnyFilter = search || status || plan || hasExtraFilters;

  // ── DAR DE BAJA ────────────────────────────────────────────────────────────

  const handleBajaConfirm = async () => {
    setIsDeactivating(true);
    try {
      await deactivateClient(bajaModal.clientId);
      setBajaModal({ isOpen: false, clientId: null, clientName: "" });
      setSuccessModal({
        isOpen: true,
        message: `Cliente "${bajaModal.clientName}" dado de baja.`,
      });
      loadClients();
    } catch (err) {
      setBajaModal({ isOpen: false, clientId: null, clientName: "" });
      setErrorModal({
        isOpen: true,
        message: err.userMessage || "Error al dar de baja.",
      });
    } finally {
      setIsDeactivating(false);
    }
  };

  // ── RENDER CELDA EXTRA ─────────────────────────────────────────────────────

  const renderExtraCell = (client, key) => {
    switch (key) {
      case "document_type":
        return (
          <span style={{ color: "#c5cdd8", fontSize: "13px" }}>
            {client.document_type || "—"}
          </span>
        );
      case "document_number":
        return (
          <span
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              color: "#c5cdd8",
              fontSize: "12px",
            }}
          >
            {client.document_number || "—"}
          </span>
        );
      case "email":
        return (
          <span style={{ color: "#8892a4", fontSize: "13px" }}>
            {client.email || "—"}
          </span>
        );
      case "phone":
        return (
          <span style={{ color: "#c5cdd8", fontSize: "13px" }}>
            {client.phone || "—"}
          </span>
        );
      case "base_price":
        return (
          <span
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              color: "#3fe5e5",
              fontSize: "13px",
            }}
          >
            {client.base_price ? formatPrice(client.base_price) : "—"}
          </span>
        );
      case "extra_price":
        return (
          <span
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              color: "#3fe5e5",
              fontSize: "13px",
            }}
          >
            {formatPrice(client.extra_price || 0)}
          </span>
        );
      case "features":
        return client.features?.length > 0 ? (
          <div
            style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}
          >
            {client.features.map((f, i) => (
              <span
                key={i}
                style={{
                  fontSize: "11px",
                  color: "#3fe5e5",
                  fontFamily: "'Share Tech Mono', monospace",
                }}
              >
                · {f.name}
              </span>
            ))}
          </div>
        ) : (
          <span style={{ color: "#8892a4", fontSize: "13px" }}>
            Sin características
          </span>
        );
      case "domain":
        return (
          <Badge
            status={
              client.domain_price_type && client.domain_price_type !== "ninguno"
                ? "activo"
                : "inactivo"
            }
            dot={false}
          >
            {client.domain_price_type !== "ninguno"
              ? "Con dominio"
              : "Sin dominio"}
          </Badge>
        );
      case "domain_price": {
        if (!client.domain_price_type || client.domain_price_type === "ninguno")
          return <span style={{ color: "#8892a4", fontSize: "13px" }}>—</span>;
        const amt =
          client.domain_price_type === "200"
            ? 200
            : client.domain_custom_price || 0;
        return (
          <span
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              color: "#3fe5e5",
              fontSize: "13px",
            }}
          >
            {formatPrice(amt)}
          </span>
        );
      }
      case "payment_frequency":
        return (
          <Badge
            status={
              client.payment_frequency === "mensual" ? "mensual" : "anual"
            }
            dot={false}
          >
            {client.payment_frequency === "mensual" ? "Mensual" : "Anual"}
          </Badge>
        );
      case "registration_date":
        return (
          <span style={{ color: "#8892a4", fontSize: "13px" }}>
            {client.registration_date
              ? formatDate(client.registration_date)
              : "—"}
          </span>
        );
      case "delivery_date":
        return (
          <span style={{ color: "#8892a4", fontSize: "13px" }}>
            {client.delivery_date ? formatDate(client.delivery_date) : "—"}
          </span>
        );
      case "notes":
        return client.notes ? (
          <span
            style={{
              color: "#8892a4",
              fontSize: "12px",
              maxWidth: "180px",
              display: "block",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
            title={client.notes}
          >
            {client.notes}
          </span>
        ) : (
          <span style={{ color: "#374151" }}>—</span>
        );
      default:
        return <span style={{ color: "#8892a4" }}>—</span>;
    }
  };

  // Columnas que tienen filtro disponible
  const filterableExtras = visibleExtras.filter((key) => {
    const col = EXTRA_COLUMNS.find((c) => c.key === key);
    return col && col.filter !== "none";
  });

  const hasActions =
    can(user, "clients", "edit") || can(user, "clients", "delete");
  const totalCols = 7 + visibleExtras.length + (hasActions ? 1 : 0);

  // ── ESTILOS REUTILIZABLES ──────────────────────────────────────────────────

  const filterInputStyle = {
    padding: "0.5rem 0.75rem",
    borderRadius: "0.375rem",
    fontSize: "13px",
    color: "white",
    backgroundColor: "#1a1d30",
    border: "1px solid rgba(63,229,229,0.2)",
    outline: "none",
    fontFamily: "'Rajdhani', sans-serif",
    width: "100%",
  };

  return (
    <>
      {/* Panel lateral de columnas */}
      {showColumnPanel && (
        <div
          onClick={() => setShowColumnPanel(false)}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 40,
            backgroundColor: "rgba(5,6,15,0.6)",
            backdropFilter: "blur(2px)",
          }}
        />
      )}
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "300px",
          zIndex: 50,
          backgroundColor: "#0b0d1a",
          borderLeft: "1px solid rgba(63,229,229,0.2)",
          boxShadow: "-8px 0 32px rgba(0,0,0,0.4)",
          display: "flex",
          flexDirection: "column",
          transform: showColumnPanel ? "translateX(0)" : "translateX(100%)",
          transition: "transform 0.3s ease-in-out",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "1.25rem 1.5rem",
            borderBottom: "1px solid rgba(63,229,229,0.1)",
          }}
        >
          <div>
            <h3
              style={{
                fontFamily: "'Rajdhani', sans-serif",
                fontSize: "16px",
                fontWeight: 700,
                color: "white",
                margin: 0,
              }}
            >
              Columnas visibles
            </h3>
            <p
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "10px",
                color: "#8892a4",
                margin: "0.25rem 0 0 0",
              }}
            >
              {visibleExtras.length} de {EXTRA_COLUMNS.length} activas
            </p>
          </div>
          <button
            onClick={() => setShowColumnPanel(false)}
            style={{
              padding: "0.5rem",
              borderRadius: "0.375rem",
              background: "transparent",
              border: "none",
              color: "#8892a4",
              cursor: "pointer",
            }}
          >
            <svg
              width="18"
              height="18"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
        <div
          style={{
            margin: "1rem 1.5rem 0",
            padding: "0.75rem 1rem",
            borderRadius: "0.375rem",
            backgroundColor: "rgba(63,229,229,0.05)",
            border: "1px solid rgba(63,229,229,0.15)",
          }}
        >
          <p
            style={{
              fontFamily: "'Rajdhani', sans-serif",
              fontSize: "12px",
              color: "#8892a4",
              margin: 0,
            }}
          >
            Al activar una columna, aparece su filtro en la barra. Se resetean
            al recargar.
          </p>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: "1rem" }}>
          {EXTRA_COLUMNS.map((col) => (
            <label
              key={col.key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.875rem",
                padding: "0.75rem 1rem",
                borderRadius: "0.5rem",
                cursor: "pointer",
                backgroundColor: visibleExtras.includes(col.key)
                  ? "rgba(63,229,229,0.08)"
                  : "transparent",
                border: visibleExtras.includes(col.key)
                  ? "1px solid rgba(63,229,229,0.25)"
                  : "1px solid transparent",
                transition: "all 0.15s",
                marginBottom: "0.25rem",
              }}
            >
              <input
                type="checkbox"
                checked={visibleExtras.includes(col.key)}
                onChange={() => toggleColumn(col.key)}
                style={{
                  accentColor: "#3fe5e5",
                  width: "16px",
                  height: "16px",
                  flexShrink: 0,
                }}
              />
              <div style={{ flex: 1 }}>
                <span
                  style={{
                    fontFamily: "'Rajdhani', sans-serif",
                    fontSize: "14px",
                    fontWeight: 500,
                    color: visibleExtras.includes(col.key)
                      ? "#3fe5e5"
                      : "#c5cdd8",
                  }}
                >
                  {col.label}
                </span>
                {col.filter !== "none" && (
                  <span
                    style={{
                      fontFamily: "'Share Tech Mono', monospace",
                      fontSize: "9px",
                      color: "#8892a4",
                      display: "block",
                      marginTop: "2px",
                    }}
                  >
                    con filtro
                  </span>
                )}
              </div>
            </label>
          ))}
        </div>
        <div
          style={{
            padding: "1rem 1.5rem",
            borderTop: "1px solid rgba(63,229,229,0.1)",
            display: "flex",
            gap: "0.75rem",
          }}
        >
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setVisibleExtras([]);
              setExtraFilters({});
            }}
            disabled={visibleExtras.length === 0}
            style={{ flex: 1 }}
          >
            Limpiar todo
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setShowColumnPanel(false)}
            style={{ flex: 1 }}
          >
            Aplicar
          </Button>
        </div>
      </div>

      {/* Contenido principal */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: "1rem",
            flexWrap: "wrap",
          }}
        >
          <div>
            <h2
              style={{
                fontFamily: "'Rajdhani', sans-serif",
                fontSize: "1.25rem",
                fontWeight: 700,
                color: "white",
                letterSpacing: "0.05em",
                margin: 0,
              }}
            >
              Clientes registrados
            </h2>
            <p
              style={{
                color: "#8892a4",
                fontSize: "14px",
                margin: "0.25rem 0 0 0",
              }}
            >
              {isLoading
                ? "Cargando..."
                : `${totalItems} cliente${totalItems !== 1 ? "s" : ""} encontrado${totalItems !== 1 ? "s" : ""}`}
            </p>
          </div>
          {can(user, "clients", "create") && (
            <Button
              variant="primary"
              size="lg"
              onClick={() => navigate("/clientes/nuevo")}
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
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Nuevo cliente
            </Button>
          )}
        </div>

        {/* KPIs — contenedor siempre visible, números se actualizan al filtrar */}
        {
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(6, 1fr)",
              gap: "1rem",
            }}
          >
            <KpiCard
              label="Total"
              value={kpis.total}
              isLoading={isLoading}
              color="#3fe5e5"
              icon={
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
                    d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
              }
            />
            <KpiCard
              label="Activos"
              value={kpis.activos}
              isLoading={isLoading}
              color="#00ff88"
              icon={
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
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              }
            />
            <KpiCard
              label="En desarrollo"
              value={kpis.desarrollo}
              isLoading={isLoading}
              color="#ffb800"
              icon={
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
                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
              }
            />
            <KpiCard
              label="Inactivos"
              value={kpis.inactivos}
              isLoading={isLoading}
              color="#ff3366"
              icon={
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
                    d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
                  />
                </svg>
              }
            />
            <KpiCard
              label="Alquiler"
              value={kpis.alquiler}
              isLoading={isLoading}
              color="#4540d9"
              icon={
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
                    d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                  />
                </svg>
              }
            />
            <KpiCard
              label="Venta"
              value={kpis.venta}
              isLoading={isLoading}
              color="#8235f2"
              icon={
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
                    d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              }
            />
          </div>
        }

        {/* ── FILA 1 — Filtros base ─────────────────────────────────────── */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "0.75rem",
            padding: "1.25rem",
            borderRadius:
              visibleExtras.length > 0 ? "0.5rem 0.5rem 0 0" : "0.5rem",
            backgroundColor: "#111427",
            border: "1px solid rgba(63,229,229,0.12)",
            borderBottom: filterableExtras.length > 0 ? "none" : undefined,
          }}
        >
          <div
            style={{
              flex: 1,
              minWidth: "200px",
              position: "relative",
              display: "flex",
              alignItems: "center",
            }}
          >
            <svg
              width="16"
              height="16"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              style={{
                position: "absolute",
                left: "0.75rem",
                color: "#8892a4",
                pointerEvents: "none",
                zIndex: 1,
              }}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              type="text"
              placeholder="Buscar por nombre completo o CUPE..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setCurrentPage(1);
              }}
              style={{
                width: "100%",
                paddingLeft: "2.5rem",
                paddingRight: "1rem",
                paddingTop: "0.625rem",
                paddingBottom: "0.625rem",
                borderRadius: "0.375rem",
                fontSize: "14px",
                color: "white",
                backgroundColor: "#1a1d30",
                border: "1px solid rgba(63,229,229,0.2)",
                outline: "none",
                fontFamily: "'Rajdhani', sans-serif",
              }}
            />
          </div>

          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setCurrentPage(1);
            }}
            style={{
              padding: "0.625rem 0.875rem",
              borderRadius: "0.375rem",
              fontSize: "14px",
              color: status ? "white" : "#8892a4",
              backgroundColor: "#1a1d30",
              border: "1px solid rgba(63,229,229,0.2)",
              outline: "none",
              minWidth: "150px",
              fontFamily: "'Rajdhani', sans-serif",
              cursor: "pointer",
            }}
          >
            <option value="">Todos los estados</option>
            <option value="activo">Activo</option>
            <option value="desarrollo">En desarrollo</option>
            <option value="inactivo">Inactivo</option>
          </select>

          <select
            value={plan}
            onChange={(e) => {
              setPlan(e.target.value);
              setCurrentPage(1);
            }}
            style={{
              padding: "0.625rem 0.875rem",
              borderRadius: "0.375rem",
              fontSize: "14px",
              color: plan ? "white" : "#8892a4",
              backgroundColor: "#1a1d30",
              border: "1px solid rgba(63,229,229,0.2)",
              outline: "none",
              minWidth: "140px",
              fontFamily: "'Rajdhani', sans-serif",
              cursor: "pointer",
            }}
          >
            <option value="">Todos los planes</option>
            <option value="alquiler">Alquiler</option>
            <option value="venta">Venta</option>
          </select>

          {hasAnyFilter && (
            <Button variant="ghost" size="sm" onClick={clearAllFilters}>
              Limpiar filtros
            </Button>
          )}

          {/* Botón columnas */}
          <button
            onClick={() => setShowColumnPanel(true)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.625rem 1rem",
              borderRadius: "0.375rem",
              fontSize: "14px",
              fontFamily: "'Rajdhani', sans-serif",
              fontWeight: 600,
              cursor: "pointer",
              backgroundColor:
                visibleExtras.length > 0
                  ? "rgba(63,229,229,0.08)"
                  : "transparent",
              border: `1px solid ${visibleExtras.length > 0 ? "rgba(63,229,229,0.35)" : "rgba(63,229,229,0.2)"}`,
              color: visibleExtras.length > 0 ? "#3fe5e5" : "#8892a4",
              transition: "all 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "#3fe5e5";
              e.currentTarget.style.backgroundColor = "rgba(63,229,229,0.06)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color =
                visibleExtras.length > 0 ? "#3fe5e5" : "#8892a4";
              e.currentTarget.style.backgroundColor =
                visibleExtras.length > 0
                  ? "rgba(63,229,229,0.08)"
                  : "transparent";
            }}
          >
            <svg
              width="15"
              height="15"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2"
              />
            </svg>
            Columnas
            {visibleExtras.length > 0 && (
              <span
                style={{
                  backgroundColor: "#3fe5e5",
                  color: "#05060f",
                  fontSize: "10px",
                  fontWeight: 700,
                  borderRadius: "9999px",
                  padding: "0 0.375rem",
                  height: "18px",
                  display: "inline-flex",
                  alignItems: "center",
                }}
              >
                {visibleExtras.length}
              </span>
            )}
          </button>
        </div>

        {/* ── FILA 2 — Filtros dinámicos de columnas extra ──────────────── */}
        {filterableExtras.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "0.75rem",
              padding: "1rem 1.25rem",
              backgroundColor: "#0d0f1f",
              border: "1px solid rgba(63,229,229,0.12)",
              borderTop: "1px solid rgba(63,229,229,0.06)",
              borderRadius: "0 0 0.5rem 0.5rem",
            }}
          >
            {/* Indicador de fila de filtros extra */}
            <div
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                marginBottom: "0.25rem",
              }}
            >
              <span
                style={{
                  fontFamily: "'Share Tech Mono', monospace",
                  fontSize: "9px",
                  color: "#8892a4",
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                }}
              >
                Filtros de columnas extra
              </span>
              <div
                style={{
                  flex: 1,
                  height: "1px",
                  backgroundColor: "rgba(63,229,229,0.08)",
                }}
              />
              {hasExtraFilters && (
                <button
                  onClick={() => setExtraFilters({})}
                  style={{
                    fontFamily: "'Rajdhani', sans-serif",
                    fontSize: "11px",
                    color: "#ff3366",
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                    padding: "0",
                  }}
                >
                  Limpiar
                </button>
              )}
            </div>

            {/* Genera un filtro por cada columna extra filtrable activa */}
            {filterableExtras.map((key) => {
              const col = EXTRA_COLUMNS.find((c) => c.key === key);
              if (!col) return null;

              return (
                <div
                  key={key}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.25rem",
                    minWidth: "160px",
                    flex: "1",
                  }}
                >
                  <label
                    style={{
                      fontFamily: "'Share Tech Mono', monospace",
                      fontSize: "9px",
                      color: "#3fe5e5",
                      letterSpacing: "0.08em",
                      textTransform: "uppercase",
                    }}
                  >
                    {col.label}
                  </label>

                  {/* Select para columnas con opciones fijas */}
                  {col.filter === "select" ? (
                    <select
                      value={extraFilters[key] || ""}
                      onChange={(e) => setExtraFilter(key, e.target.value)}
                      style={{
                        ...filterInputStyle,
                        color: extraFilters[key] ? "white" : "#8892a4",
                      }}
                    >
                      <option value="">Todos</option>
                      {col.options.map((opt) => (
                        <option key={opt} value={opt.toLowerCase()}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  ) : (
                    /* Input de texto para búsqueda libre */
                    <input
                      type="text"
                      value={extraFilters[key] || ""}
                      onChange={(e) => setExtraFilter(key, e.target.value)}
                      placeholder={`Filtrar por ${col.label.toLowerCase()}...`}
                      style={filterInputStyle}
                    />
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Tabla */}
        {isLoading ? (
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              padding: "4rem 0",
            }}
          >
            <LoadingSpinner size="md" />
          </div>
        ) : (
          <>
            <Table aria-label="Lista de clientes">
              <Table.Head>
                <Table.Row>
                  <Table.HeadCell>CUPE</Table.HeadCell>
                  <Table.HeadCell>Cliente</Table.HeadCell>
                  <Table.HeadCell>Plan</Table.HeadCell>
                  <Table.HeadCell>Estado</Table.HeadCell>
                  <Table.HeadCell>Próximo pago</Table.HeadCell>
                  <Table.HeadCell>Total</Table.HeadCell>
                  {visibleExtras.map((key) => (
                    <Table.HeadCell key={key}>
                      {EXTRA_COLUMNS.find((c) => c.key === key)?.label}
                    </Table.HeadCell>
                  ))}
                  <Table.HeadCell>Acciones</Table.HeadCell>
                </Table.Row>
              </Table.Head>
              <Table.Body>
                {clients.length === 0 ? (
                  <Table.Empty
                    colSpan={totalCols}
                    message="No se encontraron clientes"
                  />
                ) : (
                  clients.map((client, idx) => (
                    <Table.Row key={client.id} index={startIdx + idx}>
                      <Table.Cell>
                        <span
                          style={{
                            fontFamily: "'Share Tech Mono', monospace",
                            color: "#3fe5e5",
                            fontSize: "12px",
                          }}
                        >
                          {client.cupe}
                        </span>
                      </Table.Cell>
                      <Table.Cell>
                        <div>
                          <p
                            style={{
                              fontWeight: 600,
                              color: "white",
                              margin: 0,
                            }}
                          >
                            {client.name}
                          </p>
                          <p
                            style={{
                              color: "#8892a4",
                              fontSize: "12px",
                              margin: "0.25rem 0 0 0",
                            }}
                          >
                            {client.web_type_name}
                          </p>
                        </div>
                      </Table.Cell>
                      <Table.Cell>
                        <Badge status={client.plan} />
                      </Table.Cell>
                      <Table.Cell>
                        <Badge status={client.status} />
                      </Table.Cell>
                      <Table.Cell>
                        <div>
                          <p
                            style={{
                              color: isExpired(client.next_payment_date)
                                ? "#ff3366"
                                : "white",
                              margin: 0,
                              fontSize: "14px",
                            }}
                          >
                            {formatDate(client.next_payment_date)}
                          </p>
                          <p
                            style={{
                              color: "#8892a4",
                              fontSize: "12px",
                              margin: "0.25rem 0 0 0",
                            }}
                          >
                            {formatDateRelative(client.next_payment_date)}
                          </p>
                        </div>
                      </Table.Cell>
                      <Table.Cell>
                        <span
                          style={{
                            fontFamily: "'Share Tech Mono', monospace",
                            color: "#3fe5e5",
                            fontWeight: 600,
                          }}
                        >
                          {formatPrice(client.total_price)}
                        </span>
                      </Table.Cell>
                      {visibleExtras.map((key) => (
                        <Table.Cell key={key}>
                          {renderExtraCell(client, key)}
                        </Table.Cell>
                      ))}
                      <Table.Cell>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "0.375rem",
                          }}
                        >
                          <button
                            onClick={() => navigate(`/clientes/${client.id}`)}
                            title="Ver detalle"
                            style={{
                              padding: "0.375rem",
                              borderRadius: "0.375rem",
                              background: "transparent",
                              border: "none",
                              color: "#8892a4",
                              cursor: "pointer",
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor =
                                "rgba(63,229,229,0.1)";
                              e.currentTarget.style.color = "#3fe5e5";
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor =
                                "transparent";
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
                                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                              />
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={1.5}
                                d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                              />
                            </svg>
                          </button>
                          {can(user, "clients", "edit") && (
                            <button
                              onClick={() =>
                                navigate(`/clientes/${client.id}/editar`)
                              }
                              title="Editar"
                              style={{
                                padding: "0.375rem",
                                borderRadius: "0.375rem",
                                background: "transparent",
                                border: "none",
                                color: "#8892a4",
                                cursor: "pointer",
                              }}
                              onMouseEnter={(e) => {
                                e.currentTarget.style.backgroundColor =
                                  "rgba(63,229,229,0.1)";
                                e.currentTarget.style.color = "#3fe5e5";
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.backgroundColor =
                                  "transparent";
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
                                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                                />
                              </svg>
                            </button>
                          )}
                          {can(user, "clients", "delete") &&
                            client.status !== "inactivo" && (
                              <button
                                onClick={() =>
                                  setBajaModal({
                                    isOpen: true,
                                    clientId: client.id,
                                    clientName: client.name,
                                  })
                                }
                                title="Dar de baja"
                                style={{
                                  padding: "0.375rem",
                                  borderRadius: "0.375rem",
                                  background: "transparent",
                                  border: "none",
                                  color: "#8892a4",
                                  cursor: "pointer",
                                }}
                                onMouseEnter={(e) => {
                                  e.currentTarget.style.backgroundColor =
                                    "rgba(255,51,102,0.1)";
                                  e.currentTarget.style.color = "#ff3366";
                                }}
                                onMouseLeave={(e) => {
                                  e.currentTarget.style.backgroundColor =
                                    "transparent";
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
                                    d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
                                  />
                                </svg>
                              </button>
                            )}
                        </div>
                      </Table.Cell>
                    </Table.Row>
                  ))
                )}
              </Table.Body>
            </Table>
            <Table.Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              totalItems={totalItems}
              itemsPerPage={ITEMS_PER_PAGE}
              onPageChange={setCurrentPage}
            />
          </>
        )}

        {/* Modales */}
        <Modal
          isOpen={bajaModal.isOpen}
          onClose={() =>
            setBajaModal({ isOpen: false, clientId: null, clientName: "" })
          }
          variant="confirm"
          size="sm"
        >
          <Modal.Header
            title="Dar de baja al cliente"
            onClose={() =>
              setBajaModal({ isOpen: false, clientId: null, clientName: "" })
            }
          />
          <Modal.Body>
            <p style={{ textAlign: "center" }}>
              ¿Dar de baja a{" "}
              <strong style={{ color: "white" }}>{bajaModal.clientName}</strong>
              ?
            </p>
            <p
              style={{
                textAlign: "center",
                fontSize: "12px",
                color: "#8892a4",
                marginTop: "0.5rem",
              }}
            >
              Sus datos se conservan en el sistema.
            </p>
          </Modal.Body>
          <Modal.Footer>
            <Button
              variant="secondary"
              onClick={() =>
                setBajaModal({ isOpen: false, clientId: null, clientName: "" })
              }
              disabled={isDeactivating}
            >
              Cancelar
            </Button>
            <Button
              variant="danger"
              onClick={handleBajaConfirm}
              isLoading={isDeactivating}
            >
              Sí, dar de baja
            </Button>
          </Modal.Footer>
        </Modal>
        <Modal
          isOpen={errorModal.isOpen}
          onClose={() => setErrorModal({ isOpen: false, message: "" })}
          variant="error"
          size="sm"
        >
          <Modal.Header
            title="Error"
            onClose={() => setErrorModal({ isOpen: false, message: "" })}
          />
          <Modal.Body>
            <p style={{ textAlign: "center" }}>{errorModal.message}</p>
          </Modal.Body>
          <Modal.Footer>
            <Button
              variant="secondary"
              onClick={() => setErrorModal({ isOpen: false, message: "" })}
            >
              Cerrar
            </Button>
          </Modal.Footer>
        </Modal>
        <Modal
          isOpen={successModal.isOpen}
          onClose={() => setSuccessModal({ isOpen: false, message: "" })}
          variant="success"
          size="sm"
        >
          <Modal.Header
            title="¡Listo!"
            onClose={() => setSuccessModal({ isOpen: false, message: "" })}
          />
          <Modal.Body>
            <p style={{ textAlign: "center" }}>{successModal.message}</p>
          </Modal.Body>
          <Modal.Footer>
            <Button
              variant="primary"
              onClick={() => setSuccessModal({ isOpen: false, message: "" })}
            >
              Aceptar
            </Button>
          </Modal.Footer>
        </Modal>
      </div>
    </>
  );
}
