import { useEffect, useState } from "react";
import {
  decideProjectCancellation, evaluateProjectCancellation, getProjectCancellations,
  openProjectCancellation,
} from "../../api/projects";

const fieldStyle = { padding: "9px 11px", background: "#0b0d1a", color: "white", border: "1px solid #34394a", borderRadius: 6, width: "100%" };
const labels = {
  solicitada: "Solicitud registrada",
  evaluacion_tecnica: "Evaluación técnica L3",
  autorizada: "Autorización ordinaria L2",
  denegada: "Denegación L2",
  efectiva: "Cancelación efectiva",
};

export default function ProjectCancellationPanel({ project, canRequest, canEvaluate, canResolve }) {
  const [cancellations, setCancellations] = useState([]);
  const [scope, setScope] = useState(project.scope || "");
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState("");
  const [technical, setTechnical] = useState({ affected_tasks_assessment: "", obligations_assessment: "", evidence: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setCancellations(await getProjectCancellations(project.id));
      setError("");
    } catch (requestError) {
      setError(requestError.userMessage || requestError.response?.data?.detail || "No se pudo cargar el historial de cancelación.");
    }
  }

  useEffect(() => { refresh(); }, [project.id]);

  const current = [...cancellations].reverse().find((item) => {
    const last = item.events.at(-1)?.event_type;
    return !["denegada", "efectiva"].includes(last);
  });
  const latestEvent = current?.events.at(-1);
  const isEffective = cancellations.some((item) => item.events.some((event) => event.event_type === "efectiva"));
  const canOpenCancellation = canRequest && !current && !isEffective && project.status !== "Entregado";
  const canReview = canEvaluate && current && latestEvent?.event_type === "solicitada";
  const canDecide = canResolve && current && latestEvent?.event_type === "evaluacion_tecnica";
  const canMakeEffective = canResolve && current && latestEvent?.event_type === "autorizada";

  async function run(action) {
    setBusy(true);
    setError("");
    try {
      await action();
      await refresh();
    } catch (requestError) {
      setError(requestError.userMessage || requestError.response?.data?.detail || "No se pudo registrar la actuación.");
    } finally {
      setBusy(false);
    }
  }

  return <article style={{ border: "1px solid #34394a", borderRadius: 8, padding: 16, margin: "12px 0" }}>
    <h3>Cancelación integral · {project.name}</h3>
    <p style={{ color: "#aab2c5" }}>La cancelación no cambia el estado ni cancela tareas en bloque. Al hacerse efectiva, restringe el trabajo ordinario del alcance registrado.</p>
    {isEffective && <p role="status">Cancelación efectiva: se conserva el estado ordinario «{project.status}» y el historial del proyecto.</p>}
    {error && <p role="alert" style={{ color: "#ff718b" }}>{error}</p>}
    {canOpenCancellation && <div style={{ display: "grid", gap: 8, maxWidth: 760 }}>
      <label style={{ display: "grid", gap: 4 }}>Alcance completo vigente<textarea required value={scope} onChange={(event) => setScope(event.target.value)} style={fieldStyle} /></label>
      <label style={{ display: "grid", gap: 4 }}>Motivo<textarea required value={reason} onChange={(event) => setReason(event.target.value)} style={fieldStyle} /></label>
      <label style={{ display: "grid", gap: 4 }}>Referencia de evidencia<input required value={evidence} onChange={(event) => setEvidence(event.target.value)} style={fieldStyle} /></label>
      <button type="button" disabled={busy || !scope.trim() || !reason.trim() || !evidence.trim()} onClick={() => run(async () => {
        await openProjectCancellation(project.id, { cancelled_scope: scope, reason, evidence });
        setReason(""); setEvidence("");
      })} style={fieldStyle}>Registrar solicitud integral</button>
    </div>}
    {current && <section style={{ display: "grid", gap: 8, marginTop: 14, maxWidth: 760 }}>
      <p>Alcance: {current.cancelled_scope}</p>
      {canReview && <>
        <label style={{ display: "grid", gap: 4 }}>Consecuencias técnicas y tratamiento individual de tareas<textarea value={technical.affected_tasks_assessment} onChange={(event) => setTechnical({ ...technical, affected_tasks_assessment: event.target.value })} style={fieldStyle} /></label>
        <label style={{ display: "grid", gap: 4 }}>Obligaciones y actividades residuales<textarea value={technical.obligations_assessment} onChange={(event) => setTechnical({ ...technical, obligations_assessment: event.target.value })} style={fieldStyle} /></label>
        <label style={{ display: "grid", gap: 4 }}>Evidencia técnica<input value={technical.evidence} onChange={(event) => setTechnical({ ...technical, evidence: event.target.value })} style={fieldStyle} /></label>
        <button type="button" disabled={busy || Object.values(technical).some((value) => !value.trim())} onClick={() => run(async () => {
          await evaluateProjectCancellation(project.id, current.id, technical);
        })} style={fieldStyle}>Registrar evaluación técnica L3</button>
      </>}
      {canDecide && <>
        <p role="status">La autorización y efectividad L2 están bloqueadas mientras no haya criterios ratificados para acreditar que esta cancelación pertenece a su competencia ordinaria.</p>
        <label style={{ display: "grid", gap: 4 }}>Motivo de la decisión<textarea value={reason} onChange={(event) => setReason(event.target.value)} style={fieldStyle} /></label>
        <label style={{ display: "grid", gap: 4 }}>Evidencia comercial<input value={evidence} onChange={(event) => setEvidence(event.target.value)} style={fieldStyle} /></label>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="button" disabled={busy || !reason.trim() || !evidence.trim()} onClick={() => run(async () => {
            await decideProjectCancellation(project.id, current.id, { authorized: false, reason, evidence });
            setReason(""); setEvidence("");
          })} style={fieldStyle}>Denegar</button>
        </div>
      </>}
      {canMakeEffective && <>
        <p role="status">No se puede registrar la efectividad: la competencia ordinaria L2 no está acreditada mediante criterios funcionales ratificados.</p>
      </>}
    </section>}
    {cancellations.map((item) => <section key={item.id} style={{ borderTop: "1px solid #34394a", marginTop: 12, paddingTop: 8 }}>
      <strong>Expediente #{item.id} · {item.cancelled_scope}</strong>
      <p>Registrado por {item.opened_by_name} · {new Date(item.opened_at).toLocaleString()} · {item.reason}</p>
      {item.events.map((event) => <p key={event.event_type} style={{ color: "#aab2c5" }}>
        {labels[event.event_type] || event.event_type} · {event.actor_name} · {new Date(event.occurred_at).toLocaleString()}
        {event.effective_at ? ` · Efectiva ${new Date(event.effective_at).toLocaleString()}` : ""} · {event.reason} · Evidencia: {event.evidence}
      </p>)}
    </section>)}
  </article>;
}
