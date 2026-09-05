// ==============================================================================
// ROLESPAGE.JSX v6 — Hexágonos por nivel como en el mockup HTML
//
// Colores por nivel (según mockup):
//   L1 → rojo/danger   (el más alto, más visible)
//   L2 → púrpura
//   L3 → azul
//   L4 → cyan
//   L5 → gris
//   L6+ → gris oscuro
// ==============================================================================

import { useState, useEffect } from "react";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";
import { getRoles, createRole, updateRole } from "../../api/roles";
import Table from "../../components/ui/Table";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Modal from "../../components/ui/Modal";
import LoadingSpinner from "../../components/ui/LoadingSpinner";

const INITIAL_ROLE_FORM = {
  name: "",
  can_create_users: false,
  min_role_create: "",
  description: "",
};

// Colores de hexágono según nivel — igual que el mockup
const HEX_COLORS = {
  1: {
    background: "linear-gradient(135deg, #ff3366, #ff6688)",
    color: "#05060f",
  },
  2: {
    background: "linear-gradient(135deg, #8235f2, #a066ff)",
    color: "white",
  },
  3: {
    background: "linear-gradient(135deg, #4540d9, #6b6fff)",
    color: "white",
  },
  4: {
    background: "linear-gradient(135deg, #3fe5e5, #44ddff)",
    color: "#05060f",
  },
  5: {
    background: "linear-gradient(135deg, #8892a4, #aabbcc)",
    color: "#05060f",
  },
};

// Componente hexágono reutilizable
function RoleHex({ hierarchy, size = 48 }) {
  const colors = HEX_COLORS[hierarchy] || {
    background: "linear-gradient(135deg, #374151, #4b5563)",
    color: "#c5cdd8",
  };
  return (
    <div
      style={{
        width: `${size}px`,
        height: `${size}px`,
        background: colors.background,
        clipPath:
          "polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "'Orbitron', monospace",
        fontSize: size > 40 ? "12px" : "10px",
        fontWeight: 700,
        color: colors.color,
        flexShrink: 0,
      }}
    >
      L{hierarchy}
    </div>
  );
}

export default function RolesPage() {
  const { user } = useAuth();

  const [roles, setRoles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingRole, setEditingRole] = useState(null);
  const [formData, setFormData] = useState(INITIAL_ROLE_FORM);
  const [errors, setErrors] = useState({});
  const [isSaving, setIsSaving] = useState(false);
  const [errorModal, setErrorModal] = useState({ isOpen: false, message: "" });
  const [successModal, setSuccessModal] = useState({
    isOpen: false,
    message: "",
  });

  const loadRoles = async () => {
    setIsLoading(true);
    try {
      setRoles(await getRoles());
    } catch (err) {
      setErrorModal({
        isOpen: true,
        message: err.userMessage || "Error al cargar roles.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadRoles();
  }, []);

  const nextHierarchy =
    roles.length > 0 ? Math.max(...roles.map((r) => r.hierarchy)) + 1 : 1;

  const roleOptions = roles
    .filter((r) => r.hierarchy > 1)
    .map((r) => ({
      value: String(r.hierarchy),
      label: `L${r.hierarchy} — ${r.name}`,
    }));

  const handleNewRole = () => {
    setEditingRole(null);
    setFormData(INITIAL_ROLE_FORM);
    setErrors({});
    setShowForm(true);
  };
  const handleEditRole = (role) => {
    setEditingRole(role);
    setFormData({
      name: role.name,
      can_create_users: role.can_create_users,
      min_role_create: role.min_role_create ? String(role.min_role_create) : "",
      description: role.description || "",
    });
    setErrors({});
    setShowForm(true);
  };
  const handleCloseForm = () => {
    setShowForm(false);
    setEditingRole(null);
    setFormData(INITIAL_ROLE_FORM);
    setErrors({});
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: "" }));
  };

  const validateForm = () => {
    const newErrors = {};
    if (!formData.name.trim() || formData.name.trim().length < 2)
      newErrors.name = "El nombre debe tener al menos 2 caracteres.";
    if (formData.can_create_users && !formData.min_role_create)
      newErrors.min_role_create = "Seleccioná desde qué nivel puede crear.";
    if (!formData.description.trim())
      newErrors.description = "La descripción es requerida.";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;
    setIsSaving(true);
    try {
      const payload = {
        name: formData.name,
        hierarchy: editingRole ? editingRole.hierarchy : nextHierarchy,
        can_create_users: formData.can_create_users,
        min_role_create:
          formData.can_create_users && formData.min_role_create
            ? Number(formData.min_role_create)
            : null,
        description: formData.description,
      };
      if (editingRole) {
        await updateRole(editingRole.id, payload);
        setSuccessModal({
          isOpen: true,
          message: `Rol "${payload.name}" actualizado.`,
        });
      } else {
        await createRole(payload);
        setSuccessModal({
          isOpen: true,
          message: `Rol "${payload.name}" creado con nivel L${nextHierarchy}.`,
        });
      }
      handleCloseForm();
      loadRoles();
    } catch (err) {
      setErrorModal({
        isOpen: true,
        message:
          err.userMessage || err.response?.data?.detail || "Error al guardar.",
      });
    } finally {
      setIsSaving(false);
    }
  };

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
            Roles y jerarquías
          </h2>
          <p
            style={{
              color: "#8892a4",
              fontSize: "14px",
              margin: "0.25rem 0 0 0",
            }}
          >
            Define los niveles de acceso del equipo ELOMUX
          </p>
        </div>
        {can(user, "roles", "create") && (
          <Button variant="primary" size="lg" onClick={handleNewRole}>
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
            Nuevo rol
          </Button>
        )}
      </div>

      {/* Tabla + Panel */}
      <div style={{ display: "flex", gap: "1.5rem", alignItems: "flex-start" }}>
        {/* Tabla */}
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
          ) : (
            <Table aria-label="Roles">
              <Table.Head>
                <Table.Row>
                  <Table.HeadCell>Nivel</Table.HeadCell>
                  <Table.HeadCell>Rol</Table.HeadCell>
                  <Table.HeadCell>Puede crear desde</Table.HeadCell>
                  <Table.HeadCell>Descripción</Table.HeadCell>
                  {can(user, "roles", "edit") && (
                    <Table.HeadCell>Acciones</Table.HeadCell>
                  )}
                </Table.Row>
              </Table.Head>
              <Table.Body>
                {roles.length === 0 ? (
                  <Table.Empty colSpan={5} message="No hay roles registrados" />
                ) : (
                  roles.map((role, idx) => (
                    <Table.Row key={role.id} index={idx}>
                      {/* Hexágono del nivel */}
                      <Table.Cell>
                        <RoleHex hierarchy={role.hierarchy} size={48} />
                      </Table.Cell>

                      {/* Nombre */}
                      <Table.Cell>
                        <p
                          style={{ fontWeight: 600, color: "white", margin: 0 }}
                        >
                          {role.name}
                        </p>
                      </Table.Cell>

                      {/* Puede crear desde */}
                      <Table.Cell>
                        {role.can_create_users && role.min_role_create ? (
                          <div>
                            <Badge status="activo" dot={false}>
                              Sí
                            </Badge>
                            <p
                              style={{
                                color: "#8892a4",
                                fontSize: "11px",
                                fontFamily: "'Share Tech Mono', monospace",
                                margin: "0.3rem 0 0 0",
                              }}
                            >
                              Desde L{role.min_role_create} en adelante
                            </p>
                          </div>
                        ) : (
                          <Badge status="inactivo" dot={false}>
                            No
                          </Badge>
                        )}
                      </Table.Cell>

                      {/* Descripción */}
                      <Table.Cell>
                        <p
                          style={{
                            color: "#8892a4",
                            fontSize: "13px",
                            maxWidth: "280px",
                            margin: 0,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          }}
                          title={role.description}
                        >
                          {role.description}
                        </p>
                      </Table.Cell>

                      {/* Acciones — L1 Superadmin no se puede editar */}
                      {can(user, "roles", "edit") && (
                        <Table.Cell>
                          {role.hierarchy !== 1 ? (
                            <button
                              onClick={() => handleEditRole(role)}
                              title="Editar rol"
                              style={{
                                padding: "0.375rem",
                                borderRadius: "0.375rem",
                                background: "transparent",
                                border: "none",
                                color: "#8892a4",
                                cursor: "pointer",
                              }}
                              onMouseEnter={(e) =>
                                (e.currentTarget.style.backgroundColor =
                                  "rgba(63,229,229,0.1)")
                              }
                              onMouseLeave={(e) =>
                                (e.currentTarget.style.backgroundColor =
                                  "transparent")
                              }
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
                          ) : (
                            <span
                              style={{
                                fontFamily: "'Share Tech Mono', monospace",
                                fontSize: "10px",
                                color: "#374151",
                                letterSpacing: "0.05em",
                              }}
                            >
                              protegido
                            </span>
                          )}
                        </Table.Cell>
                      )}
                    </Table.Row>
                  ))
                )}
              </Table.Body>
            </Table>
          )}
        </div>

        {/* Panel lateral */}
        {showForm && can(user, "roles", "create") && (
          <div
            style={{
              width: "340px",
              flexShrink: 0,
              borderRadius: "0.5rem",
              backgroundColor: "#111427",
              border: "1px solid rgba(63,229,229,0.2)",
              overflow: "hidden",
            }}
          >
            {/* Header del panel */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "1.25rem 1.5rem",
                borderBottom: "1px solid rgba(63,229,229,0.1)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.875rem",
                }}
              >
                {/* Hexágono preview del nuevo nivel */}
                <RoleHex
                  hierarchy={
                    editingRole ? editingRole.hierarchy : nextHierarchy
                  }
                  size={36}
                />
                <h3
                  style={{
                    fontFamily: "'Rajdhani', sans-serif",
                    color: "#3fe5e5",
                    fontSize: "16px",
                    fontWeight: 600,
                    margin: 0,
                  }}
                >
                  {editingRole ? `Editar: ${editingRole.name}` : "Nuevo rol"}
                </h3>
              </div>
              <button
                onClick={handleCloseForm}
                style={{
                  padding: "0.375rem",
                  borderRadius: "0.375rem",
                  background: "transparent",
                  border: "none",
                  color: "#8892a4",
                  cursor: "pointer",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.backgroundColor =
                    "rgba(255,255,255,0.05)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.backgroundColor = "transparent")
                }
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

            {/* Formulario */}
            <form
              onSubmit={handleSubmit}
              noValidate
              style={{
                padding: "1.5rem",
                display: "flex",
                flexDirection: "column",
                gap: "1.25rem",
              }}
            >
              <Input
                label="Nombre del rol"
                name="name"
                value={formData.name}
                onChange={handleChange}
                error={errors.name}
                placeholder="Ej: Tech Lead"
                required
              />

              {/* Nivel — solo lectura con hexágono */}
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
                  Nivel jerárquico
                </label>
                <div
                  style={{
                    padding: "0.875rem 1rem",
                    borderRadius: "0.375rem",
                    backgroundColor: "rgba(63,229,229,0.05)",
                    border: "1px solid rgba(63,229,229,0.2)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <RoleHex
                    hierarchy={
                      editingRole ? editingRole.hierarchy : nextHierarchy
                    }
                    size={52}
                  />
                </div>
                <p
                  style={{
                    fontFamily: "'Rajdhani', sans-serif",
                    fontSize: "12px",
                    color: "#8892a4",
                    margin: 0,
                  }}
                >
                  {editingRole
                    ? "El nivel jerárquico no puede modificarse una vez creado."
                    : `Se asigna automáticamente — el nivel máximo actual es L${nextHierarchy - 1}.`}
                </p>
              </div>

              {/* Puede crear usuarios */}
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
                  Permisos de creación
                </label>
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.875rem",
                    padding: "0.875rem 1rem",
                    borderRadius: "0.375rem",
                    cursor: "pointer",
                    backgroundColor: formData.can_create_users
                      ? "rgba(63,229,229,0.08)"
                      : "#1a1d30",
                    border: `1px solid ${formData.can_create_users ? "rgba(63,229,229,0.3)" : "rgba(63,229,229,0.1)"}`,
                    transition: "all 0.2s",
                  }}
                >
                  <input
                    type="checkbox"
                    name="can_create_users"
                    checked={formData.can_create_users}
                    onChange={handleChange}
                    style={{
                      accentColor: "#3fe5e5",
                      width: "16px",
                      height: "16px",
                      flexShrink: 0,
                    }}
                  />
                  <span
                    style={{
                      fontSize: "14px",
                      color: "white",
                      fontFamily: "'Rajdhani', sans-serif",
                      fontWeight: 500,
                    }}
                  >
                    Puede crear usuarios
                  </span>
                </label>
              </div>

              {formData.can_create_users && (
                <Input
                  type="select"
                  label="Puede crear usuarios desde el nivel"
                  name="min_role_create"
                  value={formData.min_role_create}
                  onChange={handleChange}
                  error={errors.min_role_create}
                  placeholder="Seleccioná el nivel inicial..."
                  options={roleOptions}
                  hint="Podrá crear usuarios de ese nivel y los inferiores. L1 solo puede ser creado por otro Superadmin."
                  required
                />
              )}

              <Input
                type="textarea"
                label="Descripción del rol"
                name="description"
                value={formData.description}
                onChange={handleChange}
                error={errors.description}
                placeholder="Qué responsabilidades tiene este rol..."
                rows={3}
                required
              />

              <div
                style={{
                  display: "flex",
                  gap: "0.75rem",
                  paddingTop: "0.25rem",
                }}
              >
                <Button
                  variant="secondary"
                  onClick={handleCloseForm}
                  disabled={isSaving}
                  style={{ flex: 1 }}
                >
                  Cancelar
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  isLoading={isSaving}
                  style={{ flex: 1 }}
                >
                  {editingRole ? "Guardar cambios" : `Crear L${nextHierarchy}`}
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
