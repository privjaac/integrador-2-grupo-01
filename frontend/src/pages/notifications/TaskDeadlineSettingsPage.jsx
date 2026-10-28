import { useCallback, useEffect, useState } from "react";
import { getTaskDeadlineSettings, updateTaskDeadlineSettings } from "../../api/notifications";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";
import { useToast } from "../../components/ui/Toast";
import Button from "../../components/ui/Button";

const fieldStyle = {
  width: "100%", maxWidth: 320, boxSizing: "border-box", padding: "0.7rem 0.85rem",
  borderRadius: "0.45rem", border: "1px solid rgba(63,229,229,0.22)",
  background: "#0b0d1a", color: "white", font: "inherit",
};

function dateTimeText(value) {
  if (!value) return "Sin cambios registrados";
  return new Date(value).toLocaleString("es-PE", { dateStyle: "short", timeStyle: "short" });
}

export default function TaskDeadlineSettingsPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const canConfigure = can(user, "notifications", "configure");
  const [settings, setSettings] = useState(null);
  const [daysBefore, setDaysBefore] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const loadSettings = useCallback(async () => {
    if (!canConfigure) return;
    setLoading(true);
    try {
      const result = await getTaskDeadlineSettings();
      setSettings(result);
      setDaysBefore(result.days_before);
    } catch (error) {
      showToast("error", "ERROR AL CARGAR LA CONFIGURACIÓN", error.userMessage || "No se pudo consultar el plazo de aviso.");
    } finally {
      setLoading(false);
    }
  }, [canConfigure, showToast]);

  useEffect(() => { loadSettings(); }, [loadSettings]);

  async function submit(event) {
    event.preventDefault();
    const value = Number(daysBefore);
    if (!Number.isSafeInteger(value) || value < 1 || value > 2147483647 || saving) return;
    setSaving(true);
    try {
      const result = await updateTaskDeadlineSettings({ days_before: value });
      setSettings(result);
      setDaysBefore(result.days_before);
      showToast("success", "CONFIGURACIÓN GUARDADA", "El recordatorio interno usará el plazo actualizado.");
    } catch (error) {
      showToast("error", "ERROR AL GUARDAR", error.userMessage || "No se pudo guardar el plazo de aviso.");
    } finally {
      setSaving(false);
    }
  }

  if (!canConfigure) return <p style={{ color: "#cbd5e1" }}>No tienes permiso para configurar estos avisos.</p>;

  const valid = Number.isSafeInteger(Number(daysBefore)) && Number(daysBefore) >= 1 && Number(daysBefore) <= 2147483647;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", maxWidth: 850 }}>
      <div>
        <h1 style={{ color: "white", margin: 0, fontFamily: "'Rajdhani', sans-serif" }}>Avisos de vencimiento de tareas</h1>
        <p style={{ color: "#8892a4", margin: "0.4rem 0 0" }}>Configura con cuántos días de anticipación se genera el recordatorio interno.</p>
      </div>

      <section style={{ padding: "1.25rem", borderRadius: "0.6rem", background: "#111427", border: "1px solid rgba(63,229,229,0.14)" }}>
        {loading ? <p style={{ color: "#aab2c5" }}>Cargando configuración…</p> : (
          <form onSubmit={submit} style={{ display: "grid", gap: "1rem" }}>
            <label style={{ color: "#cbd5e1", display: "grid", gap: "0.45rem", maxWidth: 360 }}>
              Días de anticipación
              <input
                type="number" min="1" max="2147483647" step="1" required
                value={daysBefore} onChange={(event) => setDaysBefore(event.target.value)}
                style={fieldStyle} aria-describedby="deadline-reminder-help"
              />
            </label>
            <p id="deadline-reminder-help" style={{ color: "#8892a4", margin: 0, fontSize: "0.9rem" }}>
              Los avisos de tareas vencidas conservan su tratamiento actual. Esta configuración no envía mensajes por correo ni por otros canales externos.
            </p>
            <div><Button type="submit" disabled={!valid || saving}>{saving ? "Guardando…" : "Guardar plazo"}</Button></div>
          </form>
        )}
      </section>

      {!loading && settings && <section style={{ padding: "1.25rem", borderRadius: "0.6rem", background: "#111427", border: "1px solid rgba(63,229,229,0.14)" }}>
        <h2 style={{ color: "white", margin: "0 0 0.8rem", fontSize: "1.1rem" }}>Historial de cambios</h2>
        {settings.history.length === 0 ? <p style={{ color: "#8892a4", margin: 0 }}>No hay cambios registrados.</p> : (
          <ul style={{ color: "#cbd5e1", margin: 0, paddingLeft: "1.25rem", display: "grid", gap: "0.55rem" }}>
            {settings.history.map((item, index) => <li key={`${item.occurred_at}-${index}`}>
              {item.previous_days_before} → {item.new_days_before} días · {item.actor_name} · {dateTimeText(item.occurred_at)}
            </li>)}
          </ul>
        )}
      </section>}
    </div>
  );
}
