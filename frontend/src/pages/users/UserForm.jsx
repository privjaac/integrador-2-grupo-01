// ==============================================================================
// USERFORM.JSX v2 — Formulario con espaciado interno correcto (style inline)
// ==============================================================================

import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { can, getCreatableRoles } from "../../utils/permissions";
import {
  createCollaborator,
  updateCollaborator,
  getCollaboratorById,
} from "../../api/users";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import { useToast } from "../../components/ui/Toast";
import LoadingSpinner from "../../components/ui/LoadingSpinner";

const PERU_CITIES = [
  "Lima",
  "Arequipa",
  "Trujillo",
  "Chiclayo",
  "Piura",
  "Iquitos",
  "Cusco",
  "Huancayo",
  "Tacna",
  "Juliaca",
  "Ica",
  "Pucallpa",
  "Chimbote",
  "Ayacucho",
  "Cajamarca",
  "Puno",
  "Tumbes",
  "Moquegua",
].map((c) => ({ value: c, label: c }));
const WORK_AREAS = [
  "Gerencia",
  "Desarrollo",
  "Frontend",
  "Backend",
  "Base de Datos",
  "QA",
  "Diseño",
  "Marketing",
  "Soporte",
  "Gestión de Proyectos",
].map((a) => ({ value: a, label: a }));

const INITIAL_FORM = {
  username: "",
  password: "",
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  document_type: "DNI",
  document_number: "",
  role: "",
  city: "Lima",
  work_area: "Desarrollo",
};

// Estilos reutilizables
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

export default function UserForm() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { id } = useParams();

  const { showToast } = useToast();
  const isEditMode = Boolean(id);
  const action = isEditMode ? "edit" : "create";
  const creatableRoles = getCreatableRoles(user);

  useEffect(() => {
    if (!can(user, "users", action)) navigate("/usuarios", { replace: true });
  }, [user, action, navigate]);

  const [formData, setFormData] = useState(INITIAL_FORM);
  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingData, setIsLoadingData] = useState(isEditMode);

  useEffect(() => {
    if (!isEditMode) return;
    getCollaboratorById(id)
      .then((collab) => {
        setFormData({
          username: collab.username || "",
          password: "",
          first_name: collab.first_name || "",
          last_name: collab.last_name || "",
          email: collab.email || "",
          phone: collab.phone || "",
          document_type: collab.document_type || "DNI",
          document_number: collab.document_number || "",
          role: collab.role || "",
          city: collab.city || "Lima",
          work_area: collab.work_area || "Desarrollo",
        });
      })
      .catch((err) =>
        showToast(
          "error",
          "ERROR AL CARGAR",
          err.userMessage || "Error al cargar los datos.",
        ),
      )
      .finally(() => setIsLoadingData(false));
  }, [isEditMode, id]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: "" }));
  };

  const validateForm = () => {
    const newErrors = {};
    if (!formData.first_name.trim())
      newErrors.first_name = "El nombre es requerido.";
    if (!formData.last_name.trim())
      newErrors.last_name = "El apellido es requerido.";
    if (!formData.username.trim() || formData.username.trim().length < 3)
      newErrors.username = "El usuario debe tener al menos 3 caracteres.";
    if (!isEditMode && (!formData.password || formData.password.length < 6))
      newErrors.password = "La contraseña debe tener al menos 6 caracteres.";
    if (!formData.email.trim()) newErrors.email = "El correo es requerido.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email))
      newErrors.email = "El formato del correo no es válido.";
    if (!formData.phone.trim()) newErrors.phone = "El teléfono es requerido.";
    if (!formData.document_number.trim())
      newErrors.document_number = "El número de documento es requerido.";
    if (!formData.role) newErrors.role = "Seleccioná el rol.";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;
    setIsLoading(true);
    try {
      const payload = { ...formData };
      if (isEditMode && !payload.password) delete payload.password;
      if (isEditMode) {
        await updateCollaborator(id, payload);
        showToast(
          "success",
          "CAMBIOS GUARDADOS",
          "Colaborador actualizado correctamente.",
        );
        navigate("/usuarios");
      } else {
        await createCollaborator(payload);
        showToast(
          "success",
          "COLABORADOR REGISTRADO",
          "Colaborador registrado correctamente.",
        );
        navigate("/usuarios");
      }
    } catch (err) {
      showToast(
        "error",
        "ERROR AL GUARDAR",
        err.userMessage || err.response?.data?.detail || "Error al guardar.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoadingData)
    return <LoadingSpinner fullPage label="Cargando datos..." />;

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
          onClick={() => navigate("/usuarios")}
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
            {isEditMode ? "Editar colaborador" : "Registrar colaborador"}
          </h2>
          <p
            style={{
              color: "#8892a4",
              fontSize: "14px",
              margin: "0.25rem 0 0 0",
            }}
          >
            {isEditMode
              ? "Modificá los datos del colaborador"
              : "Completá los datos para registrar un nuevo colaborador"}
          </p>
        </div>
      </div>

      <form
        onSubmit={handleSubmit}
        noValidate
        style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}
      >
        {/* ── DATOS PERSONALES ────────────────────────────────────────────── */}
        <section style={sectionStyle}>
          <h3 style={sectionTitleStyle}>Datos personales</h3>

          <div style={grid2Style}>
            <Input
              label="Nombres"
              name="first_name"
              value={formData.first_name}
              onChange={handleChange}
              error={errors.first_name}
              placeholder="Ej: Pedro"
              required
            />
            <Input
              label="Apellidos"
              name="last_name"
              value={formData.last_name}
              onChange={handleChange}
              error={errors.last_name}
              placeholder="Ej: García"
              required
            />
          </div>

          <div style={grid2Style}>
            <Input
              type="select"
              label="Tipo de documento"
              name="document_type"
              value={formData.document_type}
              onChange={handleChange}
              options={[
                { value: "DNI", label: "DNI" },
                { value: "CE", label: "Carné de Extranjería" },
                { value: "Pasaporte", label: "Pasaporte" },
              ]}
            />
            <Input
              label="Número de documento"
              name="document_number"
              value={formData.document_number}
              onChange={handleChange}
              error={errors.document_number}
              placeholder="Ej: 45678901"
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
              placeholder="colaborador@elomux.com"
              required
            />
            <Input
              type="tel"
              label="Teléfono"
              name="phone"
              value={formData.phone}
              onChange={handleChange}
              error={errors.phone}
              placeholder="Ej: 999000001"
              required
            />
          </div>

          <div style={grid2Style}>
            <Input
              type="select"
              label="Ciudad"
              name="city"
              value={formData.city}
              onChange={handleChange}
              options={PERU_CITIES}
            />
            <Input
              type="select"
              label="Área de trabajo"
              name="work_area"
              value={formData.work_area}
              onChange={handleChange}
              options={WORK_AREAS}
            />
          </div>
        </section>

        {/* ── ACCESO AL SISTEMA ────────────────────────────────────────────── */}
        <section style={sectionStyle}>
          <h3 style={sectionTitleStyle}>Acceso al sistema</h3>

          <div style={grid2Style}>
            <Input
              label="Nombre de usuario"
              name="username"
              value={formData.username}
              onChange={handleChange}
              error={errors.username}
              placeholder="Ej: pedro.garcia"
              hint="Solo letras, números y puntos"
              required
            />
            <Input
              type="password"
              label={isEditMode ? "Nueva contraseña (opcional)" : "Contraseña"}
              name="password"
              value={formData.password}
              onChange={handleChange}
              error={errors.password}
              placeholder={
                isEditMode
                  ? "Dejá vacío para no cambiar"
                  : "Mínimo 6 caracteres"
              }
              required={!isEditMode}
            />
          </div>

          <Input
            type="select"
            label="Rol en el sistema"
            name="role"
            value={formData.role}
            onChange={handleChange}
            error={errors.role}
            placeholder="Seleccioná el rol..."
            options={creatableRoles}
            hint={`Podés asignar roles de menor jerarquía que el tuyo (${user?.role_name})`}
            required
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
            onClick={() => navigate("/usuarios")}
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
                : "Registrar colaborador"}
          </Button>
        </div>
      </form>
    </div>
  );
}
