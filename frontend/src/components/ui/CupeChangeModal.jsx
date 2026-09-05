// ==============================================================================
// CUPECHANGEMODAL.JSX — Modal de cambio de CUPE
//
// Responsabilidad: muestra el modal para cambiar el CUPE de un cliente
//   o colaborador. Solo accesible para Superadmin (L1).
//
// Flujo:
//   1. Muestra advertencia amarilla (acción crítica)
//   2. Muestra CUPE actual → flecha → nuevo CUPE generado automáticamente
//   3. Pide motivo (select) y observaciones (textarea)
//   4. Al confirmar → llama onConfirm(motivo, observaciones)
//   5. El backend registra el cambio en cupe_log con timestamp y usuario
//
// Props:
//   isOpen       (boolean)  → si el modal está visible
//   onClose      (function) → cierra el modal
//   onConfirm    (function) → (motivo, observaciones) → Promise
//   currentCupe  (string)   → CUPE actual del registro
//   newCupe      (string)   → nuevo CUPE generado por el sistema
//   entityName   (string)   → nombre del cliente o colaborador
//   entityType   (string)   → 'cliente' | 'colaborador'
// ==============================================================================

import { useState } from "react";
import Button from "../ui/Button";
import Modal from "../ui/Modal";

const MOTIVOS = [
  { value: "", label: "— Seleccioná el motivo —" },
  { value: "error_generacion", label: "Error en la generación original" },
  { value: "reingreso", label: "Reingreso del registro" },
  { value: "correccion_administrativa", label: "Corrección administrativa" },
  { value: "solicitud_cliente", label: "Solicitud del cliente" },
  { value: "migracion_sistema", label: "Migración del sistema" },
  { value: "otro", label: "Otro" },
];

export default function CupeChangeModal({
  isOpen,
  onClose,
  onConfirm,
  currentCupe,
  newCupe,
  entityName,
  entityType = "registro",
}) {
  const [motivo, setMotivo] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [errors, setErrors] = useState({});
  const [isSaving, setIsSaving] = useState(false);

  // Limpia el estado al cerrar
  const handleClose = () => {
    setMotivo("");
    setObservaciones("");
    setErrors({});
    onClose();
  };

  const validate = () => {
    const newErrors = {};
    if (!motivo) newErrors.motivo = "Seleccioná el motivo del cambio.";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleConfirm = async () => {
    if (!validate()) return;
    setIsSaving(true);
    try {
      await onConfirm(motivo, observaciones);
      handleClose();
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} variant="confirm" size="md">
      <Modal.Header title="Cambio de CUPE" onClose={handleClose} />

      <Modal.Body>
        <div
          style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}
        >
          {/* ── ADVERTENCIA AMARILLA ────────────────────────────────────── */}
          <div
            style={{
              display: "flex",
              gap: "0.75rem",
              alignItems: "flex-start",
              padding: "1rem",
              borderRadius: "0.5rem",
              backgroundColor: "rgba(255,184,0,0.06)",
              border: "1px solid rgba(255,184,0,0.25)",
            }}
          >
            <span style={{ fontSize: "18px", flexShrink: 0 }}>⚠</span>
            <p
              style={{
                fontFamily: "'Rajdhani', sans-serif",
                fontSize: "13px",
                color: "#ffb800",
                lineHeight: 1.6,
                margin: 0,
              }}
            >
              El cambio de CUPE es una <strong>acción crítica</strong>. Afecta
              el identificador único del {entityType} en todo el sistema y queda
              registrado en el historial de auditoría con el usuario que lo
              autorizó.
            </p>
          </div>

          {/* ── DISPLAY CUPE ACTUAL → NUEVO ─────────────────────────────── */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "1.5rem",
              padding: "1.25rem",
              borderRadius: "0.5rem",
              backgroundColor: "rgba(63,229,229,0.03)",
              border: "1px solid rgba(63,229,229,0.12)",
            }}
          >
            {/* CUPE actual — tachado */}
            <div style={{ textAlign: "center" }}>
              <p
                style={{
                  fontFamily: "'Share Tech Mono', monospace",
                  fontSize: "9px",
                  color: "#8892a4",
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  margin: "0 0 0.375rem 0",
                }}
              >
                CUPE ACTUAL
              </p>
              <p
                style={{
                  fontFamily: "'Orbitron', monospace",
                  fontSize: "18px",
                  fontWeight: 700,
                  color: "#8892a4",
                  textDecoration: "line-through",
                  textDecorationColor: "#ff3366",
                  margin: 0,
                }}
              >
                {currentCupe}
              </p>
            </div>

            {/* Flecha */}
            <span style={{ fontSize: "22px", color: "#3fe5e5" }}>→</span>

            {/* Nuevo CUPE */}
            <div style={{ textAlign: "center" }}>
              <p
                style={{
                  fontFamily: "'Share Tech Mono', monospace",
                  fontSize: "9px",
                  color: "#8892a4",
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  margin: "0 0 0.375rem 0",
                }}
              >
                NUEVO CUPE
              </p>
              <p
                style={{
                  fontFamily: "'Orbitron', monospace",
                  fontSize: "18px",
                  fontWeight: 700,
                  color: "#00ff88",
                  margin: 0,
                }}
              >
                {newCupe}
              </p>
            </div>
          </div>

          {/* Nombre del registro */}
          <p
            style={{
              fontFamily: "'Rajdhani', sans-serif",
              fontSize: "13px",
              color: "#8892a4",
              textAlign: "center",
              margin: 0,
            }}
          >
            {entityType === "cliente" ? "Cliente" : "Colaborador"}:{" "}
            <strong style={{ color: "white" }}>{entityName}</strong>
          </p>

          {/* ── MOTIVO ──────────────────────────────────────────────────── */}
          <div
            style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}
          >
            <label
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "10px",
                fontWeight: 700,
                color: errors.motivo ? "#ff3366" : "#3fe5e5",
                letterSpacing: "0.12em",
                textTransform: "uppercase",
              }}
            >
              Motivo del cambio *
            </label>
            <select
              value={motivo}
              onChange={(e) => {
                setMotivo(e.target.value);
                if (errors.motivo) setErrors({});
              }}
              style={{
                width: "100%",
                padding: "0.875rem 1rem",
                borderRadius: "0.375rem",
                fontSize: "14px",
                color: motivo ? "white" : "#8892a4",
                backgroundColor: "#1a1d30",
                border: `1px solid ${errors.motivo ? "rgba(255,51,102,0.6)" : "rgba(63,229,229,0.2)"}`,
                outline: "none",
                fontFamily: "'Rajdhani', sans-serif",
                cursor: "pointer",
              }}
            >
              {MOTIVOS.map((m) => (
                <option
                  key={m.value}
                  value={m.value}
                  style={{ backgroundColor: "#1a1d30" }}
                >
                  {m.label}
                </option>
              ))}
            </select>
            {errors.motivo && (
              <p style={{ color: "#ff3366", fontSize: "12px", margin: 0 }}>
                ⚠ {errors.motivo}
              </p>
            )}
          </div>

          {/* ── OBSERVACIONES ───────────────────────────────────────────── */}
          <div
            style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}
          >
            <label
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "10px",
                fontWeight: 700,
                color: "#3fe5e5",
                letterSpacing: "0.12em",
                textTransform: "uppercase",
              }}
            >
              Observaciones
            </label>
            <textarea
              value={observaciones}
              onChange={(e) => setObservaciones(e.target.value)}
              placeholder="Describe el motivo del cambio de CUPE..."
              rows={3}
              style={{
                width: "100%",
                padding: "0.875rem 1rem",
                borderRadius: "0.375rem",
                fontSize: "14px",
                color: "white",
                backgroundColor: "#1a1d30",
                border: "1px solid rgba(63,229,229,0.2)",
                outline: "none",
                fontFamily: "'Rajdhani', sans-serif",
                resize: "vertical",
                minHeight: "80px",
                boxSizing: "border-box",
              }}
            />
          </div>

          {/* ── NOTA DE AUDITORÍA ────────────────────────────────────────── */}
          <div
            style={{
              padding: "0.75rem 1rem",
              borderRadius: "0.375rem",
              backgroundColor: "rgba(63,229,229,0.04)",
              border: "1px solid rgba(63,229,229,0.1)",
            }}
          >
            <p
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "10px",
                color: "#8892a4",
                margin: 0,
                lineHeight: 1.6,
                letterSpacing: "0.03em",
              }}
            >
              // Este cambio quedará registrado automáticamente en{" "}
              <span style={{ color: "#3fe5e5" }}>cupe_log</span> con timestamp,
              motivo y el usuario que lo autorizó.
            </p>
          </div>
        </div>
      </Modal.Body>

      <Modal.Footer>
        <Button variant="secondary" onClick={handleClose} disabled={isSaving}>
          Cancelar
        </Button>
        <Button variant="primary" onClick={handleConfirm} isLoading={isSaving}>
          Autorizar cambio
        </Button>
      </Modal.Footer>
    </Modal>
  );
}
