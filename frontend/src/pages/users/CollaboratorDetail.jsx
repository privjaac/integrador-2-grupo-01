// ==============================================================================
// COLLABORATORDETAIL.JSX v2 — Con cambio de CUPE + historial
// ==============================================================================

import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";
import { getCollaboratorById, toggleCollaboratorStatus } from "../../api/users";
import { getNextCupe, changeCupe, getCupeHistory } from "../../api/cupe";
import { formatDate } from "../../utils/formatDate";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import CupeChangeModal from "../../components/ui/CupeChangeModal";

function DetailRow({ label, value, valueColor }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "0.625rem 0",
        borderBottom: "1px solid rgba(255,255,255,0.04)",
        gap: "1rem",
      }}
    >
      <span
        style={{
          fontFamily: "'Share Tech Mono', monospace",
          fontSize: "10px",
          color: "#8892a4",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          flexShrink: 0,
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: "13px",
          fontWeight: 600,
          color: valueColor || "white",
          textAlign: "right",
        }}
      >
        {value || "—"}
      </span>
    </div>
  );
}

function DetailCard({ title, children }) {
  return (
    <div
      style={{
        backgroundColor: "#111427",
        border: "1px solid rgba(63,229,229,0.08)",
        borderRadius: "0.75rem",
        padding: "1.25rem 1.5rem",
      }}
    >
      <p
        style={{
          fontFamily: "'Share Tech Mono', monospace",
          fontSize: "10px",
          fontWeight: 700,
          color: "#3fe5e5",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          margin: "0 0 1rem 0",
          paddingBottom: "0.75rem",
          borderBottom: "1px solid rgba(63,229,229,0.08)",
        }}
      >
        {title}
      </p>
      {children}
    </div>
  );
}

const MOTIVO_LABELS = {
  error_generacion: "Error en la generación original",
  reingreso: "Reingreso del registro",
  correccion_administrativa: "Corrección administrativa",
  solicitud_cliente: "Solicitud del cliente",
  migracion_sistema: "Migración del sistema",
  otro: "Otro",
};

export default function CollaboratorDetail() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { id } = useParams();

  const [collab, setCollab] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [cupeHistory, setCupeHistory] = useState([]);

  const [toggleModal, setToggleModal] = useState({ isOpen: false });
  const [isToggling, setIsToggling] = useState(false);
  const [cupeModal, setCupeModal] = useState({ isOpen: false, newCupe: "" });
  const [isLoadingCupe, setIsLoadingCupe] = useState(false);
  const [errorModal, setErrorModal] = useState({ isOpen: false, message: "" });
  const [successModal, setSuccessModal] = useState({
    isOpen: false,
    message: "",
  });

  const loadCollab = async () => {
    try {
      const [collabData, history] = await Promise.all([
        getCollaboratorById(id),
        getCupeHistory("collaborator", id),
      ]);
      setCollab(collabData);
      setCupeHistory(history);
    } catch (err) {
      setErrorModal({
        isOpen: true,
        message: err.userMessage || "Error al cargar el colaborador.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadCollab();
  }, [id]);

  const handleToggleStatus = async () => {
    setIsToggling(true);
    try {
      await toggleCollaboratorStatus(Number(id), !collab.is_active);
      setToggleModal({ isOpen: false });
      setSuccessModal({
        isOpen: true,
        message: `Colaborador ${!collab.is_active ? "activado" : "desactivado"} correctamente.`,
      });
      await loadCollab();
    } catch (err) {
      setToggleModal({ isOpen: false });
      setErrorModal({
        isOpen: true,
        message: err.userMessage || "Error al cambiar el estado.",
      });
    } finally {
      setIsToggling(false);
    }
  };

  const handleOpenCupeModal = async () => {
    setIsLoadingCupe(true);
    try {
      const newCupe = await getNextCupe("collaborator");
      setCupeModal({ isOpen: true, newCupe });
    } catch (err) {
      setErrorModal({
        isOpen: true,
        message: "Error al generar el nuevo CUPE.",
      });
    } finally {
      setIsLoadingCupe(false);
    }
  };

  const handleCupeConfirm = async (motivo, observaciones) => {
    await changeCupe(
      "collaborator",
      id,
      cupeModal.newCupe,
      motivo,
      observaciones,
      user?.username,
    );
    setCupeModal({ isOpen: false, newCupe: "" });
    setSuccessModal({
      isOpen: true,
      message: `CUPE cambiado de ${collab.cupe} a ${cupeModal.newCupe} correctamente.`,
    });
    await loadCollab();
  };

  if (isLoading)
    return <LoadingSpinner fullPage label="Cargando colaborador..." />;

  if (!collab)
    return (
      <div style={{ textAlign: "center", padding: "4rem", color: "#8892a4" }}>
        <p>Colaborador no encontrado.</p>
        <Button
          variant="secondary"
          onClick={() => navigate("/usuarios")}
          style={{ marginTop: "1rem" }}
        >
          Volver
        </Button>
      </div>
    );

  const canToggle = can(user, "users", "delete") && collab.id !== user?.id;
  const isSuperAdmin = user?.role === "L1";

  return (
    <div
      style={{
        maxWidth: "900px",
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: "1.5rem",
      }}
    >
      {/* Header */}
      <div>
        <button
          onClick={() => navigate("/usuarios")}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            padding: "0.5rem 0.875rem",
            borderRadius: "0.375rem",
            backgroundColor: "transparent",
            border: "1px solid rgba(63,229,229,0.2)",
            color: "#c5cdd8",
            fontSize: "13px",
            fontFamily: "'Rajdhani', sans-serif",
            fontWeight: 600,
            cursor: "pointer",
            marginBottom: "1.25rem",
            transition: "all 0.2s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = "#3fe5e5";
            e.currentTarget.style.color = "#3fe5e5";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "rgba(63,229,229,0.2)";
            e.currentTarget.style.color = "#c5cdd8";
          }}
        >
          <svg
            width="14"
            height="14"
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
          Volver a colaboradores
        </button>

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
            {/* CUPE con botón de cambio */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.625rem",
                marginBottom: "0.5rem",
              }}
            >
              <p
                style={{
                  fontFamily: "'Share Tech Mono', monospace",
                  fontSize: "12px",
                  color: "#3fe5e5",
                  letterSpacing: "0.08em",
                  margin: 0,
                }}
              >
                // {collab.cupe}
              </p>
              {isSuperAdmin && (
                <button
                  onClick={handleOpenCupeModal}
                  disabled={isLoadingCupe}
                  title="Cambiar CUPE"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.25rem",
                    padding: "0.25rem 0.5rem",
                    borderRadius: "0.25rem",
                    backgroundColor: "rgba(255,184,0,0.08)",
                    border: "1px solid rgba(255,184,0,0.25)",
                    color: "#ffb800",
                    fontSize: "10px",
                    fontFamily: "'Share Tech Mono', monospace",
                    letterSpacing: "0.05em",
                    cursor: isLoadingCupe ? "wait" : "pointer",
                    transition: "all 0.2s",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor =
                      "rgba(255,184,0,0.15)";
                    e.currentTarget.style.borderColor = "rgba(255,184,0,0.5)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor =
                      "rgba(255,184,0,0.08)";
                    e.currentTarget.style.borderColor = "rgba(255,184,0,0.25)";
                  }}
                >
                  {isLoadingCupe ? "..." : "⟳ CAMBIAR CUPE"}
                </button>
              )}
            </div>
            <h1
              style={{
                fontFamily: "'Orbitron', monospace",
                fontSize: "20px",
                fontWeight: 700,
                color: "white",
                letterSpacing: "0.1em",
                margin: "0 0 0.75rem 0",
              }}
            >
              {collab.first_name.toUpperCase()} {collab.last_name.toUpperCase()}
            </h1>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                flexWrap: "wrap",
              }}
            >
              <Badge status={collab.is_active} />
              <span
                style={{
                  fontSize: "12px",
                  color: "#8892a4",
                  fontFamily: "'Share Tech Mono', monospace",
                }}
              >
                {collab.role} · {collab.role_name}
              </span>
            </div>
          </div>

          <div style={{ display: "flex", gap: "0.75rem", flexShrink: 0 }}>
            {can(user, "users", "edit") && (
              <Button
                variant="secondary"
                onClick={() => navigate(`/usuarios/${id}/editar`)}
              >
                <svg
                  width="14"
                  height="14"
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
              </Button>
            )}
            {canToggle && (
              <Button
                variant={collab.is_active ? "danger" : "primary"}
                onClick={() => setToggleModal({ isOpen: true })}
              >
                {collab.is_active ? "Desactivar" : "Activar"}
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Tarjetas */}
      <div
        style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}
      >
        <DetailCard title="Datos personales">
          <DetailRow label="Nombres" value={collab.first_name} />
          <DetailRow label="Apellidos" value={collab.last_name} />
          <DetailRow label="Tipo doc." value={collab.document_type} />
          <DetailRow
            label="Documento"
            value={collab.document_number}
            valueColor="#c5cdd8"
          />
          <DetailRow label="Ciudad" value={collab.city} />
        </DetailCard>

        <DetailCard title="Contacto">
          <DetailRow label="Email" value={collab.email} valueColor="#3fe5e5" />
          <DetailRow label="Teléfono" value={collab.phone} />
        </DetailCard>

        <DetailCard title="Acceso al sistema">
          <DetailRow
            label="Usuario"
            value={`@${collab.username}`}
            valueColor="#3fe5e5"
          />
          <DetailRow label="Rol" value={collab.role_name} />
          <DetailRow label="Nivel" value={collab.role} valueColor="#3fe5e5" />
          <DetailRow label="Área" value={collab.work_area} />
          <DetailRow
            label="Estado"
            value={collab.is_active ? "Activo" : "Inactivo"}
            valueColor={collab.is_active ? "#00ff88" : "#ff3366"}
          />
        </DetailCard>

        <DetailCard title="Registro">
          <DetailRow
            label="Registrado el"
            value={collab.created_at ? formatDate(collab.created_at) : "—"}
          />
          <DetailRow
            label="Última actualización"
            value={collab.updated_at ? formatDate(collab.updated_at) : "—"}
          />
        </DetailCard>
      </div>

      {/* Historial CUPE */}
      {isSuperAdmin && (
        <DetailCard title="Historial de cambios de CUPE">
          {cupeHistory.length === 0 ? (
            <p
              style={{
                fontSize: "13px",
                color: "#8892a4",
                margin: 0,
                textAlign: "center",
                padding: "1rem 0",
              }}
            >
              Sin cambios de CUPE registrados.
            </p>
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
                paddingTop: "0.25rem",
              }}
            >
              {cupeHistory.map((entry, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "1rem",
                    padding: "0.875rem 1rem",
                    borderRadius: "0.5rem",
                    backgroundColor: "rgba(255,184,0,0.04)",
                    border: "1px solid rgba(255,184,0,0.15)",
                  }}
                >
                  <div
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      backgroundColor: "#ffb800",
                      flexShrink: 0,
                      marginTop: "4px",
                    }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.75rem",
                        flexWrap: "wrap",
                        marginBottom: "0.25rem",
                      }}
                    >
                      <span
                        style={{
                          fontFamily: "'Orbitron', monospace",
                          fontSize: "13px",
                          color: "#00ff88",
                        }}
                      >
                        → {entry.new_cupe}
                      </span>
                      <span
                        style={{
                          fontFamily: "'Share Tech Mono', monospace",
                          fontSize: "10px",
                          color: "#8892a4",
                        }}
                      >
                        {entry.created_at ? formatDate(entry.created_at) : "—"}
                      </span>
                    </div>
                    <p
                      style={{
                        fontFamily: "'Rajdhani', sans-serif",
                        fontSize: "13px",
                        color: "#c5cdd8",
                        margin: 0,
                      }}
                    >
                      <strong style={{ color: "#ffb800" }}>Motivo:</strong>{" "}
                      {MOTIVO_LABELS[entry.motivo] || entry.motivo}
                    </p>
                    {entry.observaciones && (
                      <p
                        style={{
                          fontFamily: "'Rajdhani', sans-serif",
                          fontSize: "12px",
                          color: "#8892a4",
                          margin: "0.25rem 0 0 0",
                        }}
                      >
                        {entry.observaciones}
                      </p>
                    )}
                    {entry.authorized_by && (
                      <p
                        style={{
                          fontFamily: "'Share Tech Mono', monospace",
                          fontSize: "10px",
                          color: "#8892a4",
                          margin: "0.25rem 0 0 0",
                        }}
                      >
                        Autorizado por: @{entry.authorized_by}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </DetailCard>
      )}

      {/* Modales */}
      <CupeChangeModal
        isOpen={cupeModal.isOpen}
        onClose={() => setCupeModal({ isOpen: false, newCupe: "" })}
        onConfirm={handleCupeConfirm}
        currentCupe={collab.cupe}
        newCupe={cupeModal.newCupe}
        entityName={`${collab.first_name} ${collab.last_name}`}
        entityType="colaborador"
      />

      <Modal
        isOpen={toggleModal.isOpen}
        onClose={() => setToggleModal({ isOpen: false })}
        variant="confirm"
        size="sm"
      >
        <Modal.Header
          title={
            collab.is_active ? "Desactivar colaborador" : "Activar colaborador"
          }
          onClose={() => setToggleModal({ isOpen: false })}
        />
        <Modal.Body>
          <p style={{ textAlign: "center" }}>
            ¿{collab.is_active ? "Desactivar" : "Activar"} a{" "}
            <strong style={{ color: "white" }}>
              {collab.first_name} {collab.last_name}
            </strong>
            ?
          </p>
        </Modal.Body>
        <Modal.Footer>
          <Button
            variant="secondary"
            onClick={() => setToggleModal({ isOpen: false })}
            disabled={isToggling}
          >
            Cancelar
          </Button>
          <Button
            variant={collab.is_active ? "danger" : "primary"}
            onClick={handleToggleStatus}
            isLoading={isToggling}
          >
            {collab.is_active ? "Sí, desactivar" : "Sí, activar"}
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
  );
}
