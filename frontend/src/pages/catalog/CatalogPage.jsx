// ==============================================================================
// CATALOGPAGE.JSX v3 — Cards en grilla 3x3 como el mockup HTML + paginación
//
// Diseño según mockup:
//   - Grilla de 3 columnas con cards para tipos de web y características
//   - Cada card muestra nombre + precio alquiler (púrpura) + precio venta (cyan)
//   - Botón editar abajo a la derecha de cada card
//   - Paginación de 9 items por página
//   - Panel lateral para crear/editar (igual que antes)
//   - Tabs para alternar entre tipos de web y características
// ==============================================================================

import { useState, useEffect } from "react";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";
import { formatPrice } from "../../utils/formatPrice";
import {
  getWebTypes,
  createWebType,
  updateWebType,
  getWebFeatures,
  createWebFeature,
  updateWebFeature,
} from "../../api/catalog";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Modal from "../../components/ui/Modal";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import Badge from "../../components/ui/Badge";

const ITEMS_PER_PAGE = 9;
const INITIAL_TYPE_FORM = {
  name: "",
  base_price_rent: "",
  base_price_sale: "",
  is_active: true,
};
const INITIAL_FEATURE_FORM = {
  name: "",
  extra_price: "",
  web_type_ids: [],
  is_active: true,
};

// ── COMPONENTE PAGINACIÓN ─────────────────────────────────────────────────────

function Pagination({
  currentPage,
  totalPages,
  totalItems,
  itemsPerPage,
  onPageChange,
}) {
  if (totalPages <= 1) return null;
  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalItems);
  const getPages = () => {
    const pages = [];
    let start = Math.max(1, currentPage - 2);
    let end = Math.min(totalPages, start + 4);
    if (end - start < 4) start = Math.max(1, end - 4);
    for (let i = start; i <= end; i++) pages.push(i);
    return pages;
  };
  const btnStyle = (isActive, isDisabled = false) => ({
    padding: "0.375rem 0.75rem",
    borderRadius: "0.375rem",
    fontSize: "13px",
    fontFamily: "'Rajdhani', sans-serif",
    fontWeight: isActive ? 600 : 400,
    cursor: isDisabled ? "not-allowed" : "pointer",
    border: isActive
      ? "1px solid rgba(63,229,229,0.4)"
      : "1px solid rgba(63,229,229,0.15)",
    backgroundColor: isActive ? "rgba(63,229,229,0.12)" : "transparent",
    color: isActive ? "#3fe5e5" : isDisabled ? "#374151" : "#8892a4",
    transition: "all 0.15s",
    minWidth: "36px",
    textAlign: "center",
  });
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "1rem 0",
        flexWrap: "wrap",
        gap: "0.75rem",
      }}
    >
      <p
        style={{
          color: "#8892a4",
          fontSize: "13px",
          fontFamily: "'Rajdhani', sans-serif",
          margin: 0,
        }}
      >
        Mostrando{" "}
        <span style={{ color: "white", fontWeight: 600 }}>
          {startItem}–{endItem}
        </span>{" "}
        de <span style={{ color: "white", fontWeight: 600 }}>{totalItems}</span>{" "}
        registros
      </p>
      <div style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          style={btnStyle(false, currentPage === 1)}
        >
          ‹
        </button>
        {getPages().map((n) => (
          <button
            key={n}
            onClick={() => onPageChange(n)}
            style={btnStyle(n === currentPage)}
          >
            {n}
          </button>
        ))}
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          style={btnStyle(false, currentPage === totalPages)}
        >
          ›
        </button>
      </div>
    </div>
  );
}

export default function CatalogPage() {
  const { user } = useAuth();

  const [webTypes, setWebTypes] = useState([]);
  const [webFeatures, setWebFeatures] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("types");

  // Paginación separada para cada tab
  const [typesPage, setTypesPage] = useState(1);
  const [featuresPage, setFeaturesPage] = useState(1);

  // Panel formulario — tipos
  const [showTypeForm, setShowTypeForm] = useState(false);
  const [editingType, setEditingType] = useState(null);
  const [typeForm, setTypeForm] = useState(INITIAL_TYPE_FORM);
  const [typeErrors, setTypeErrors] = useState({});
  const [isSavingType, setIsSavingType] = useState(false);

  // Panel formulario — características
  const [showFeatureForm, setShowFeatureForm] = useState(false);
  const [editingFeature, setEditingFeature] = useState(null);
  const [featureForm, setFeatureForm] = useState(INITIAL_FEATURE_FORM);
  const [featureErrors, setFeatureErrors] = useState({});
  const [isSavingFeature, setIsSavingFeature] = useState(false);

  const [errorModal, setErrorModal] = useState({ isOpen: false, message: "" });
  const [successModal, setSuccessModal] = useState({
    isOpen: false,
    message: "",
  });

  // ── CARGA ──────────────────────────────────────────────────────────────────

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [types, features] = await Promise.all([
        getWebTypes(),
        getWebFeatures(),
      ]);
      setWebTypes(types);
      setWebFeatures(features);
    } catch (err) {
      setErrorModal({
        isOpen: true,
        message: err.userMessage || "Error al cargar el catálogo.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // ── PAGINACIÓN ─────────────────────────────────────────────────────────────

  const totalTypePages = Math.ceil(webTypes.length / ITEMS_PER_PAGE);
  const totalFeaturePages = Math.ceil(webFeatures.length / ITEMS_PER_PAGE);
  const pagedTypes = webTypes.slice(
    (typesPage - 1) * ITEMS_PER_PAGE,
    typesPage * ITEMS_PER_PAGE,
  );
  const pagedFeatures = webFeatures.slice(
    (featuresPage - 1) * ITEMS_PER_PAGE,
    featuresPage * ITEMS_PER_PAGE,
  );

  // ── HANDLERS TIPOS ─────────────────────────────────────────────────────────

  const handleNewType = () => {
    setEditingType(null);
    setTypeForm(INITIAL_TYPE_FORM);
    setTypeErrors({});
    setShowTypeForm(true);
    setShowFeatureForm(false);
  };
  const handleEditType = (type) => {
    setEditingType(type);
    setTypeForm({
      name: type.name,
      base_price_rent: type.base_price_rent,
      base_price_sale: type.base_price_sale,
      is_active: type.is_active,
    });
    setTypeErrors({});
    setShowTypeForm(true);
    setShowFeatureForm(false);
  };
  const handleTypeChange = (e) => {
    const { name, value, type, checked } = e.target;
    setTypeForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
    if (typeErrors[name]) setTypeErrors((prev) => ({ ...prev, [name]: "" }));
  };
  const validateTypeForm = () => {
    const e = {};
    if (!typeForm.name.trim()) e.name = "El nombre es requerido.";
    if (!typeForm.base_price_rent || Number(typeForm.base_price_rent) <= 0)
      e.base_price_rent = "Ingresá un precio válido.";
    if (!typeForm.base_price_sale || Number(typeForm.base_price_sale) <= 0)
      e.base_price_sale = "Ingresá un precio válido.";
    setTypeErrors(e);
    return Object.keys(e).length === 0;
  };
  const handleTypeSubmit = async (e) => {
    e.preventDefault();
    if (!validateTypeForm()) return;
    setIsSavingType(true);
    try {
      const payload = {
        ...typeForm,
        base_price_rent: Number(typeForm.base_price_rent),
        base_price_sale: Number(typeForm.base_price_sale),
      };
      if (editingType) {
        await updateWebType(editingType.id, payload);
        setSuccessModal({
          isOpen: true,
          message: `Tipo "${payload.name}" actualizado.`,
        });
      } else {
        await createWebType(payload);
        setSuccessModal({
          isOpen: true,
          message: `Tipo "${payload.name}" creado.`,
        });
      }
      setShowTypeForm(false);
      setEditingType(null);
      loadData();
    } catch (err) {
      setErrorModal({
        isOpen: true,
        message: err.userMessage || "Error al guardar.",
      });
    } finally {
      setIsSavingType(false);
    }
  };

  // ── HANDLERS CARACTERÍSTICAS ───────────────────────────────────────────────

  const handleNewFeature = () => {
    setEditingFeature(null);
    setFeatureForm({
      ...INITIAL_FEATURE_FORM,
      web_type_ids: webTypes.map((t) => t.id),
    });
    setFeatureErrors({});
    setShowFeatureForm(true);
    setShowTypeForm(false);
  };
  const handleEditFeature = (feature) => {
    setEditingFeature(feature);
    setFeatureForm({
      name: feature.name,
      extra_price: feature.extra_price,
      web_type_ids:
        feature.web_type_ids ||
        (feature.web_type_id ? [feature.web_type_id] : []),
      is_active: feature.is_active,
    });
    setFeatureErrors({});
    setShowFeatureForm(true);
    setShowTypeForm(false);
  };
  const handleFeatureChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFeatureForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
    if (featureErrors[name])
      setFeatureErrors((prev) => ({ ...prev, [name]: "" }));
  };
  const handleFeatureWebTypeToggle = (typeId) => {
    setFeatureForm((prev) => {
      const ids = prev.web_type_ids || [];
      const next = ids.includes(typeId)
        ? ids.filter((id) => id !== typeId)
        : [...ids, typeId];
      return { ...prev, web_type_ids: next };
    });
  };
  const validateFeatureForm = () => {
    const e = {};
    if (!featureForm.name.trim()) e.name = "El nombre es requerido.";
    if (featureForm.extra_price === "" || Number(featureForm.extra_price) < 0)
      e.extra_price = "Ingresá un precio válido.";
    setFeatureErrors(e);
    return Object.keys(e).length === 0;
  };
  const handleFeatureSubmit = async (e) => {
    e.preventDefault();
    if (!validateFeatureForm()) return;
    setIsSavingFeature(true);
    try {
      const payload = {
        ...featureForm,
        extra_price: Number(featureForm.extra_price),
        web_type_ids: featureForm.web_type_ids || [],
      };
      if (editingFeature) {
        await updateWebFeature(editingFeature.id, payload);
        setSuccessModal({
          isOpen: true,
          message: `Característica "${payload.name}" actualizada.`,
        });
      } else {
        await createWebFeature(payload);
        setSuccessModal({
          isOpen: true,
          message: `Característica "${payload.name}" creada.`,
        });
      }
      setShowFeatureForm(false);
      setEditingFeature(null);
      loadData();
    } catch (err) {
      setErrorModal({
        isOpen: true,
        message: err.userMessage || "Error al guardar.",
      });
    } finally {
      setIsSavingFeature(false);
    }
  };

  const showSidePanel =
    (activeTab === "types" && showTypeForm) ||
    (activeTab === "features" && showFeatureForm);

  // ── TAB STYLE ──────────────────────────────────────────────────────────────

  const getTabStyle = (tabKey) => {
    const isActive = activeTab === tabKey;
    return {
      padding: "0.75rem 1.5rem",
      borderRadius: "0.375rem",
      fontFamily: "'Rajdhani', sans-serif",
      fontSize: "14px",
      fontWeight: 600,
      cursor: "pointer",
      outline: "none",
      border: isActive
        ? "1px solid rgba(63,229,229,0.3)"
        : "1px solid transparent",
      backgroundColor: isActive ? "rgba(63,229,229,0.12)" : "transparent",
      color: isActive ? "#3fe5e5" : "#8892a4",
      transition: "all 0.2s",
    };
  };

  // ── RENDER ─────────────────────────────────────────────────────────────────

  return (
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
            {activeTab === "types"
              ? "Tipos de sitio web"
              : "Características extra"}
          </h2>
          <p
            style={{
              color: "#8892a4",
              fontSize: "14px",
              margin: "0.25rem 0 0 0",
            }}
          >
            {activeTab === "types"
              ? "// Precios de alquiler y venta por tipo"
              : "// Características adicionales para los sitios web"}
          </p>
        </div>
        {can(user, "catalog", "create") && (
          <Button
            variant="primary"
            size="lg"
            onClick={activeTab === "types" ? handleNewType : handleNewFeature}
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
            {activeTab === "types" ? "Agregar tipo" : "Nueva característica"}
          </Button>
        )}
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: "0.375rem",
          padding: "0.375rem",
          borderRadius: "0.5rem",
          width: "fit-content",
          backgroundColor: "#0b0d1a",
          border: "1px solid rgba(63,229,229,0.12)",
        }}
      >
        {[
          { key: "types", label: "Tipos de web" },
          { key: "features", label: "Características extra" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => {
              setActiveTab(tab.key);
              setShowTypeForm(false);
              setShowFeatureForm(false);
            }}
            style={getTabStyle(tab.key)}
            onMouseEnter={(e) => {
              if (activeTab !== tab.key) {
                e.currentTarget.style.backgroundColor = "rgba(63,229,229,0.06)";
                e.currentTarget.style.color = "#c5cdd8";
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== tab.key) {
                e.currentTarget.style.backgroundColor = "transparent";
                e.currentTarget.style.color = "#8892a4";
              }
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Contenido + panel lateral */}
      <div style={{ display: "flex", gap: "1.5rem", alignItems: "flex-start" }}>
        {/* Grilla de cards */}
        <div style={{ flex: 1, minWidth: 0 }}>
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
          ) : activeTab === "types" ? (
            <>
              {/* Grilla 3 columnas — tipos de web */}
              {pagedTypes.length === 0 ? (
                <div
                  style={{
                    textAlign: "center",
                    padding: "4rem",
                    color: "#8892a4",
                  }}
                >
                  <p>No hay tipos de web registrados.</p>
                </div>
              ) : (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    gap: "1rem",
                  }}
                >
                  {pagedTypes.map((type) => (
                    <div
                      key={type.id}
                      style={{
                        backgroundColor: "#111427",
                        border: "1px solid rgba(63,229,229,0.08)",
                        borderRadius: "0.75rem",
                        padding: "1.125rem",
                        transition: "all 0.2s",
                        display: "flex",
                        flexDirection: "column",
                        gap: "0.75rem",
                      }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.borderColor =
                          "rgba(63,229,229,0.25)")
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.borderColor =
                          "rgba(63,229,229,0.08)")
                      }
                    >
                      {/* Nombre del tipo + estado */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          justifyContent: "space-between",
                          gap: "0.5rem",
                        }}
                      >
                        <p
                          style={{
                            fontFamily: "'Orbitron', monospace",
                            fontSize: "12px",
                            fontWeight: 700,
                            color: "white",
                            letterSpacing: "0.05em",
                            margin: 0,
                            lineHeight: 1.3,
                          }}
                        >
                          {type.name}
                        </p>
                        {!type.is_active && (
                          <Badge status="inactivo" dot={false} />
                        )}
                      </div>

                      {/* Precios */}
                      <div style={{ display: "flex", gap: "0.625rem" }}>
                        {/* Alquiler */}
                        <div
                          style={{
                            flex: 1,
                            backgroundColor: "rgba(255,255,255,0.03)",
                            border: "1px solid rgba(255,255,255,0.06)",
                            borderRadius: "0.5rem",
                            padding: "0.625rem",
                            textAlign: "center",
                          }}
                        >
                          <p
                            style={{
                              fontFamily: "'Share Tech Mono', monospace",
                              fontSize: "8px",
                              color: "#8892a4",
                              letterSpacing: "0.08em",
                              margin: "0 0 0.25rem 0",
                              textTransform: "uppercase",
                            }}
                          >
                            Alquiler/mes
                          </p>
                          <p
                            style={{
                              fontFamily: "'Orbitron', monospace",
                              fontSize: "16px",
                              fontWeight: 700,
                              color: "#8235f2",
                              margin: 0,
                            }}
                          >
                            {formatPrice(type.base_price_rent)}
                          </p>
                        </div>
                        {/* Venta */}
                        <div
                          style={{
                            flex: 1,
                            backgroundColor: "rgba(255,255,255,0.03)",
                            border: "1px solid rgba(255,255,255,0.06)",
                            borderRadius: "0.5rem",
                            padding: "0.625rem",
                            textAlign: "center",
                          }}
                        >
                          <p
                            style={{
                              fontFamily: "'Share Tech Mono', monospace",
                              fontSize: "8px",
                              color: "#8892a4",
                              letterSpacing: "0.08em",
                              margin: "0 0 0.25rem 0",
                              textTransform: "uppercase",
                            }}
                          >
                            Venta
                          </p>
                          <p
                            style={{
                              fontFamily: "'Orbitron', monospace",
                              fontSize: "16px",
                              fontWeight: 700,
                              color: "#3fe5e5",
                              margin: 0,
                            }}
                          >
                            {formatPrice(type.base_price_sale)}
                          </p>
                        </div>
                      </div>

                      {/* Botón editar */}
                      {can(user, "catalog", "edit") && (
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "flex-end",
                          }}
                        >
                          <button
                            onClick={() => handleEditType(type)}
                            title="Editar"
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "0.375rem",
                              padding: "0.375rem 0.75rem",
                              borderRadius: "0.375rem",
                              background: "transparent",
                              border: "1px solid rgba(63,229,229,0.15)",
                              color: "#8892a4",
                              cursor: "pointer",
                              fontSize: "12px",
                              fontFamily: "'Rajdhani', sans-serif",
                              fontWeight: 600,
                              transition: "all 0.2s",
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.borderColor =
                                "rgba(63,229,229,0.4)";
                              e.currentTarget.style.color = "#3fe5e5";
                              e.currentTarget.style.backgroundColor =
                                "rgba(63,229,229,0.08)";
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.borderColor =
                                "rgba(63,229,229,0.15)";
                              e.currentTarget.style.color = "#8892a4";
                              e.currentTarget.style.backgroundColor =
                                "transparent";
                            }}
                          >
                            <svg
                              width="12"
                              height="12"
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
                            Editar
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Paginación tipos */}
              <Pagination
                currentPage={typesPage}
                totalPages={totalTypePages}
                totalItems={webTypes.length}
                itemsPerPage={ITEMS_PER_PAGE}
                onPageChange={setTypesPage}
              />
            </>
          ) : (
            <>
              {/* Grilla 3 columnas — características extra */}
              {pagedFeatures.length === 0 ? (
                <div
                  style={{
                    textAlign: "center",
                    padding: "4rem",
                    color: "#8892a4",
                  }}
                >
                  <p>No hay características registradas.</p>
                </div>
              ) : (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    gap: "1rem",
                  }}
                >
                  {pagedFeatures.map((feature) => (
                    <div
                      key={feature.id}
                      style={{
                        backgroundColor: "#111427",
                        border: "1px solid rgba(63,229,229,0.08)",
                        borderRadius: "0.75rem",
                        padding: "1.125rem",
                        transition: "all 0.2s",
                        display: "flex",
                        flexDirection: "column",
                        gap: "0.75rem",
                      }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.borderColor =
                          "rgba(63,229,229,0.25)")
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.borderColor =
                          "rgba(63,229,229,0.08)")
                      }
                    >
                      {/* Nombre + estado */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          justifyContent: "space-between",
                          gap: "0.5rem",
                        }}
                      >
                        <p
                          style={{
                            fontFamily: "'Orbitron', monospace",
                            fontSize: "12px",
                            fontWeight: 700,
                            color: "white",
                            letterSpacing: "0.05em",
                            margin: 0,
                            lineHeight: 1.3,
                          }}
                        >
                          {feature.name}
                        </p>
                        {!feature.is_active && (
                          <Badge status="inactivo" dot={false} />
                        )}
                      </div>

                      {/* Precio extra + aplica a */}
                      <div style={{ display: "flex", gap: "0.625rem" }}>
                        <div
                          style={{
                            flex: 1,
                            backgroundColor: "rgba(255,255,255,0.03)",
                            border: "1px solid rgba(255,255,255,0.06)",
                            borderRadius: "0.5rem",
                            padding: "0.625rem",
                            textAlign: "center",
                          }}
                        >
                          <p
                            style={{
                              fontFamily: "'Share Tech Mono', monospace",
                              fontSize: "8px",
                              color: "#8892a4",
                              letterSpacing: "0.08em",
                              margin: "0 0 0.25rem 0",
                              textTransform: "uppercase",
                            }}
                          >
                            Precio extra
                          </p>
                          <p
                            style={{
                              fontFamily: "'Orbitron', monospace",
                              fontSize: "16px",
                              fontWeight: 700,
                              color: "#3fe5e5",
                              margin: 0,
                            }}
                          >
                            +{formatPrice(feature.extra_price)}
                          </p>
                        </div>
                        <div
                          style={{
                            flex: 1,
                            backgroundColor: "rgba(255,255,255,0.03)",
                            border: "1px solid rgba(255,255,255,0.06)",
                            borderRadius: "0.5rem",
                            padding: "0.625rem",
                            textAlign: "center",
                          }}
                        >
                          <p
                            style={{
                              fontFamily: "'Share Tech Mono', monospace",
                              fontSize: "8px",
                              color: "#8892a4",
                              letterSpacing: "0.08em",
                              margin: "0 0 0.25rem 0",
                              textTransform: "uppercase",
                            }}
                          >
                            Aplica a
                          </p>
                          <p
                            style={{
                              fontFamily: "'Rajdhani', sans-serif",
                              fontSize: "12px",
                              fontWeight: 600,
                              color: "#c5cdd8",
                              margin: 0,
                            }}
                          >
                            {(() => {
                              const ids =
                                feature.web_type_ids ||
                                (feature.web_type_id
                                  ? [feature.web_type_id]
                                  : []);
                              if (ids.length === 0) return "Todos";
                              const first =
                                webTypes.find((t) => t.id === ids[0])?.name ||
                                "Tipo";
                              return ids.length === 1
                                ? first
                                : `${first} +${ids.length - 1}`;
                            })()}
                          </p>
                        </div>
                      </div>

                      {/* Botón editar */}
                      {can(user, "catalog", "edit") && (
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "flex-end",
                          }}
                        >
                          <button
                            onClick={() => handleEditFeature(feature)}
                            title="Editar"
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "0.375rem",
                              padding: "0.375rem 0.75rem",
                              borderRadius: "0.375rem",
                              background: "transparent",
                              border: "1px solid rgba(63,229,229,0.15)",
                              color: "#8892a4",
                              cursor: "pointer",
                              fontSize: "12px",
                              fontFamily: "'Rajdhani', sans-serif",
                              fontWeight: 600,
                              transition: "all 0.2s",
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.borderColor =
                                "rgba(63,229,229,0.4)";
                              e.currentTarget.style.color = "#3fe5e5";
                              e.currentTarget.style.backgroundColor =
                                "rgba(63,229,229,0.08)";
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.borderColor =
                                "rgba(63,229,229,0.15)";
                              e.currentTarget.style.color = "#8892a4";
                              e.currentTarget.style.backgroundColor =
                                "transparent";
                            }}
                          >
                            <svg
                              width="12"
                              height="12"
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
                            Editar
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Paginación características */}
              <Pagination
                currentPage={featuresPage}
                totalPages={totalFeaturePages}
                totalItems={webFeatures.length}
                itemsPerPage={ITEMS_PER_PAGE}
                onPageChange={setFeaturesPage}
              />
            </>
          )}
        </div>

        {/* Panel lateral — tipo de web */}
        {showTypeForm && can(user, "catalog", "create") && (
          <div
            style={{
              width: "320px",
              flexShrink: 0,
              borderRadius: "0.5rem",
              backgroundColor: "#111427",
              border: "1px solid rgba(63,229,229,0.2)",
              overflow: "hidden",
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
              <h3
                style={{
                  fontFamily: "'Rajdhani', sans-serif",
                  color: "#3fe5e5",
                  fontSize: "15px",
                  fontWeight: 600,
                  margin: 0,
                }}
              >
                {editingType
                  ? `Editar: ${editingType.name}`
                  : "Nuevo tipo de web"}
              </h3>
              <button
                onClick={() => {
                  setShowTypeForm(false);
                  setEditingType(null);
                }}
                style={{
                  padding: "0.25rem",
                  borderRadius: "0.25rem",
                  background: "transparent",
                  border: "none",
                  color: "#8892a4",
                  cursor: "pointer",
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
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
            <form
              onSubmit={handleTypeSubmit}
              noValidate
              style={{
                padding: "1.5rem",
                display: "flex",
                flexDirection: "column",
                gap: "1rem",
              }}
            >
              <Input
                label="Nombre del tipo"
                name="name"
                value={typeForm.name}
                onChange={handleTypeChange}
                error={typeErrors.name}
                placeholder="Ej: Landing Page"
                required
              />
              <Input
                type="number"
                label="Precio alquiler/mes (S/)"
                name="base_price_rent"
                value={typeForm.base_price_rent}
                onChange={handleTypeChange}
                error={typeErrors.base_price_rent}
                placeholder="0.00"
                required
              />
              <Input
                type="number"
                label="Precio venta única (S/)"
                name="base_price_sale"
                value={typeForm.base_price_sale}
                onChange={handleTypeChange}
                error={typeErrors.base_price_sale}
                placeholder="0.00"
                required
              />
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  padding: "0.75rem 1rem",
                  borderRadius: "0.375rem",
                  cursor: "pointer",
                  backgroundColor: typeForm.is_active
                    ? "rgba(63,229,229,0.08)"
                    : "#1a1d30",
                  border: `1px solid ${typeForm.is_active ? "rgba(63,229,229,0.3)" : "rgba(63,229,229,0.1)"}`,
                }}
              >
                <input
                  type="checkbox"
                  name="is_active"
                  checked={typeForm.is_active}
                  onChange={handleTypeChange}
                  style={{ accentColor: "#3fe5e5" }}
                />
                <span
                  style={{
                    fontSize: "14px",
                    color: "white",
                    fontFamily: "'Rajdhani', sans-serif",
                  }}
                >
                  Disponible para clientes
                </span>
              </label>
              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  paddingTop: "0.25rem",
                }}
              >
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setShowTypeForm(false);
                    setEditingType(null);
                  }}
                  disabled={isSavingType}
                  style={{ flex: 1 }}
                >
                  Cancelar
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={isSavingType}
                  style={{ flex: 1 }}
                >
                  {editingType ? "Guardar" : "Crear"}
                </Button>
              </div>
            </form>
          </div>
        )}

        {/* Panel lateral — características */}
        {showFeatureForm && can(user, "catalog", "create") && (
          <div
            style={{
              width: "320px",
              flexShrink: 0,
              borderRadius: "0.5rem",
              backgroundColor: "#111427",
              border: "1px solid rgba(63,229,229,0.2)",
              overflow: "hidden",
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
              <h3
                style={{
                  fontFamily: "'Rajdhani', sans-serif",
                  color: "#3fe5e5",
                  fontSize: "15px",
                  fontWeight: 600,
                  margin: 0,
                }}
              >
                {editingFeature
                  ? `Editar: ${editingFeature.name}`
                  : "Nueva característica"}
              </h3>
              <button
                onClick={() => {
                  setShowFeatureForm(false);
                  setEditingFeature(null);
                }}
                style={{
                  padding: "0.25rem",
                  borderRadius: "0.25rem",
                  background: "transparent",
                  border: "none",
                  color: "#8892a4",
                  cursor: "pointer",
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
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
            <form
              onSubmit={handleFeatureSubmit}
              noValidate
              style={{
                padding: "1.5rem",
                display: "flex",
                flexDirection: "column",
                gap: "1rem",
              }}
            >
              <Input
                label="Nombre"
                name="name"
                value={featureForm.name}
                onChange={handleFeatureChange}
                error={featureErrors.name}
                placeholder="Ej: Chat en vivo"
                required
              />
              <Input
                type="number"
                label="Precio extra (S/)"
                name="extra_price"
                value={featureForm.extra_price}
                onChange={handleFeatureChange}
                error={featureErrors.extra_price}
                placeholder="0.00"
                required
              />
              {/* Multi-select de tipos de web */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <label
                    style={{
                      fontFamily: "'Rajdhani', sans-serif",
                      fontSize: "14px",
                      fontWeight: 500,
                      color: "#c5cdd8",
                    }}
                  >
                    Aplica a tipos de web
                  </label>
                  <button
                    type="button"
                    onClick={() =>
                      setFeatureForm((prev) => ({
                        ...prev,
                        web_type_ids:
                          prev.web_type_ids?.length === webTypes.length
                            ? []
                            : webTypes.map((t) => t.id),
                      }))
                    }
                    style={{
                      fontFamily: "'Share Tech Mono', monospace",
                      fontSize: "9px",
                      color: "#3fe5e5",
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                      letterSpacing: "0.08em",
                    }}
                  >
                    {featureForm.web_type_ids?.length === webTypes.length
                      ? "DESELECCIONAR TODOS"
                      : "SELECCIONAR TODOS"}
                  </button>
                </div>
                <p
                  style={{
                    fontFamily: "'Rajdhani', sans-serif",
                    fontSize: "12px",
                    color: "#8892a4",
                    margin: 0,
                  }}
                >
                  Sin selección = aplica a todos los tipos
                </p>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.375rem",
                    maxHeight: "200px",
                    overflowY: "auto",
                    padding: "0.25rem 0",
                    scrollbarWidth: "thin",
                    scrollbarColor: "rgba(63,229,229,0.3) transparent",
                  }}
                >
                  {webTypes.map((t) => (
                    <label
                      key={t.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.75rem",
                        padding: "0.5rem 0.75rem",
                        borderRadius: "0.375rem",
                        cursor: "pointer",
                        backgroundColor: (
                          featureForm.web_type_ids || []
                        ).includes(t.id)
                          ? "rgba(63,229,229,0.08)"
                          : "transparent",
                        border: `1px solid ${(featureForm.web_type_ids || []).includes(t.id) ? "rgba(63,229,229,0.3)" : "rgba(63,229,229,0.08)"}`,
                        transition: "all 0.15s",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={(featureForm.web_type_ids || []).includes(
                          t.id,
                        )}
                        onChange={() => handleFeatureWebTypeToggle(t.id)}
                        style={{
                          accentColor: "#3fe5e5",
                          width: "14px",
                          height: "14px",
                          flexShrink: 0,
                        }}
                      />
                      <span
                        style={{
                          fontFamily: "'Rajdhani', sans-serif",
                          fontSize: "13px",
                          color: (featureForm.web_type_ids || []).includes(t.id)
                            ? "#3fe5e5"
                            : "#c5cdd8",
                          fontWeight: 500,
                        }}
                      >
                        {t.name}
                      </span>
                    </label>
                  ))}
                </div>
                {(featureForm.web_type_ids || []).length > 0 && (
                  <p
                    style={{
                      fontFamily: "'Share Tech Mono', monospace",
                      fontSize: "10px",
                      color: "#3fe5e5",
                      margin: 0,
                    }}
                  >
                    ✓ {featureForm.web_type_ids.length} tipo
                    {featureForm.web_type_ids.length !== 1 ? "s" : ""}{" "}
                    seleccionado
                    {featureForm.web_type_ids.length !== 1 ? "s" : ""}
                  </p>
                )}
              </div>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  padding: "0.75rem 1rem",
                  borderRadius: "0.375rem",
                  cursor: "pointer",
                  backgroundColor: featureForm.is_active
                    ? "rgba(63,229,229,0.08)"
                    : "#1a1d30",
                  border: `1px solid ${featureForm.is_active ? "rgba(63,229,229,0.3)" : "rgba(63,229,229,0.1)"}`,
                }}
              >
                <input
                  type="checkbox"
                  name="is_active"
                  checked={featureForm.is_active}
                  onChange={handleFeatureChange}
                  style={{ accentColor: "#3fe5e5" }}
                />
                <span
                  style={{
                    fontSize: "14px",
                    color: "white",
                    fontFamily: "'Rajdhani', sans-serif",
                  }}
                >
                  Disponible
                </span>
              </label>
              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  paddingTop: "0.25rem",
                }}
              >
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setShowFeatureForm(false);
                    setEditingFeature(null);
                  }}
                  disabled={isSavingFeature}
                  style={{ flex: 1 }}
                >
                  Cancelar
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={isSavingFeature}
                  style={{ flex: 1 }}
                >
                  {editingFeature ? "Guardar" : "Crear"}
                </Button>
              </div>
            </form>
          </div>
        )}
      </div>

      {/* Modales */}
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
  );
}
