import { useEffect, useState } from "react";
import {
  createProjectSubstitution, decideProjectCancellationExceptionally,
  decideProjectResumptionExceptionally, endProjectSubstitution,
  getL1ExceptionalCancellations, getL1ExceptionalResumptions,
  getL1SubstitutionContext, getProjectSubstitutions,
} from "../../api/projects";

const fieldStyle = { padding: "9px 11px", background: "#0b0d1a", color: "white", border: "1px solid #34394a", borderRadius: 6, width: "100%" };
const panelStyle = { border: "1px solid #34394a", borderRadius: 8, padding: 16, margin: "12px 0", display: "grid", gap: 10 };
const displayDate = (value) => value ? new Date(value).toLocaleString() : "—";

export default function ProjectExceptionalWorklist() {
  const [cancellations, setCancellations] = useState([]);
  const [resumptions, setResumptions] = useState([]);
  const [substitutionContext, setSubstitutionContext] = useState({ coordinations: [], substitutes: [] });
  const [substitutions, setSubstitutions] = useState({});
  const [forms, setForms] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const [cancellationRows, resumptionRows, context] = await Promise.all([
        getL1ExceptionalCancellations(), getL1ExceptionalResumptions(), getL1SubstitutionContext(),
      ]);
      setCancellations(cancellationRows);
      setResumptions(resumptionRows);
      setSubstitutionContext(context);
      const projectIds = [...new Set(context.coordinations.map((item) => item.project_id))];
      const histories = await Promise.all(projectIds.map(async (projectId) => [
        projectId, await getProjectSubstitutions(projectId),
      ]));
      setSubstitutions(Object.fromEntries(histories));
      setError("");
    } catch (requestError) {
      setError(requestError.userMessage || requestError.response?.data?.detail || "No se pudieron cargar las actuaciones L1.");
    }
  }

  useEffect(() => { refresh(); }, []);

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

  function update(key, field, value) {
    setForms((items) => ({ ...items, [key]: { ...(items[key] || {}), [field]: value } }));
  }

  return <main style={{ padding: 24, color: "white" }}>
    <h1>Actuaciones excepcionales</h1>
    <p style={{ color: "#aab2c5" }}>Bandeja L1 para decisiones excepcionales acreditadas y sustituciones temporales de coordinación.</p>
    {error && <p role="alert" style={{ color: "#ff718b" }}>{error}</p>}

    <section>
      <h2>Cancelaciones excepcionales pendientes</h2>
      {cancellations.length === 0 && <p>No hay decisiones L1 pendientes.</p>}
      {cancellations.map((item) => {
        const key = `cancel-${item.id}`;
        const input = forms[key] || {};
        return <article key={item.id} style={panelStyle}>
          <h3>{item.project_name} · expediente #{item.id}</h3>
          <p>Estado del proyecto: {item.project_status}. Alcance: {item.cancelled_scope}</p>
          <p>{item.reason} · evidencia inicial: {item.evidence}</p>
          {item.events.map((event, index) => <p key={`${event.event_type}-${index}`} style={{ color: "#aab2c5" }}>
            {event.event_type} · {event.actor_name} · {displayDate(event.occurred_at)} · {event.reason} · {event.evidence}
            {event.data && <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(event.data, null, 2)}</pre>}
          </p>)}
          <label><input type="checkbox" checked={Boolean(input.authorized)} onChange={(event) => update(key, "authorized", event.target.checked)} /> Autorizar cancelación excepcional</label>
          {input.authorized && <label>Fecha prevista de efectividad<input type="datetime-local" value={input.planned_effective_at || ""} onChange={(event) => update(key, "planned_effective_at", event.target.value)} style={fieldStyle} /></label>}
          <label>Motivo de la decisión<textarea value={input.reason || ""} onChange={(event) => update(key, "reason", event.target.value)} style={fieldStyle} /></label>
          <label>Evidencia de la decisión<input value={input.evidence || ""} onChange={(event) => update(key, "evidence", event.target.value)} style={fieldStyle} /></label>
          <button type="button" style={fieldStyle} disabled={busy || !input.reason?.trim() || !input.evidence?.trim() || (input.authorized && !input.planned_effective_at)} onClick={() => run(async () => {
            await decideProjectCancellationExceptionally(item.project_id, item.id, {
              authorized: Boolean(input.authorized), reason: input.reason, evidence: input.evidence,
              planned_effective_at: input.authorized ? new Date(input.planned_effective_at).toISOString() : null,
            });
          })}>Registrar decisión L1</button>
        </article>;
      })}
    </section>

    <section>
      <h2>Reanudaciones que requieren decisión L1</h2>
      {resumptions.length === 0 && <p>No hay reanudaciones pendientes de decisión L1.</p>}
      {resumptions.map((item) => {
        const key = `resume-${item.id}`;
        const input = forms[key] || {};
        return <article key={item.id} style={panelStyle}>
          <h3>{item.project_name} · reanudación #{item.id}</h3>
          <p>Estado del proyecto conservado: {item.project_status} · cancelación #{item.cancellation_id}</p>
          <h4>Antecedentes de cancelación: {item.cancellation.reason}</h4>
          <p>Alcance: {item.cancellation.cancelled_scope} · evidencia inicial: {item.cancellation.evidence}</p>
          {item.cancellation.events.map((event, index) => <p key={`cancellation-${event.event_type}-${index}`} style={{ color: "#aab2c5" }}>
            {event.event_type} · {event.actor_name} · {displayDate(event.occurred_at)} · {event.reason} · {event.evidence}
            {event.data && <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(event.data, null, 2)}</pre>}
          </p>)}
          {item.events.map((event, index) => <p key={`${event.event_type}-${index}`} style={{ color: "#aab2c5" }}>
            {event.event_type} · {event.actor_name} · {displayDate(event.occurred_at)} · {event.reason} · {event.evidence}
            {event.data && <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(event.data, null, 2)}</pre>}
          </p>)}
          <label><input type="checkbox" checked={Boolean(input.authorized)} onChange={(event) => update(key, "authorized", event.target.checked)} /> Autorizar reanudación excepcional</label>
          <label>Motivo<textarea value={input.reason || ""} onChange={(event) => update(key, "reason", event.target.value)} style={fieldStyle} /></label>
          <label>Condiciones<textarea value={input.conditions || ""} onChange={(event) => update(key, "conditions", event.target.value)} style={fieldStyle} /></label>
          <label>Evidencia<input value={input.evidence || ""} onChange={(event) => update(key, "evidence", event.target.value)} style={fieldStyle} /></label>
          <button type="button" style={fieldStyle} disabled={busy || !input.reason?.trim() || !input.conditions?.trim() || !input.evidence?.trim()} onClick={() => run(async () => {
            await decideProjectResumptionExceptionally(item.id, {
              authorized: Boolean(input.authorized), reason: input.reason,
              conditions: input.conditions, evidence: input.evidence,
            });
          })}>Registrar decisión L1</button>
        </article>;
      })}
    </section>

    <section>
      <h2>Sustituciones por ausencia de L3</h2>
      {substitutionContext.coordinations.length === 0 && <p>No hay coordinaciones L3 disponibles.</p>}
      {substitutionContext.coordinations.map((coordination) => {
        const key = `sub-${coordination.id}`;
        const input = forms[key] || {};
        const history = substitutions[coordination.project_id] || [];
        const active = history.filter((item) => item.coordination_id === coordination.id
          && item.is_active && new Date(item.valid_until) > new Date());
        const currentIds = new Set(active.map((item) => item.id));
        return <article key={coordination.id} style={panelStyle}>
          <h3>{coordination.project_name} · coordinación #{coordination.id}</h3>
          <p>Responsable L3: {coordination.coordinator_name}{coordination.coordinator_active ? " · activo" : " · inactivo"}</p>
          {active.map((item) => <div key={item.id}>
            <p>Sustitución #{item.id} · {item.substitute_id ? `sustituto ${item.substitute_id}` : "intervención L1 sin sustituto"} · {new Date(item.valid_from).toLocaleString()} a {new Date(item.valid_until).toLocaleString()}</p>
            <p>Ámbito: {item.scope}. Motivo: {item.reason}. Evidencia: {item.evidence}</p>
            <button type="button" style={fieldStyle} disabled={busy} onClick={() => run(() => endProjectSubstitution(coordination.project_id, item.id))}>Finalizar sustitución</button>
          </div>)}
          {history.filter((item) => item.coordination_id === coordination.id && !currentIds.has(item.id)).map((item) => <p key={item.id} style={{ color: "#aab2c5" }}>
            Historial #{item.id} · {item.substitute_id ? `sustituto ${item.substitute_id}` : "intervención L1"} · {item.is_active ? `vencida ${displayDate(item.valid_until)}` : `finalizada ${displayDate(item.ended_at)}`} · {item.reason}
          </p>)}
          {!active.length && <div style={{ display: "grid", gap: 8 }}>
            <label>Sustituto L3<select value={input.substitute_id || ""} onChange={(event) => update(key, "substitute_id", event.target.value)} style={fieldStyle}><option value="">Intervención L1 sin sustituto</option>{substitutionContext.substitutes.filter((candidate) => candidate.id !== coordination.coordinator_id).map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name} · #{candidate.id}</option>)}</select></label>
            <label>Ámbito<textarea value={input.scope || ""} onChange={(event) => update(key, "scope", event.target.value)} style={fieldStyle} /></label>
            <label>Motivo de ausencia<textarea value={input.reason || ""} onChange={(event) => update(key, "reason", event.target.value)} style={fieldStyle} /></label>
            <label>Referencia de evidencia<input value={input.evidence || ""} onChange={(event) => update(key, "evidence", event.target.value)} style={fieldStyle} /></label>
            {input.substitute_id && <p>La facultad temporal queda limitada a consulta de tareas.</p>}
            <label>Vigente desde<input type="datetime-local" value={input.valid_from || ""} onChange={(event) => update(key, "valid_from", event.target.value)} style={fieldStyle} /></label>
            <label>Vigente hasta<input type="datetime-local" value={input.valid_until || ""} onChange={(event) => update(key, "valid_until", event.target.value)} style={fieldStyle} /></label>
            <button type="button" style={fieldStyle} disabled={busy || !input.scope?.trim() || !input.reason?.trim() || !input.evidence?.trim() || !input.valid_from || !input.valid_until} onClick={() => run(() => createProjectSubstitution(coordination.project_id, {
              coordination_id: coordination.id, absent_level: "L3",
              absent_person_id: coordination.coordinator_id,
              substitute_id: input.substitute_id ? Number(input.substitute_id) : null,
              reason: input.reason, evidence: input.evidence, scope: input.scope,
              faculties: input.substitute_id ? ["tasks.view"] : [],
              valid_from: new Date(input.valid_from).toISOString(),
              valid_until: new Date(input.valid_until).toISOString(),
            }))}>Registrar sustitución L1</button>
          </div>}
        </article>;
      })}
    </section>
  </main>;
}
