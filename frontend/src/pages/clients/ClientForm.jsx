// ==============================================================================
// CLIENTFORM.JSX v4 — Precios automáticos completos
//
// Lógica de precios:
//   - Precio base     → automático según tipo de web + plan (solo lectura)
//   - Precio extra    → suma automática de características seleccionadas (solo lectura)
//   - Pago total      → precio base + precio extra (solo lectura, se calcula solo)
//   - Dominio         → cargo aparte, se muestra en resumen
// ==============================================================================

import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";
import { parsePriceInput, formatPrice } from "../../utils/formatPrice";
import { createClient, updateClient, getClientById } from "../../api/clients";
import { getWebTypes, getWebFeatures } from "../../api/catalog";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import { useToast } from "../../components/ui/Toast";
import LoadingSpinner from "../../components/ui/LoadingSpinner";

const INITIAL_FORM = {
  name: "",
  document_type: "DNI",
  document_number: "",
  email: "",
  phone: "",
  web_type_id: "",
  plan: "",
  status: "desarrollo",
  base_price: "",
  payment_frequency: "",
  registration_date: new Date().toISOString().split("T")[0],
  delivery_date: "",
  domain_price_type: "ninguno",
  domain_custom_price: "",
  notes: "",
};

const sectionStyle = {
  backgroundColor: "#111427",
  border: "1px solid rgba(63,229,229,0.12)",
  borderRadius: "0.5rem",
  padding: "1.75rem",
  display: "flex",
  flexDirection: "column",
  gap: "1.25rem",
};

const sectionTitleStyle = {
  fontFamily: "'Share Tech Mono', monospace",
  fontSize: "11px",
  fontWeight: 700,
  color: "#3fe5e5",
  textTransform: "uppercase",
  letterSpacing: "0.12em",
  margin: 0,
};

const grid2Style = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: "1rem",
};

const grid3Style = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr 1fr",
  gap: "1rem",
};

// Componente para mostrar un precio calculado automáticamente (solo lectura)
function AutoPriceField({ label, value, color = "#3fe5e5", hint, error }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      <label
        style={{
          fontFamily: "'Rajdhani', sans-serif",
          fontSize: "14px",
          fontWeight: 500,
          color: error ? "#ff3366" : "#c5cdd8",
        }}
      >
        {label}
      </label>
      <div
        style={{
          padding: "0.875rem 1rem",
          borderRadius: "0.375rem",
          backgroundColor: value ? "rgba(63,229,229,0.05)" : "#1a1d30",
          border: error
            ? "1px solid rgba(255,51,102,0.6)"
            : value
              ? "1px solid rgba(63,229,229,0.2)"
              : "1px solid rgba(63,229,229,0.08)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "0.5rem",
        }}
      >
        <span
          style={{
            fontFamily: "'Rajdhani', sans-serif",
            fontSize: "12px",
            color: "#8892a4",
          }}
        >
          {hint || "Automático"}
        </span>
        <span
          style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: "18px",
            fontWeight: 700,
            color: value ? color : "#374151",
          }}
        >
          {value !== "" && value !== 0
            ? formatPrice(value)
            : value === 0
              ? formatPrice(0)
              : "—"}
        </span>
      </div>
      {error && (
        <p style={{ color: "#ff3366", fontSize: "12px", margin: 0 }}>
          ⚠ {error}
        </p>
      )}
    </div>
  );
}

export default function ClientForm() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const { id } = useParams();

  const isEditMode = Boolean(id);
  const action = isEditMode ? "edit" : "create";

  useEffect(() => {
    if (!can(user, "clients", action)) navigate("/clientes", { replace: true });
  }, [user, action, navigate]);

  const [formData, setFormData] = useState(INITIAL_FORM);
  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingData, setIsLoadingData] = useState(isEditMode);
  const [webTypes, setWebTypes] = useState([]);
  const [webFeatures, setWebFeatures] = useState([]);
  const [selectedFeatures, setSelectedFeatures] = useState([]);

  // Tipo de web seleccionado (para acceder a sus precios)
  const selectedWebType = webTypes.find(
    (t) => String(t.id) === String(formData.web_type_id),
  );

  // ── CÁLCULOS AUTOMÁTICOS ───────────────────────────────────────────────────

  // Precio extra = suma de todas las características seleccionadas
  const extraPrice = webFeatures
    .filter((f) => selectedFeatures.includes(f.id))
    .reduce((sum, f) => sum + (f.extra_price || 0), 0);

  // Precio base numérico
  const basePrice = parsePriceInput(String(formData.base_price)) || 0;

  // Precio de dominio
  const domainPrice =
    formData.domain_price_type === "200"
      ? 200
      : formData.domain_price_type === "otro"
        ? parsePriceInput(String(formData.domain_custom_price)) || 0
        : 0;

  // Pago total = base + extra (sin dominio — el dominio es un cargo separado)
  const totalPayment = basePrice + extraPrice;

  // ── CARGA INICIAL ──────────────────────────────────────────────────────────

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const types = await getWebTypes(true);
        setWebTypes(types);
        if (isEditMode) {
          const client = await getClientById(id);
          setFormData({
            name: client.name || "",
            document_type: client.document_type || "DNI",
            document_number: client.document_number || "",
            email: client.email || "",
            phone: client.phone || "",
            web_type_id: client.web_type_id || "",
            plan: client.plan || "",
            status: client.status || "desarrollo",
            base_price: client.base_price || "",
            payment_frequency: client.payment_frequency || "",
            registration_date: client.registration_date || "",
            delivery_date: client.delivery_date || "",
            domain_price_type: client.domain_price_type || "ninguno",
            domain_custom_price: client.domain_custom_price || "",
            notes: client.notes || "",
          });
          setSelectedFeatures(client.features?.map((f) => f.id) || []);
        }
      } catch (err) {
        showToast(
          "error",
          "ERROR AL CARGAR",
          err.userMessage || "Error al cargar los datos.",
        );
      } finally {
        setIsLoadingData(false);
      }
    };
    loadInitialData();
  }, [isEditMode, id]);

  // Carga características según tipo de web
  useEffect(() => {
    if (!formData.web_type_id) {
      setWebFeatures([]);
      return;
    }
    getWebFeatures(formData.web_type_id, true)
      .then(setWebFeatures)
      .catch(() => setWebFeatures([]));
  }, [formData.web_type_id]);

  // ── HANDLERS ───────────────────────────────────────────────────────────────

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: "" }));
  };

  const handleWebTypeChange = (e) => {
    setFormData((prev) => ({
      ...prev,
      web_type_id: e.target.value,
      plan: "",
      base_price: "",
      payment_frequency: "",
    }));
    setSelectedFeatures([]);
    if (errors.web_type_id) setErrors((prev) => ({ ...prev, web_type_id: "" }));
  };

  const handlePlanChange = (e) => {
    const plan = e.target.value;
    const webType = webTypes.find(
      (t) => String(t.id) === String(formData.web_type_id),
    );
    setFormData((prev) => ({
      ...prev,
      plan,
      base_price:
        plan === "alquiler"
          ? webType?.base_price_rent || ""
          : webType?.base_price_sale || "",
      payment_frequency: plan === "alquiler" ? "mensual" : "anual",
    }));
    if (errors.plan) setErrors((prev) => ({ ...prev, plan: "" }));
  };

  const handleFeatureToggle = (featureId) => {
    setSelectedFeatures((prev) =>
      prev.includes(featureId)
        ? prev.filter((fid) => fid !== featureId)
        : [...prev, featureId],
    );
  };

  // ── VALIDACIÓN ─────────────────────────────────────────────────────────────

  const validateForm = () => {
    const newErrors = {};
    if (!formData.name.trim() || formData.name.trim().length < 3)
      newErrors.name = "El nombre debe tener al menos 3 caracteres.";
    if (!formData.document_type)
      newErrors.document_type = "Seleccioná el tipo de documento.";
    if (!formData.document_number.trim())
      newErrors.document_number = "El número de documento es requerido.";
    if (!formData.email.trim())
      newErrors.email = "El correo electrónico es requerido.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email))
      newErrors.email = "El formato del correo no es válido.";
    if (!formData.phone.trim()) newErrors.phone = "El teléfono es requerido.";
    if (!formData.web_type_id)
      newErrors.web_type_id = "Seleccioná el tipo de web.";
    if (!formData.plan) newErrors.plan = "Seleccioná el plan.";
    if (!formData.base_price)
      newErrors.base_price = "El precio base es requerido.";
    if (!formData.registration_date)
      newErrors.registration_date = "La fecha de registro es requerida.";
    if (formData.domain_price_type === "otro" && !formData.domain_custom_price)
      newErrors.domain_custom_price = "Ingresá el precio del dominio.";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // ── SUBMIT ─────────────────────────────────────────────────────────────────

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;
    setIsLoading(true);
    try {
      const payload = {
        ...formData,
        base_price: basePrice,
        extra_price: extraPrice,
        total_price: totalPayment,
        domain_price: domainPrice,
        domain_custom_price:
          formData.domain_price_type === "otro"
            ? parsePriceInput(String(formData.domain_custom_price))
            : null,
        delivery_date: formData.delivery_date || null,
        notes: formData.notes || null,
        feature_ids: selectedFeatures,
      };
      if (isEditMode) {
        await updateClient(id, payload);
        showToast(
          "success",
          "CAMBIOS GUARDADOS",
          "Cliente actualizado correctamente.",
        );
        navigate("/clientes");
      } else {
        await createClient(payload);
        showToast(
          "success",
          "CLIENTE REGISTRADO",
          "Cliente registrado correctamente.",
        );
        navigate("/clientes");
      }
    } catch (err) {
      showToast(
        "error",
        "ERROR AL GUARDAR",
        err.userMessage ||
          err.response?.data?.detail ||
          "Error al guardar el cliente.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoadingData)
    return <LoadingSpinner fullPage label="Cargando datos del cliente..." />;

  // ── RENDER ─────────────────────────────────────────────────────────────────

  return (
    <div
      style={{
        maxWidth: "760px",
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: "1.5rem",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        <button
          onClick={() => navigate("/clientes")}
          style={{
            padding: "0.5rem",
            borderRadius: "0.375rem",
            background: "transparent",
            border: "none",
            color: "#8892a4",
            cursor: "pointer",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.05)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.backgroundColor = "transparent")
          }
        >
          <svg
            width="20"
            height="20"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 19l-7-7m0 0l7-7m-7 7h18"
            />
          </svg>
        </button>
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
            {isEditMode ? "Editar cliente" : "Registrar nuevo cliente"}
          </h2>
          <p
            style={{
              color: "#8892a4",
              fontSize: "14px",
              margin: "0.25rem 0 0 0",
            }}
          >
            {isEditMode
              ? "Modificá los datos del cliente"
              : "Completá los datos para registrar un nuevo cliente"}
          </p>
        </div>
      </div>

      <form
        onSubmit={handleSubmit}
        noValidate
        style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}
      >
        {/* ── DATOS DEL CLIENTE ─────────────────────────────────────────── */}
        <section style={sectionStyle}>
          <h3 style={sectionTitleStyle}>Datos del cliente</h3>

          <Input
            label="Nombre completo o razón social"
            name="name"
            value={formData.name}
            onChange={handleChange}
            error={errors.name}
            placeholder="Ej: Pollería El Gordo SAC"
            required
          />

          <div style={grid2Style}>
            <Input
              type="select"
              label="Tipo de documento"
              name="document_type"
              value={formData.document_type}
              onChange={handleChange}
              error={errors.document_type}
              options={[
                { value: "DNI", label: "DNI" },
                { value: "RUC", label: "RUC" },
                { value: "CE", label: "Carné de Extranjería" },
                { value: "Pasaporte", label: "Pasaporte" },
              ]}
              required
            />
            <Input
              label="Número de documento"
              name="document_number"
              value={formData.document_number}
              onChange={handleChange}
              error={errors.document_number}
              placeholder="Ej: 20601234567"
              required
            />
          </div>

          <div style={grid2Style}>
            <Input
              type="email"
              label="Correo electrónico"
              name="email"
              value={formData.email}
              onChange={handleChange}
              error={errors.email}
              placeholder="correo@empresa.com"
              required
            />
            <Input
              type="tel"
              label="Teléfono"
              name="phone"
              value={formData.phone}
              onChange={handleChange}
              error={errors.phone}
              placeholder="Ej: 999999999"
              required
            />
          </div>
        </section>

        {/* ── SERVICIO CONTRATADO ───────────────────────────────────────── */}
        <section style={sectionStyle}>
          <h3 style={sectionTitleStyle}>Servicio contratado</h3>

          <div style={grid2Style}>
            <Input
              type="select"
              label="Tipo de sitio web"
              name="web_type_id"
              value={formData.web_type_id}
              onChange={handleWebTypeChange}
              error={errors.web_type_id}
              placeholder="Seleccioná el tipo..."
              options={webTypes.map((t) => ({ value: t.id, label: t.name }))}
              required
            />
            <Input
              type="select"
              label="Estado"
              name="status"
              value={formData.status}
              onChange={handleChange}
              options={[
                { value: "desarrollo", label: "En desarrollo" },
                { value: "activo", label: "Activo" },
                { value: "inactivo", label: "Inactivo" },
              ]}
            />
          </div>

          {/* Plan */}
          <div
            style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}
          >
            <label
              style={{
                fontFamily: "'Rajdhani', sans-serif",
                fontSize: "14px",
                fontWeight: 500,
                color: errors.plan ? "#ff3366" : "#c5cdd8",
              }}
            >
              Plan <span style={{ color: "#ff3366" }}>*</span>
            </label>

            {!formData.web_type_id ? (
              <div
                style={{
                  padding: "0.875rem 1rem",
                  borderRadius: "0.375rem",
                  backgroundColor: "#111427",
                  border: "1px solid rgba(63,229,229,0.08)",
                  color: "#374151",
                  fontSize: "14px",
                  fontFamily: "'Rajdhani', sans-serif",
                  cursor: "not-allowed",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                }}
              >
                <svg
                  width="14"
                  height="14"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  style={{ flexShrink: 0 }}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                  />
                </svg>
                Seleccioná primero el tipo de web
              </div>
            ) : (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "0.75rem",
                }}
              >
                {/* Card Alquiler */}
                <label
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.375rem",
                    padding: "1rem 1.125rem",
                    borderRadius: "0.5rem",
                    cursor: "pointer",
                    backgroundColor:
                      formData.plan === "alquiler"
                        ? "rgba(63,229,229,0.08)"
                        : "#1a1d30",
                    border:
                      formData.plan === "alquiler"
                        ? "2px solid rgba(63,229,229,0.5)"
                        : "1px solid rgba(63,229,229,0.15)",
                    transition: "all 0.2s",
                  }}
                  onMouseEnter={(e) => {
                    if (formData.plan !== "alquiler") {
                      e.currentTarget.style.borderColor =
                        "rgba(63,229,229,0.3)";
                      e.currentTarget.style.backgroundColor =
                        "rgba(63,229,229,0.04)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (formData.plan !== "alquiler") {
                      e.currentTarget.style.borderColor =
                        "rgba(63,229,229,0.15)";
                      e.currentTarget.style.backgroundColor = "#1a1d30";
                    }
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.625rem",
                    }}
                  >
                    <input
                      type="radio"
                      name="plan"
                      value="alquiler"
                      checked={formData.plan === "alquiler"}
                      onChange={handlePlanChange}
                      style={{
                        accentColor: "#3fe5e5",
                        width: "16px",
                        height: "16px",
                        flexShrink: 0,
                      }}
                    />
                    <span
                      style={{
                        fontFamily: "'Rajdhani', sans-serif",
                        fontSize: "14px",
                        fontWeight: 600,
                        color: "white",
                      }}
                    >
                      Alquiler
                    </span>
                  </div>
                  <p
                    style={{
                      margin: 0,
                      fontFamily: "'Rajdhani', sans-serif",
                      fontSize: "12px",
                      color: "#8892a4",
                      paddingLeft: "1.5rem",
                    }}
                  >
                    Pago recurrente
                  </p>
                  <p
                    style={{
                      margin: 0,
                      fontFamily: "'Share Tech Mono', monospace",
                      fontSize: "18px",
                      fontWeight: 700,
                      color: "#3fe5e5",
                      paddingLeft: "1.5rem",
                    }}
                  >
                    {selectedWebType
                      ? formatPrice(selectedWebType.base_price_rent)
                      : "S/ —"}
                    <span style={{ fontSize: "11px", color: "#8892a4" }}>
                      /mes
                    </span>
                  </p>
                </label>

                {/* Card Venta */}
                <label
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.375rem",
                    padding: "1rem 1.125rem",
                    borderRadius: "0.5rem",
                    cursor: "pointer",
                    backgroundColor:
                      formData.plan === "venta"
                        ? "rgba(130,53,242,0.08)"
                        : "#1a1d30",
                    border:
                      formData.plan === "venta"
                        ? "2px solid rgba(130,53,242,0.5)"
                        : "1px solid rgba(63,229,229,0.15)",
                    transition: "all 0.2s",
                  }}
                  onMouseEnter={(e) => {
                    if (formData.plan !== "venta") {
                      e.currentTarget.style.borderColor =
                        "rgba(130,53,242,0.3)";
                      e.currentTarget.style.backgroundColor =
                        "rgba(130,53,242,0.04)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (formData.plan !== "venta") {
                      e.currentTarget.style.borderColor =
                        "rgba(63,229,229,0.15)";
                      e.currentTarget.style.backgroundColor = "#1a1d30";
                    }
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.625rem",
                    }}
                  >
                    <input
                      type="radio"
                      name="plan"
                      value="venta"
                      checked={formData.plan === "venta"}
                      onChange={handlePlanChange}
                      style={{
                        accentColor: "#8235f2",
                        width: "16px",
                        height: "16px",
                        flexShrink: 0,
                      }}
                    />
                    <span
                      style={{
                        fontFamily: "'Rajdhani', sans-serif",
                        fontSize: "14px",
                        fontWeight: 600,
                        color: "white",
                      }}
                    >
                      Venta
                    </span>
                  </div>
                  <p
                    style={{
                      margin: 0,
                      fontFamily: "'Rajdhani', sans-serif",
                      fontSize: "12px",
                      color: "#8892a4",
                      paddingLeft: "1.5rem",
                    }}
                  >
                    Pago único
                  </p>
                  <p
                    style={{
                      margin: 0,
                      fontFamily: "'Share Tech Mono', monospace",
                      fontSize: "18px",
                      fontWeight: 700,
                      color: "#8235f2",
                      paddingLeft: "1.5rem",
                    }}
                  >
                    {selectedWebType
                      ? formatPrice(selectedWebType.base_price_sale)
                      : "S/ —"}
                  </p>
                </label>
              </div>
            )}
            {errors.plan && (
              <p style={{ color: "#ff3366", fontSize: "12px", margin: 0 }}>
                ⚠ {errors.plan}
              </p>
            )}
          </div>

          {/* Frecuencia de pago — solo lectura */}
          {formData.plan && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.5rem",
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
                Frecuencia de pago
              </label>
              <div
                style={{
                  padding: "0.875rem 1rem",
                  borderRadius: "0.375rem",
                  backgroundColor: "rgba(63,229,229,0.05)",
                  border: "1px solid rgba(63,229,229,0.2)",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.625rem",
                }}
              >
                <svg
                  width="14"
                  height="14"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  style={{ color: "#3fe5e5", flexShrink: 0 }}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <span
                  style={{
                    fontFamily: "'Rajdhani', sans-serif",
                    fontSize: "14px",
                    fontWeight: 600,
                    color: "#3fe5e5",
                  }}
                >
                  {formData.payment_frequency === "mensual"
                    ? "Mensual"
                    : "Anual (pago único)"}
                </span>
                <span
                  style={{
                    fontFamily: "'Rajdhani', sans-serif",
                    fontSize: "12px",
                    color: "#8892a4",
                  }}
                >
                  — automático según el plan
                </span>
              </div>
            </div>
          )}

          {/* Características extra */}
          {webFeatures.length > 0 && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
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
                Características extra
              </label>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "0.75rem",
                }}
              >
                {webFeatures.map((feature) => (
                  <label
                    key={feature.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.75rem",
                      padding: "0.875rem 1rem",
                      borderRadius: "0.375rem",
                      cursor: "pointer",
                      backgroundColor: selectedFeatures.includes(feature.id)
                        ? "rgba(63,229,229,0.08)"
                        : "#1a1d30",
                      border: selectedFeatures.includes(feature.id)
                        ? "1px solid rgba(63,229,229,0.3)"
                        : "1px solid rgba(63,229,229,0.1)",
                      transition: "all 0.2s",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedFeatures.includes(feature.id)}
                      onChange={() => handleFeatureToggle(feature.id)}
                      style={{ accentColor: "#3fe5e5", flexShrink: 0 }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p
                        style={{
                          fontSize: "13px",
                          fontWeight: 500,
                          color: "white",
                          margin: 0,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {feature.name}
                      </p>
                      <p
                        style={{
                          fontFamily: "'Share Tech Mono', monospace",
                          color: "#3fe5e5",
                          fontSize: "11px",
                          margin: "0.2rem 0 0 0",
                        }}
                      >
                        +{formatPrice(feature.extra_price)}
                      </p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* ── PRECIOS Y PAGOS ───────────────────────────────────────────── */}
        <section style={sectionStyle}>
          <h3 style={sectionTitleStyle}>Precios y pagos</h3>

          <div style={grid3Style}>
            {/* Precio base — automático */}
            <AutoPriceField
              label="Precio base (S/)"
              value={basePrice || ""}
              hint="Según tipo de web y plan"
              error={errors.base_price}
            />

            {/* Precio extra — automático según características */}
            <AutoPriceField
              label="Precio extra (S/)"
              value={extraPrice}
              hint={
                selectedFeatures.length > 0
                  ? `${selectedFeatures.length} característica(s)`
                  : "Sin características"
              }
              color="#3fe5e5"
            />

            {/* Pago total — base + extra */}
            <AutoPriceField
              label="Pago total (S/)"
              value={totalPayment || ""}
              hint="Base + extras"
              color="#00ff88"
            />
          </div>

          {/* Dominio */}
          <div style={grid2Style}>
            <Input
              type="select"
              label="Precio de dominio"
              name="domain_price_type"
              value={formData.domain_price_type}
              onChange={handleChange}
              options={[
                { value: "ninguno", label: "Sin dominio" },
                { value: "200", label: "S/ 200 (estándar)" },
                { value: "otro", label: "Precio custom" },
              ]}
            />
            {formData.domain_price_type === "otro" && (
              <Input
                type="number"
                label="Precio custom de dominio (S/)"
                name="domain_custom_price"
                value={formData.domain_custom_price}
                onChange={handleChange}
                error={errors.domain_custom_price}
                placeholder="0.00"
                required
              />
            )}
          </div>

          {/* Resumen total con dominio */}
          {totalPayment > 0 && (
            <div
              style={{
                padding: "1.25rem",
                borderRadius: "0.5rem",
                backgroundColor: "rgba(63,229,229,0.06)",
                border: "1px solid rgba(63,229,229,0.2)",
              }}
            >
              <p
                style={{
                  fontFamily: "'Share Tech Mono', monospace",
                  fontSize: "10px",
                  color: "#8892a4",
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  margin: "0 0 0.75rem 0",
                }}
              >
                Resumen
              </p>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                }}
              >
                <div
                  style={{ display: "flex", justifyContent: "space-between" }}
                >
                  <span
                    style={{
                      fontFamily: "'Rajdhani', sans-serif",
                      fontSize: "13px",
                      color: "#8892a4",
                    }}
                  >
                    Precio base
                  </span>
                  <span
                    style={{
                      fontFamily: "'Share Tech Mono', monospace",
                      fontSize: "13px",
                      color: "white",
                    }}
                  >
                    {formatPrice(basePrice)}
                  </span>
                </div>
                {extraPrice > 0 && (
                  <div
                    style={{ display: "flex", justifyContent: "space-between" }}
                  >
                    <span
                      style={{
                        fontFamily: "'Rajdhani', sans-serif",
                        fontSize: "13px",
                        color: "#8892a4",
                      }}
                    >
                      Características extra
                    </span>
                    <span
                      style={{
                        fontFamily: "'Share Tech Mono', monospace",
                        fontSize: "13px",
                        color: "#3fe5e5",
                      }}
                    >
                      +{formatPrice(extraPrice)}
                    </span>
                  </div>
                )}
                {domainPrice > 0 && (
                  <div
                    style={{ display: "flex", justifyContent: "space-between" }}
                  >
                    <span
                      style={{
                        fontFamily: "'Rajdhani', sans-serif",
                        fontSize: "13px",
                        color: "#8892a4",
                      }}
                    >
                      Dominio
                    </span>
                    <span
                      style={{
                        fontFamily: "'Share Tech Mono', monospace",
                        fontSize: "13px",
                        color: "#3fe5e5",
                      }}
                    >
                      +{formatPrice(domainPrice)}
                    </span>
                  </div>
                )}
                <div
                  style={{
                    height: "1px",
                    backgroundColor: "rgba(63,229,229,0.2)",
                    margin: "0.25rem 0",
                  }}
                />
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "'Rajdhani', sans-serif",
                      fontSize: "14px",
                      fontWeight: 700,
                      color: "white",
                    }}
                  >
                    Pago total
                  </span>
                  <span
                    style={{
                      fontFamily: "'Share Tech Mono', monospace",
                      fontSize: "22px",
                      fontWeight: 700,
                      color: "#00ff88",
                    }}
                  >
                    {formatPrice(totalPayment + domainPrice)}
                  </span>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ── FECHAS Y OBSERVACIONES ────────────────────────────────────── */}
        <section style={sectionStyle}>
          <h3 style={sectionTitleStyle}>Fechas y observaciones</h3>

          <div style={grid2Style}>
            <Input
              type="date"
              label="Fecha de registro"
              name="registration_date"
              value={formData.registration_date}
              onChange={handleChange}
              error={errors.registration_date}
              required
            />
            <Input
              type="date"
              label="Fecha de entrega"
              name="delivery_date"
              value={formData.delivery_date}
              onChange={handleChange}
              hint="Cuándo se entregó o entregará la web"
            />
          </div>

          <Input
            type="textarea"
            label="Notas y observaciones"
            name="notes"
            value={formData.notes}
            onChange={handleChange}
            placeholder="Observaciones internas sobre el cliente..."
            rows={3}
          />
        </section>

        {/* Botones */}
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: "0.75rem",
            paddingBottom: "2rem",
          }}
        >
          <Button
            variant="secondary"
            onClick={() => navigate("/clientes")}
            disabled={isLoading}
          >
            Cancelar
          </Button>
          <Button type="submit" variant="primary" isLoading={isLoading}>
            {isLoading
              ? isEditMode
                ? "Guardando..."
                : "Registrando..."
              : isEditMode
                ? "Guardar cambios"
                : "Registrar cliente"}
          </Button>
        </div>
      </form>
    </div>
  );
}
