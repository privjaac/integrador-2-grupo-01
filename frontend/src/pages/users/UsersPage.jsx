// ==============================================================================
// USERSPAGE.JSX v5 — Columnas configurables con filtros dinámicos
//
// Novedades v5:
//   - Fila 2 de filtros dinámicos por columnas extra activas
//   - Filtros de texto e input para cada columna filtrable
//   - Los filtros extra se aplican localmente
// ==============================================================================

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";
import { getCollaborators, toggleCollaboratorStatus } from "../../api/users";
import { getRoles } from "../../api/roles";
import { formatDate } from "../../utils/formatDate";
import Table from "../../components/ui/Table";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import LoadingSpinner from "../../components/ui/LoadingSpinner";

const ITEMS_PER_PAGE = 10;

const EXTRA_COLUMNS = [
  {
    key: "document_type",
    label: "Tipo de documento",
    filter: "select",
    options: ["DNI", "CE", "Pasaporte"],
  },
  { key: "document_number", label: "Nº de documento", filter: "text" },
  { key: "email", label: "Correo electrónico", filter: "text" },
  { key: "phone", label: "Teléfono", filter: "text" },
  { key: "city", label: "Ciudad", filter: "text" },
  { key: "username", label: "Usuario del sistema", filter: "text" },
];

export default function UsersPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [allCollaborators, setAllCollaborators] = useState([]);
  const [roles, setRoles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);

  // Filtros base
  const [search, setSearch] = useState("");
  const [roleId, setRoleId] = useState("");
  const [isActive, setIsActive] = useState("");

  // Columnas y filtros extra
  const [visibleExtras, setVisibleExtras] = useState([]);
  const [showColumnPanel, setShowColumnPanel] = useState(false);
  const [extraFilters, setExtraFilters] = useState({});

  // Modales
  const [confirmModal, setConfirmModal] = useState({
    isOpen: false,
    collaboratorId: null,
    collaboratorName: "",
    newStatus: null,
  });
  const [isToggling, setIsToggling] = useState(false);
  const [errorModal, setErrorModal] = useState({ isOpen: false, message: "" });
  const [successModal, setSuccessModal] = useState({
    isOpen: false,
    message: "",
  });

  useEffect(() => {
    getRoles()
      .then(setRoles)
      .catch(() => {});
  }, []);

  const loadCollaborators = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await getCollaborators({
        search: search || undefined,
        role_id: roleId || undefined,
        is_active: isActive !== "" ? isActive === "true" : undefined,
      });
      setAllCollaborators(result);
      setCurrentPage(1);
    } catch (err) {
      setErrorModal({
        isOpen: true,
        message: err.userMessage || "Error al cargar los colaboradores.",
      });
    } finally {
      setIsLoading(false);
    }
  }, [search, roleId, isActive]);

  useEffect(() => {
    loadCollaborators();
  }, [loadCollaborators]);

  // ── FILTROS EXTRA — aplicados localmente ──────────────────────────────────

  const filteredCollaborators = allCollaborators.filter((collab) => {
    for (const [key, value] of Object.entries(extraFilters)) {
      if (!value) continue;
      const val = value.toLowerCase();
      switch (key) {
        case "document_type":
          if (collab.document_type?.toLowerCase() !== val) return false;
          break;
        case "document_number":
          if (!collab.document_number?.toLowerCase().includes(val))
            return false;
          break;
        case "email":
          if (!collab.email?.toLowerCase().includes(val)) return false;
          break;
        case "phone":
          if (!collab.phone?.toLowerCase().includes(val)) return false;
          break;
        case "city":
          if (!collab.city?.toLowerCase().includes(val)) return false;
          break;
        case "username":
          if (!collab.username?.toLowerCase().includes(val)) return false;
          break;
        default:
          break;
      }
    }
    return true;
  });

  // ── PAGINACIÓN ─────────────────────────────────────────────────────────────

  const totalItems = filteredCollaborators.length;
  const totalPages = Math.ceil(totalItems / ITEMS_PER_PAGE);
  const startIdx = (currentPage - 1) * ITEMS_PER_PAGE;
  const collaborators = filteredCollaborators.slice(
    startIdx,
    startIdx + ITEMS_PER_PAGE,
  );

  // ── HANDLERS ───────────────────────────────────────────────────────────────

  const toggleColumn = (key) => {
    setVisibleExtras((prev) => {
      const next = prev.includes(key)
        ? prev.filter((k) => k !== key)
        : [...prev, key];
      if (prev.includes(key))
        setExtraFilters((f) => {
          const nf = { ...f };
          delete nf[key];
          return nf;
        });
      return next;
    });
  };

  const setExtraFilter = (key, value) => {
    setExtraFilters((prev) => ({ ...prev, [key]: value }));
    setCurrentPage(1);
  };

  const hasExtraFilters = Object.values(extraFilters).some((v) => v);
  const hasAnyFilter = search || roleId || isActive !== "" || hasExtraFilters;

  const clearAllFilters = () => {
    setSearch("");
    setRoleId("");
    setIsActive("");
    setExtraFilters({});
  };

  const handleToggleStatus = async () => {
    setIsToggling(true);
    try {
      await toggleCollaboratorStatus(
        confirmModal.collaboratorId,
        confirmModal.newStatus,
      );
      setConfirmModal({
        isOpen: false,
        collaboratorId: null,
        collaboratorName: "",
        newStatus: null,
      });
      setSuccessModal({
        isOpen: true,
        message: `Colaborador "${confirmModal.collaboratorName}" ${confirmModal.newStatus ? "activado" : "desactivado"}.`,
      });
      loadCollaborators();
    } catch (err) {
      setConfirmModal({
        isOpen: false,
        collaboratorId: null,
        collaboratorName: "",
        newStatus: null,
      });
      setErrorModal({
        isOpen: true,
        message: err.userMessage || "Error al cambiar el estado.",
      });
    } finally {
      setIsToggling(false);
    }
  };

  const renderExtraCell = (collab, key) => {
    switch (key) {
      case "document_type":
        return (
          <span style={{ color: "#c5cdd8", fontSize: "13px" }}>
            {collab.document_type || "—"}
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
            {collab.document_number || "—"}
          </span>
        );
      case "email":
        return (
          <span style={{ color: "#8892a4", fontSize: "13px" }}>
            {collab.email || "—"}
          </span>
        );
      case "phone":
        return (
          <span style={{ color: "#c5cdd8", fontSize: "13px" }}>
            {collab.phone || "—"}
          </span>
        );
      case "city":
        return (
          <span style={{ color: "#c5cdd8", fontSize: "13px" }}>
            {collab.city || "—"}
          </span>
        );
      case "username":
        return (
          <span
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              color: "#3fe5e5",
              fontSize: "12px",
            }}
          >
            {collab.username || "—"}
          </span>
        );
      default:
        return <span style={{ color: "#8892a4" }}>—</span>;
    }
  };

  const filterableExtras = visibleExtras.filter((key) => {
    const col = EXTRA_COLUMNS.find((c) => c.key === key);
    return col && col.filter !== "none";
  });

  const hasActions = can(user, "users", "edit") || can(user, "users", "delete");
  const totalCols = 7 + visibleExtras.length + (hasActions ? 1 : 0);

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
      {/* Panel lateral */}
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

      {/* Contenido */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
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
              Colaboradores ELOMUX
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
                : `${totalItems} colaborador${totalItems !== 1 ? "es" : ""} encontrado${totalItems !== 1 ? "s" : ""}`}
            </p>
          </div>
          {can(user, "users", "create") && (
            <Button
              variant="primary"
              size="lg"
              onClick={() => navigate("/usuarios/nuevo")}
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
              Nuevo colaborador
            </Button>
          )}
        </div>

        {/* Fila 1 — filtros base */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "0.75rem",
            padding: "1.25rem",
            borderRadius:
              filterableExtras.length > 0 ? "0.5rem 0.5rem 0 0" : "0.5rem",
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
              placeholder="Buscar por nombre completo, CUPE o email..."
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
            value={roleId}
            onChange={(e) => {
              setRoleId(e.target.value);
              setCurrentPage(1);
            }}
            style={{
              padding: "0.625rem 0.875rem",
              borderRadius: "0.375rem",
              fontSize: "14px",
              color: roleId ? "white" : "#8892a4",
              backgroundColor: "#1a1d30",
              border: "1px solid rgba(63,229,229,0.2)",
              outline: "none",
              minWidth: "150px",
              fontFamily: "'Rajdhani', sans-serif",
              cursor: "pointer",
            }}
          >
            <option value="">Todos los roles</option>
            {roles.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>

          <select
            value={isActive}
            onChange={(e) => {
              setIsActive(e.target.value);
              setCurrentPage(1);
            }}
            style={{
              padding: "0.625rem 0.875rem",
              borderRadius: "0.375rem",
              fontSize: "14px",
              color: isActive !== "" ? "white" : "#8892a4",
              backgroundColor: "#1a1d30",
              border: "1px solid rgba(63,229,229,0.2)",
              outline: "none",
              minWidth: "140px",
              fontFamily: "'Rajdhani', sans-serif",
              cursor: "pointer",
            }}
          >
            <option value="">Todos los estados</option>
            <option value="true">Activos</option>
            <option value="false">Inactivos</option>
          </select>

          {hasAnyFilter && (
            <Button variant="ghost" size="sm" onClick={clearAllFilters}>
              Limpiar filtros
            </Button>
          )}

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

        {/* Fila 2 — filtros dinámicos */}
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
                  }}
                >
                  Limpiar
                </button>
              )}
            </div>
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
            <Table aria-label="Lista de colaboradores">
              <Table.Head>
                <Table.Row>
                  <Table.HeadCell>CUPE</Table.HeadCell>
                  <Table.HeadCell>Colaborador</Table.HeadCell>
                  <Table.HeadCell>Rol</Table.HeadCell>
                  <Table.HeadCell>Área</Table.HeadCell>
                  <Table.HeadCell>Estado</Table.HeadCell>
                  <Table.HeadCell>Registrado</Table.HeadCell>
                  {visibleExtras.map((key) => (
                    <Table.HeadCell key={key}>
                      {EXTRA_COLUMNS.find((c) => c.key === key)?.label}
                    </Table.HeadCell>
                  ))}
                  {hasActions && <Table.HeadCell>Acciones</Table.HeadCell>}
                </Table.Row>
              </Table.Head>
              <Table.Body>
                {collaborators.length === 0 ? (
                  <Table.Empty
                    colSpan={totalCols}
                    message="No se encontraron colaboradores"
                  />
                ) : (
                  collaborators.map((collab, idx) => (
                    <Table.Row key={collab.id} index={startIdx + idx}>
                      <Table.Cell>
                        <span
                          style={{
                            fontFamily: "'Share Tech Mono', monospace",
                            color: "#3fe5e5",
                            fontSize: "12px",
                          }}
                        >
                          {collab.cupe}
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
                            {collab.first_name} {collab.last_name}
                          </p>
                          <p
                            style={{
                              color: "#8892a4",
                              fontSize: "12px",
                              margin: "0.25rem 0 0 0",
                            }}
                          >
                            {collab.username} · {collab.email}
                          </p>
                        </div>
                      </Table.Cell>
                      <Table.Cell>
                        <div>
                          <p
                            style={{
                              color: "white",
                              margin: 0,
                              fontSize: "14px",
                              fontWeight: 500,
                            }}
                          >
                            {collab.role_name}
                          </p>
                          <p
                            style={{
                              color: "#8892a4",
                              fontSize: "11px",
                              fontFamily: "'Share Tech Mono', monospace",
                              margin: "0.25rem 0 0 0",
                            }}
                          >
                            {collab.role}
                          </p>
                        </div>
                      </Table.Cell>
                      <Table.Cell>
                        <span style={{ color: "#c5cdd8", fontSize: "14px" }}>
                          {collab.work_area}
                        </span>
                      </Table.Cell>
                      <Table.Cell>
                        <Badge status={collab.is_active} />
                      </Table.Cell>
                      <Table.Cell>
                        <span style={{ color: "#8892a4", fontSize: "13px" }}>
                          {formatDate(collab.created_at)}
                        </span>
                      </Table.Cell>
                      {visibleExtras.map((key) => (
                        <Table.Cell key={key}>
                          {renderExtraCell(collab, key)}
                        </Table.Cell>
                      ))}
                      {hasActions && (
                        <Table.Cell>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "0.5rem",
                            }}
                          >
                            <button
                              onClick={() => navigate(`/usuarios/${collab.id}`)}
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
                            {can(user, "users", "edit") && (
                              <button
                                onClick={() =>
                                  navigate(`/usuarios/${collab.id}/editar`)
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
                            {can(user, "users", "delete") &&
                              collab.id !== user?.id && (
                                <button
                                  onClick={() =>
                                    setConfirmModal({
                                      isOpen: true,
                                      collaboratorId: collab.id,
                                      collaboratorName: `${collab.first_name} ${collab.last_name}`,
                                      newStatus: !collab.is_active,
                                    })
                                  }
                                  title={
                                    collab.is_active ? "Desactivar" : "Activar"
                                  }
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
                                      collab.is_active
                                        ? "rgba(255,51,102,0.1)"
                                        : "rgba(0,255,136,0.1)";
                                    e.currentTarget.style.color =
                                      collab.is_active ? "#ff3366" : "#00ff88";
                                  }}
                                  onMouseLeave={(e) => {
                                    e.currentTarget.style.backgroundColor =
                                      "transparent";
                                    e.currentTarget.style.color = "#8892a4";
                                  }}
                                >
                                  {collab.is_active ? (
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
                                  ) : (
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
                                  )}
                                </button>
                              )}
                          </div>
                        </Table.Cell>
                      )}
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
          isOpen={confirmModal.isOpen}
          onClose={() =>
            setConfirmModal({
              isOpen: false,
              collaboratorId: null,
              collaboratorName: "",
              newStatus: null,
            })
          }
          variant="confirm"
          size="sm"
        >
          <Modal.Header
            title={
              confirmModal.newStatus
                ? "Activar colaborador"
                : "Desactivar colaborador"
            }
            onClose={() =>
              setConfirmModal({
                isOpen: false,
                collaboratorId: null,
                collaboratorName: "",
                newStatus: null,
              })
            }
          />
          <Modal.Body>
            <p style={{ textAlign: "center" }}>
              ¿{confirmModal.newStatus ? "Activar" : "Desactivar"} a{" "}
              <strong style={{ color: "white" }}>
                {confirmModal.collaboratorName}
              </strong>
              ?
            </p>
          </Modal.Body>
          <Modal.Footer>
            <Button
              variant="secondary"
              onClick={() =>
                setConfirmModal({
                  isOpen: false,
                  collaboratorId: null,
                  collaboratorName: "",
                  newStatus: null,
                })
              }
              disabled={isToggling}
            >
              Cancelar
            </Button>
            <Button
              variant={confirmModal.newStatus ? "primary" : "danger"}
              onClick={handleToggleStatus}
              isLoading={isToggling}
            >
              {confirmModal.newStatus ? "Sí, activar" : "Sí, desactivar"}
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
