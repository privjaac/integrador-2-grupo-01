// ==============================================================================
// CLIENTDETAIL.JSX v2 — Con cambio de CUPE + historial de cambios
//
// Ruta: /clientes/:id
// Solo Superadmin (L1) puede cambiar el CUPE.
// El historial de cambios se muestra al final de la página.
// ==============================================================================

import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";
import { getClientById, deactivateClient } from "../../api/clients";
import { getNextCupe, changeCupe, getCupeHistory } from "../../api/cupe";
import {
  formatDate,
  formatDateRelative,
  isExpired,
} from "../../utils/formatDate";
import { formatPrice } from "../../utils/formatPrice";
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

// Etiqueta de motivo legible
const MOTIVO_LABELS = {
  error_generacion: "Error en la generación original",
  reingreso: "Reingreso del registro",
  correccion_administrativa: "Corrección administrativa",
  solicitud_cliente: "Solicitud del cliente",
  migracion_sistema: "Migración del sistema",
  otro: "Otro",
};

export default function ClientDetail() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { id } = useParams();

  const [client, setClient] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [cupeHistory, setCupeHistory] = useState([]);

  // Modal de dar de baja
  const [bajaModal, setBajaModal] = useState({ isOpen: false });
  const [isDeactivating, setIsDeactivating] = useState(false);

  // Modal de cambio de CUPE
  const [cupeModal, setCupeModal] = useState({ isOpen: false, newCupe: "" });
  const [isLoadingCupe, setIsLoadingCupe] = useState(false);

  // Modales de feedback
  const [errorModal, setErrorModal] = useState({ isOpen: false, message: "" });
  const [successModal, setSuccessModal] = useState({
    isOpen: false,
    message: "",
  });

  // ── CARGA ──────────────────────────────────────────────────────────────────

  const loadClient = async () => {
    try {
      const [clientData, history] = await Promise.all([
        getClientById(id),
        getCupeHistory("client", id),
      ]);
      setClient(clientData);
      setCupeHistory(history);
    } catch (err) {
      setErrorModal({
        isOpen: true,
        message: err.userMessage || "Error al cargar el cliente.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadClient();
  }, [id]);

  // ── DAR DE BAJA ────────────────────────────────────────────────────────────

  const handleBaja = async () => {
    setIsDeactivating(true);
    try {
      await deactivateClient(id);
      setBajaModal({ isOpen: false });
      setSuccessModal({
        isOpen: true,
        message: `Cliente "${client.name}" dado de baja correctamente.`,
      });
      await loadClient();
    } catch (err) {
      setBajaModal({ isOpen: false });
      setErrorModal({
        isOpen: true,
        message: err.userMessage || "Error al dar de baja.",
      });
    } finally {
      setIsDeactivating(false);
    }
  };

  // ── ABRIR MODAL CUPE — genera el nuevo CUPE antes de mostrar el modal ──────

  const handleOpenCupeModal = async () => {
    setIsLoadingCupe(true);
    try {
      const newCupe = await getNextCupe("client");
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

  // ── CONFIRMAR CAMBIO DE CUPE ───────────────────────────────────────────────

  const handleCupeConfirm = async (motivo, observaciones) => {
    await changeCupe(
      "client",
      id,
      cupeModal.newCupe,
      motivo,
      observaciones,
      user?.username,
    );
    setCupeModal({ isOpen: false, newCupe: "" });
    setSuccessModal({
      isOpen: true,
      message: `CUPE cambiado de ${client.cupe} a ${cupeModal.newCupe} correctamente.`,
    });
    await loadClient(); // recarga para mostrar el nuevo CUPE
  };

  if (isLoading) return <LoadingSpinner fullPage label="Cargando cliente..." />;

  if (!client)
    return (
      <div style={{ textAlign: "center", padding: "4rem", color: "#8892a4" }}>
        <p>Cliente no encontrado.</p>
        <Button
          variant="secondary"
          onClick={() => navigate("/clientes")}
          style={{ marginTop: "1rem" }}
        >
          Volver
        </Button>
      </div>
    );

  const domainPrice =
    client.domain_price_type === "200"
      ? 200
      : client.domain_price_type === "otro"
        ? client.domain_custom_price || 0
        : 0;
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
          onClick={() => navigate("/clientes")}
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
          Volver a clientes
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
            {/* CUPE con botón de cambio inline */}
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
                // {client.cupe}
              </p>
              {/* Botón cambiar CUPE — solo Superadmin */}
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
                fontSize: "22px",
                fontWeight: 700,
                color: "white",
                letterSpacing: "0.1em",
                margin: "0 0 0.75rem 0",
              }}
            >
              {client.name.toUpperCase()}
            </h1>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                flexWrap: "wrap",
              }}
            >
              <Badge status={client.status} />
              <Badge status={client.plan} />
              {client.web_type_name && (
                <span
                  style={{
                    fontSize: "12px",
                    color: "#8892a4",
                    fontFamily: "'Rajdhani', sans-serif",
                  }}
                >
                  {client.web_type_name}
                </span>
              )}
            </div>
          </div>

          <div style={{ display: "flex", gap: "0.75rem", flexShrink: 0 }}>
            {can(user, "clients", "edit") && (
              <Button
                variant="secondary"
                onClick={() => navigate(`/clientes/${id}/editar`)}
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
            {can(user, "clients", "delete") && client.status !== "inactivo" && (
              <Button
                variant="danger"
                onClick={() => setBajaModal({ isOpen: true })}
              >
                Dar de baja
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Tarjetas de datos */}
      <div
        style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}
      >
        <DetailCard title="Datos del cliente">
          <DetailRow label="Nombre" value={client.name} />
          <DetailRow label="Tipo doc." value={client.document_type} />
          <DetailRow
            label="Documento"
            value={client.document_number}
            valueColor="#c5cdd8"
          />
          <DetailRow label="Teléfono" value={client.phone} />
          <DetailRow label="Email" value={client.email} valueColor="#3fe5e5" />
        </DetailCard>

        <DetailCard title="Servicio contratado">
          <DetailRow label="Tipo de web" value={client.web_type_name} />
          <DetailRow
            label="Plan"
            value={
              client.plan === "alquiler" ? "Alquiler mensual" : "Venta única"
            }
            valueColor={client.plan === "alquiler" ? "#4540d9" : "#8235f2"}
          />
          <DetailRow
            label="Frecuencia"
            value={client.payment_frequency === "mensual" ? "Mensual" : "Anual"}
          />
          <DetailRow
            label="Dominio"
            value={
              client.domain_price_type === "ninguno"
                ? "Sin dominio"
                : domainPrice > 0
                  ? formatPrice(domainPrice)
                  : "Incluido"
            }
          />
        </DetailCard>

        <DetailCard title="Precios y pagos">
          <DetailRow
            label="Precio base"
            value={client.base_price ? formatPrice(client.base_price) : "—"}
            valueColor="#3fe5e5"
          />
          <DetailRow
            label="Precio extra"
            value={
              client.extra_price > 0
                ? formatPrice(client.extra_price)
                : "S/ 0.00"
            }
            valueColor={client.extra_price > 0 ? "#3fe5e5" : "#8892a4"}
          />
          <DetailRow
            label="Dominio"
            value={domainPrice > 0 ? formatPrice(domainPrice) : "Sin dominio"}
          />
          <div
            style={{
              height: "1px",
              backgroundColor: "rgba(63,229,229,0.15)",
              margin: "0.5rem 0",
            }}
          />
          <DetailRow
            label="Pago total"
            value={client.total_price ? formatPrice(client.total_price) : "—"}
            valueColor="#00ff88"
          />
          {client.next_payment_date && (
            <DetailRow
              label="Próximo pago"
              value={`${formatDate(client.next_payment_date)} (${formatDateRelative(client.next_payment_date)})`}
              valueColor={
                isExpired(client.next_payment_date) ? "#ff3366" : "white"
              }
            />
          )}
        </DetailCard>

        <DetailCard title="Fechas">
          <DetailRow
            label="Registro"
            value={
              client.registration_date
                ? formatDate(client.registration_date)
                : "—"
            }
          />
          <DetailRow
            label="Entrega web"
            value={
              client.delivery_date
                ? formatDate(client.delivery_date)
                : "Pendiente"
            }
            valueColor={client.delivery_date ? "white" : "#ffb800"}
          />
          <DetailRow
            label="Estado"
            value={
              client.status === "activo"
                ? "Activo"
                : client.status === "desarrollo"
                  ? "En desarrollo"
                  : "Inactivo"
            }
            valueColor={
              client.status === "activo"
                ? "#00ff88"
                : client.status === "desarrollo"
                  ? "#ffb800"
                  : "#ff3366"
            }
          />
        </DetailCard>
      </div>

      {/* Características */}
      {client.features && client.features.length > 0 && (
        <DetailCard title="Características extra contratadas">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "0.75rem",
              paddingTop: "0.25rem",
            }}
          >
            {client.features.map((f, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "0.625rem 0.875rem",
                  borderRadius: "0.375rem",
                  backgroundColor: "rgba(63,229,229,0.05)",
                  border: "1px solid rgba(63,229,229,0.15)",
                }}
              >
                <span
                  style={{
                    fontSize: "13px",
                    color: "white",
                    fontFamily: "'Rajdhani', sans-serif",
                    fontWeight: 500,
                  }}
                >
                  {f.name}
                </span>
                <span
                  style={{
                    fontFamily: "'Share Tech Mono', monospace",
                    fontSize: "12px",
                    color: "#3fe5e5",
                  }}
                >
                  +{formatPrice(f.extra_price)}
                </span>
              </div>
            ))}
          </div>
        </DetailCard>
      )}

      {/* Notas */}
      {client.notes && (
        <DetailCard title="Notas y observaciones">
          <p
            style={{
              fontSize: "14px",
              color: "#c5cdd8",
              lineHeight: 1.7,
              margin: 0,
              paddingTop: "0.25rem",
            }}
          >
            {client.notes}
          </p>
        </DetailCard>
      )}

      {/* ── HISTORIAL DE CAMBIOS DE CUPE ──────────────────────────────────── */}
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
                  {/* Indicador */}
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

      {/* ── MODALES ─────────────────────────────────────────────────────────── */}

      {/* Cambio de CUPE */}
      <CupeChangeModal
        isOpen={cupeModal.isOpen}
        onClose={() => setCupeModal({ isOpen: false, newCupe: "" })}
        onConfirm={handleCupeConfirm}
        currentCupe={client.cupe}
        newCupe={cupeModal.newCupe}
        entityName={client.name}
        entityType="cliente"
      />

      {/* Dar de baja */}
      <Modal
        isOpen={bajaModal.isOpen}
        onClose={() => setBajaModal({ isOpen: false })}
        variant="confirm"
        size="sm"
      >
        <Modal.Header
          title="Dar de baja al cliente"
          onClose={() => setBajaModal({ isOpen: false })}
        />
        <Modal.Body>
          <p style={{ textAlign: "center" }}>
            ¿Dar de baja a{" "}
            <strong style={{ color: "white" }}>{client.name}</strong>?
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
            onClick={() => setBajaModal({ isOpen: false })}
            disabled={isDeactivating}
          >
            Cancelar
          </Button>
          <Button
            variant="danger"
            onClick={handleBaja}
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
  );
}
