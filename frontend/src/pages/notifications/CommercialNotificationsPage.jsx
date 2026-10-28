import { useCallback, useEffect, useState } from "react";
import {
  getCommercialNoticeConfig,
  getCommercialNoticeDetail,
  getCommercialNoticeLogs,
  getUpcomingCommercialNotices,
  resendCommercialNotice,
  updateCommercialNoticeConfig,
} from "../../api/notifications";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";
import { useToast } from "../../components/ui/Toast";
import Button from "../../components/ui/Button";

const card = { padding: "1.1rem", borderRadius: "0.6rem", background: "#111427", border: "1px solid rgba(63,229,229,0.14)" };
const input = { padding: "0.65rem 0.75rem", borderRadius: "0.4rem", border: "1px solid rgba(63,229,229,0.22)", background: "#0b0d1a", color: "white", font: "inherit" };
const th = { color: "#8892a4", textAlign: "left", fontSize: "0.8rem", padding: "0.65rem" };
const td = { color: "#cbd5e1", padding: "0.65rem", borderTop: "1px solid rgba(255,255,255,0.06)", verticalAlign: "top" };
const CHANNELS = { whatsapp: "WhatsApp", email: "Correo", internal: "Interna" };
const STATUSES = { preparada: "Preparada; sin envío externo", disponible: "Disponible en bandeja interna", fallida: "Fallida", null: "Sin aviso registrado" };

function dateText(value) {
  return value ? new Date(value).toLocaleString("es-PE", { dateStyle: "short", timeStyle: "short" }) : "—";
}

function Filters({ filters, setFilters, history = false }) {
  return <div style={{ display: "flex", flexWrap: "wrap", gap: "0.6rem", margin: "0.8rem 0" }}>
    <input aria-label="Buscar cliente o servicio" placeholder="Cliente o servicio" value={filters.search} onChange={(e) => setFilters((old) => ({ ...old, search: e.target.value }))} style={{ ...input, minWidth: 200 }} />
    <select aria-label="Canal" value={filters.channel} onChange={(e) => setFilters((old) => ({ ...old, channel: e.target.value }))} style={input}>
      <option value="">Todos los canales</option>{Object.entries(CHANNELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
    </select>
    <select aria-label="Estado" value={filters.status} onChange={(e) => setFilters((old) => ({ ...old, status: e.target.value }))} style={input}>
      <option value="">Todos los estados</option>{Object.entries(STATUSES).filter(([key]) => key !== "null").map(([key, label]) => <option key={key} value={key}>{label}</option>)}
    </select>
    {history && <>
      <input aria-label="Desde" type="date" value={filters.date_from} onChange={(e) => setFilters((old) => ({ ...old, date_from: e.target.value }))} style={input} />
      <input aria-label="Hasta" type="date" value={filters.date_to} onChange={(e) => setFilters((old) => ({ ...old, date_to: e.target.value }))} style={input} />
    </>}
  </div>;
}

export default function CommercialNotificationsPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const canConfigure = can(user, "notifications", "configure");
  const [tab, setTab] = useState("upcoming");
  const [filters, setFilters] = useState({ search: "", channel: "", status: "", date_from: "", date_to: "" });
  const [items, setItems] = useState([]);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [configs, setConfigs] = useState([]);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadRows = useCallback(async () => {
    if (tab === "config") return;
    setLoading(true);
    try {
      const params = { search: filters.search || undefined, channel: filters.channel || undefined, status: filters.status || undefined, limit: 50, offset };
      if (tab === "history") {
        const result = await getCommercialNoticeLogs({ ...params, date_from: filters.date_from || undefined, date_to: filters.date_to || undefined });
        setItems(result.items); setCount(result.count);
      } else {
        const result = await getUpcomingCommercialNotices(params);
        setItems(result.items); setCount(result.count);
      }
    } catch (error) {
      showToast("error", "NO SE CARGARON LOS AVISOS", error.userMessage || "Intenta nuevamente.");
    } finally { setLoading(false); }
  }, [filters, offset, showToast, tab]);

  const loadConfig = useCallback(async () => {
    if (!canConfigure || tab !== "config") return;
    setLoading(true);
    try { setConfigs(await getCommercialNoticeConfig()); }
    catch (error) { showToast("error", "NO SE CARGÓ LA CONFIGURACIÓN", error.userMessage || "Intenta nuevamente."); }
    finally { setLoading(false); }
  }, [canConfigure, showToast, tab]);

  useEffect(() => { setOffset(0); }, [filters, tab]);
  useEffect(() => { loadRows(); }, [loadRows]);
  useEffect(() => { loadConfig(); }, [loadConfig]);

  async function openDetail(id) {
    if (!id) return;
    try { setDetail(await getCommercialNoticeDetail(id)); }
    catch (error) { showToast("error", "NO SE CARGÓ EL AVISO", error.userMessage || "Intenta nuevamente."); }
  }

  async function resend(item) {
    if (!canConfigure || item.channel !== "internal" || item.status !== "fallida") return;
    if (!window.confirm("¿Crear un nuevo intento interno para el responsable comercial vigente? No enviará correo ni WhatsApp.")) return;
    try {
      await resendCommercialNotice(item.id);
      showToast("success", "AVISO INTERNO DISPONIBLE", "El nuevo intento quedó en la bandeja interna; no se realizó un envío externo.");
      await loadRows();
    } catch (error) { showToast("error", "NO SE REINTENTÓ EL AVISO", error.userMessage || "Intenta nuevamente."); }
  }

  async function saveConfig(config) {
    const days = config.daysText.split(",").map((value) => Number(value.trim()));
    if (!days.length || days.some((value) => !Number.isSafeInteger(value) || value < 1 || value > 32767) || new Set(days).size !== days.length) {
      showToast("error", "CONFIGURACIÓN INVÁLIDA", "Ingresa días enteros entre 1 y 32767, sin repetición."); return;
    }
    try {
      const result = await updateCommercialNoticeConfig(config.channel, { anticipation_days: days, is_active: config.is_active });
      setConfigs((current) => current.map((row) => row.channel === result.channel ? result : row));
      showToast("success", "CONFIGURACIÓN GUARDADA", "Los cambios quedaron registrados en el historial.");
    } catch (error) { showToast("error", "NO SE GUARDÓ", error.userMessage || "Intenta nuevamente."); }
  }

  const tabs = [["upcoming", "Próximos vencimientos"], ["history", "Historial"], ...(canConfigure ? [["config", "Configuración comercial"]] : [])];
  return <main style={{ display: "grid", gap: "1rem", maxWidth: 1200 }}>
    <header>
      <h1 style={{ color: "white", margin: 0, fontFamily: "'Rajdhani', sans-serif" }}>Alertas comerciales</h1>
      <p style={{ color: "#8892a4", margin: "0.4rem 0 0" }}>Avisos basados en vencimientos documentados. “Preparada” no significa que se haya enviado ni entregado por un canal externo.</p>
    </header>
    <nav aria-label="Secciones de alertas" style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
      {tabs.map(([key, label]) => <Button key={key} type="button" variant={tab === key ? "primary" : "secondary"} onClick={() => setTab(key)}>{label}</Button>)}
    </nav>

    {tab !== "config" ? <section style={card}>
      <h2 style={{ color: "white", margin: 0, fontSize: "1.1rem" }}>{tab === "history" ? "Historial registrado" : "Vencimientos próximos (30 días)"}</h2>
      <Filters filters={filters} setFilters={setFilters} history={tab === "history"} />
      {loading ? <p style={{ color: "#cbd5e1" }}>Cargando…</p> : <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse", minWidth: 760 }}>
        <thead><tr>{["Vencimiento", "Días", "Cliente / servicio", "Canal", "Estado registrado", "Fecha de registro", "Acciones"].map((label) => <th style={th} key={label}>{label}</th>)}</tr></thead>
        <tbody>{items.map((item, index) => <tr key={item.id || `${item.due_id}-${item.channel}-${index}`}>
          <td style={td}>{item.due_date}</td><td style={td}>{item.days_remaining ?? "—"}</td>
          <td style={td}>{item.client_name}<br /><span style={{ color: "#8892a4" }}>{item.service_name}</span></td>
          <td style={td}>{CHANNELS[item.channel] || "—"}</td><td style={td}>{STATUSES[item.status ?? "null"] || item.status}</td>
          <td style={td}>{dateText(item.created_at)}</td><td style={td}>
            {item.id && <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
              <Button type="button" variant="secondary" onClick={() => openDetail(item.id)}>Detalle</Button>
              {canConfigure && item.channel === "internal" && item.status === "fallida" && <Button type="button" onClick={() => resend(item)}>Reintentar interno</Button>}
            </div>}
          </td>
        </tr>)}</tbody>
      </table>{!items.length && <p style={{ color: "#8892a4" }}>No hay registros para los filtros seleccionados.</p>}</div>}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", color: "#8892a4", marginTop: "0.8rem" }}>
        <span>{count} registros</span><div style={{ display: "flex", gap: "0.5rem" }}>
          <Button type="button" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Anterior</Button>
          <Button type="button" variant="secondary" disabled={offset + 50 >= count} onClick={() => setOffset(offset + 50)}>Siguiente</Button>
        </div>
      </div>
    </section> : <section style={{ display: "grid", gap: "0.8rem" }}>
      <p style={{ color: "#8892a4", margin: 0 }}>Esta configuración aplica solo a avisos comerciales documentados; no cambia los recordatorios de tareas.</p>
      {loading ? <p style={{ color: "#cbd5e1" }}>Cargando…</p> : configs.map((item) => <ConfigCard key={item.channel} config={item} onSave={saveConfig} />)}
    </section>}

    {detail && <div role="presentation" onClick={() => setDetail(null)} style={{ position: "fixed", inset: 0, zIndex: 30, background: "rgba(0,0,0,.72)", display: "grid", placeItems: "center", padding: "1rem" }}>
      <section role="dialog" aria-modal="true" aria-labelledby="notice-detail-title" onClick={(event) => event.stopPropagation()} style={{ ...card, width: "min(650px, 100%)", maxHeight: "85vh", overflow: "auto" }}>
        <h2 id="notice-detail-title" style={{ color: "white", marginTop: 0 }}>Detalle del aviso</h2>
        <dl style={{ color: "#cbd5e1", display: "grid", gridTemplateColumns: "minmax(120px, 1fr) 2fr", gap: "0.6rem" }}>
          {[ ["Cliente", detail.client_name], ["Servicio", detail.service_name], ["Canal", CHANNELS[detail.channel]], ["Estado", STATUSES[detail.status] || detail.status], ["Fecha de vencimiento", detail.due_date], ["Destinatario", detail.recipient], ["Creado", dateText(detail.created_at)], ["Disponible", dateText(detail.available_at)], ["Referencia de obligación", detail.obligation_reference || "No disponible"], ["Evidencia", detail.evidence_reference || "No disponible"], ["Resultado", detail.error_message || "Sin fallo registrado"] ].map(([label, value]) => <div key={label} style={{ display: "contents" }}><dt style={{ color: "#8892a4" }}>{label}</dt><dd style={{ margin: 0, overflowWrap: "anywhere" }}>{value ?? "—"}</dd></div>)}
        </dl>
        <p style={{ color: "#cbd5e1", whiteSpace: "pre-wrap" }}>{detail.message}</p>
        <Button type="button" onClick={() => setDetail(null)}>Cerrar</Button>
      </section>
    </div>}
  </main>;
}

function ConfigCard({ config, onSave }) {
  const [daysText, setDaysText] = useState(config.anticipation_days.join(", "));
  const [active, setActive] = useState(config.is_active);
  return <section style={card}>
    <form onSubmit={(event) => { event.preventDefault(); onSave({ ...config, daysText, is_active: active }); }} style={{ display: "grid", gridTemplateColumns: "minmax(120px, .7fr) minmax(220px, 2fr) auto auto", gap: "0.8rem", alignItems: "end" }}>
      <strong style={{ color: "white" }}>{CHANNELS[config.channel]}</strong>
      <label style={{ display: "grid", gap: "0.35rem", color: "#cbd5e1" }}>Días de anticipación (separados por coma)
        <input value={daysText} onChange={(event) => setDaysText(event.target.value)} required style={input} aria-label={`Días de anticipación ${CHANNELS[config.channel]}`} />
      </label>
      <label style={{ color: "#cbd5e1", display: "flex", gap: "0.4rem", alignItems: "center" }}><input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} /> Activo</label>
      <Button type="submit">Guardar</Button>
    </form>
    <p style={{ color: "#8892a4", marginBottom: 0 }}>Último cambio: {config.updated_by_name || "Configuración inicial"} · {dateText(config.updated_at)}</p>
    {config.history?.length > 0 && <details style={{ marginTop: "0.7rem", color: "#cbd5e1" }}>
      <summary style={{ cursor: "pointer" }}>Historial de configuración ({config.history.length})</summary>
      <ul style={{ display: "grid", gap: "0.4rem" }}>{config.history.map((event, index) => <li key={`${event.occurred_at}-${index}`}>
        {event.previous_days.join(", ")} → {event.new_days.join(", ")} días; {event.previous_active ? "activo" : "inactivo"} → {event.new_active ? "activo" : "inactivo"} · {event.actor_name} · {dateText(event.occurred_at)}
      </li>)}</ul>
    </details>}
  </section>;
}
