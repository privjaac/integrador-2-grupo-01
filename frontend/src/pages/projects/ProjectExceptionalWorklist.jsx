import { useEffect, useState } from "react";
import {
  createProjectSubstitution, decideProjectCancellationExceptionally,
  decideProjectResumptionExceptionally, endProjectSubstitution,
  getL1ExceptionalCancellations, getL1ExceptionalResumptions,
  getL1SubstitutionContext, getProjectSubstitutions,
} from "../../api/projects";
import Button from "../../components/ui/Button";

const fieldStyle = { boxSizing: "border-box", padding: "10px 12px", background: "#0b0d1a", color: "white", border: "1px solid rgba(63,229,229,.28)", borderRadius: 6, width: "100%", font: "inherit" };
const pageStyle = { display: "grid", gap: 20, maxWidth: 1200, margin: "0 auto", color: "white" };
const sectionStyle = { display: "grid", gap: 12, padding: 18, background: "#111427", border: "1px solid rgba(63,229,229,.12)", borderRadius: 10 };
const panelStyle = { border: "1px solid rgba(63,229,229,.18)", background: "#0b0d1a", borderRadius: 8, padding: 16, display: "grid", gap: 12 };
const mutedStyle = { color: "#aab2c5", margin: 0 };
const disclosureStyle = { color: "#3fe5e5", cursor: "pointer", fontWeight: 600, padding: "4px 0" };
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

  return <main style={pageStyle}>
    <header>
      <h1 style={{ marginBottom: 6 }}>Actuaciones excepcionales</h1>
      <p style={mutedStyle}>Bandeja L1 para decisiones excepcionales acreditadas y sustituciones temporales de coordinación.</p>
    </header>
    {error && <p role="alert" style={{ color: "#ff718b", padding: 12, border: "1px solid rgba(255,51,102,.3)", borderRadius: 8 }}>{error}</p>}

    <section style={sectionStyle} aria-labelledby="exceptional-cancellations-heading">
      <div>
        <h2 id="exceptional-cancellations-heading" style={{ margin: "0 0 4px" }}>Cancelaciones excepcionales pendientes</h2>
        <p style={mutedStyle}>{cancellations.length ? `${cancellations.length} expediente${cancellations.length === 1 ? "" : "s"} por resolver` : "Bandeja al día"}</p>
      </div>
      {cancellations.length === 0 && <p role="status" style={mutedStyle}>No hay decisiones L1 pendientes.</p>}
      {cancellations.map((item) => {
        const key = `cancel-${item.id}`;
        const input = forms[key] || {};
        return <article key={item.id} style={panelStyle}>
          <div>
            <h3 style={{ margin: "0 0 8px" }}>{item.project_name} · expediente #{item.id}</h3>
            <p style={mutedStyle}>Estado del proyecto: {item.project_status} · Alcance: {item.cancelled_scope}</p>
          </div>
          <div style={{ padding: 12, borderRadius: 6, background: "rgba(255,255,255,.03)" }}>
            <strong>Motivo y evidencia recibidos</strong>
            <p style={mutedStyle}>{item.reason} · {item.evidence}</p>
          </div>
          {!!item.events.length && <details>
            <summary style={disclosureStyle}>Ver antecedentes e historial ({item.events.length})</summary>
            <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
              {item.events.map((event, index) => <div key={`${event.event_type}-${index}`} style={{ borderLeft: "2px solid rgba(63,229,229,.35)", paddingLeft: 12 }}>
                <p style={mutedStyle}>{event.event_type} · {event.actor_name} · {displayDate(event.occurred_at)} · {event.reason} · {event.evidence}</p>
                {event.data && <details><summary style={disclosureStyle}>Datos registrados</summary><pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(event.data, null, 2)}</pre></details>}
              </div>)}
            </div>
          </details>}
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}><input type="checkbox" checked={Boolean(input.authorized)} onChange={(event) => update(key, "authorized", event.target.checked)} /> Autorizar cancelación excepcional</label>
          {input.authorized && <label>Fecha prevista de efectividad<input type="datetime-local" value={input.planned_effective_at || ""} onChange={(event) => update(key, "planned_effective_at", event.target.value)} style={fieldStyle} /></label>}
          <label>Motivo de la decisión<textarea rows={3} value={input.reason || ""} onChange={(event) => update(key, "reason", event.target.value)} style={fieldStyle} /></label>
          <label>Evidencia de la decisión<input value={input.evidence || ""} onChange={(event) => update(key, "evidence", event.target.value)} style={fieldStyle} /></label>
          <Button variant="primary" disabled={busy || !input.reason?.trim() || !input.evidence?.trim() || (input.authorized && !input.planned_effective_at)} onClick={() => run(async () => {
            await decideProjectCancellationExceptionally(item.project_id, item.id, {
              authorized: Boolean(input.authorized), reason: input.reason, evidence: input.evidence,
              planned_effective_at: input.authorized ? new Date(input.planned_effective_at).toISOString() : null,
            });
          })}>Registrar decisión L1</Button>
        </article>;
      })}
    </section>

    <section style={sectionStyle} aria-labelledby="exceptional-resumptions-heading">
      <div>
        <h2 id="exceptional-resumptions-heading" style={{ margin: "0 0 4px" }}>Reanudaciones que requieren decisión L1</h2>
        <p style={mutedStyle}>{resumptions.length ? `${resumptions.length} expediente${resumptions.length === 1 ? "" : "s"} por resolver` : "Bandeja al día"}</p>
      </div>
      {resumptions.length === 0 && <p role="status" style={mutedStyle}>No hay reanudaciones pendientes de decisión L1.</p>}
      {resumptions.map((item) => {
        const key = `resume-${item.id}`;
        const input = forms[key] || {};
        return <article key={item.id} style={panelStyle}>
          <div>
            <h3 style={{ margin: "0 0 8px" }}>{item.project_name} · reanudación #{item.id}</h3>
            <p style={mutedStyle}>Estado conservado: {item.project_status} · cancelación #{item.cancellation_id}</p>
          </div>
          <details>
            <summary style={disclosureStyle}>Consultar antecedentes de cancelación</summary>
            <div style={{ marginTop: 10 }}>
              <strong>{item.cancellation.reason}</strong>
              <p style={mutedStyle}>Alcance: {item.cancellation.cancelled_scope} · evidencia: {item.cancellation.evidence}</p>
              {[...item.cancellation.events, ...item.events].map((event, index) => <div key={`${event.event_type}-${index}`} style={{ borderLeft: "2px solid rgba(63,229,229,.35)", paddingLeft: 12, margin: "8px 0" }}>
                <p style={mutedStyle}>{event.event_type} · {event.actor_name} · {displayDate(event.occurred_at)} · {event.reason} · {event.evidence}</p>
                {event.data && <details><summary style={disclosureStyle}>Datos registrados</summary><pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(event.data, null, 2)}</pre></details>}
              </div>)}
            </div>
          </details>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}><input type="checkbox" checked={Boolean(input.authorized)} onChange={(event) => update(key, "authorized", event.target.checked)} /> Autorizar reanudación excepcional</label>
          <label>Motivo<textarea rows={3} value={input.reason || ""} onChange={(event) => update(key, "reason", event.target.value)} style={fieldStyle} /></label>
          <label>Condiciones<textarea rows={3} value={input.conditions || ""} onChange={(event) => update(key, "conditions", event.target.value)} style={fieldStyle} /></label>
          <label>Evidencia<input value={input.evidence || ""} onChange={(event) => update(key, "evidence", event.target.value)} style={fieldStyle} /></label>
          <Button disabled={busy || !input.reason?.trim() || !input.conditions?.trim() || !input.evidence?.trim()} onClick={() => run(async () => {
            await decideProjectResumptionExceptionally(item.id, {
              authorized: Boolean(input.authorized), reason: input.reason,
              conditions: input.conditions, evidence: input.evidence,
            });
          })}>Registrar decisión L1</Button>
        </article>;
      })}
    </section>

    <section style={sectionStyle} aria-labelledby="exceptional-substitutions-heading">
      <div>
        <h2 id="exceptional-substitutions-heading" style={{ margin: "0 0 4px" }}>Sustituciones por ausencia de L3</h2>
        <p style={mutedStyle}>La intervención temporal queda limitada a la coordinación y al ámbito que se documenten.</p>
      </div>
      {substitutionContext.coordinations.length === 0 && <p role="status" style={mutedStyle}>No hay coordinaciones L3 disponibles.</p>}
      {substitutionContext.coordinations.map((coordination) => {
        const key = `sub-${coordination.id}`;
        const input = forms[key] || {};
        const history = substitutions[coordination.project_id] || [];
        const active = history.filter((item) => item.coordination_id === coordination.id
          && item.is_active && new Date(item.valid_until) > new Date());
        const currentIds = new Set(active.map((item) => item.id));
        return <article key={coordination.id} style={panelStyle}>
          <div>
            <h3 style={{ margin: "0 0 8px" }}>{coordination.project_name} · {coordination.scope || `coordinación #${coordination.id}`}</h3>
            <p style={mutedStyle}>Coordinación #{coordination.id} · responsable L3: {coordination.coordinator_name}{coordination.coordinator_active ? " · activo" : " · inactivo"}</p>
          </div>
          {active.map((item) => <div key={item.id}>
            <p><strong>Sustitución vigente #{item.id}</strong> · {item.substitute_id ? `sustituto ${item.substitute_id}` : "intervención L1 sin sustituto"}</p>
            <p style={mutedStyle}>{displayDate(item.valid_from)} a {displayDate(item.valid_until)} · ámbito: {item.scope}</p>
            <details><summary style={disclosureStyle}>Ver motivo e evidencia</summary><p style={mutedStyle}>{item.reason} · {item.evidence}</p></details>
            <Button variant="secondary" disabled={busy} onClick={() => run(() => endProjectSubstitution(coordination.project_id, item.id))}>Finalizar sustitución</Button>
          </div>)}
          {history.filter((item) => item.coordination_id === coordination.id && !currentIds.has(item.id)).length > 0 && <details>
            <summary style={disclosureStyle}>Historial de sustituciones ({history.filter((item) => item.coordination_id === coordination.id && !currentIds.has(item.id)).length})</summary>
            {history.filter((item) => item.coordination_id === coordination.id && !currentIds.has(item.id)).map((item) => <p key={item.id} style={mutedStyle}>
              #{item.id} · {item.substitute_id ? `sustituto ${item.substitute_id}` : "intervención L1"} · {item.is_active ? `vencida ${displayDate(item.valid_until)}` : `finalizada ${displayDate(item.ended_at)}`} · {item.reason}
            </p>)}
          </details>}
          {!active.length && <details>
            <summary style={disclosureStyle}>Registrar una sustitución</summary>
            <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
            <label>Sustituto L3<select value={input.substitute_id || ""} onChange={(event) => update(key, "substitute_id", event.target.value)} style={fieldStyle}><option value="">Intervención L1 sin sustituto</option>{substitutionContext.substitutes.filter((candidate) => candidate.id !== coordination.coordinator_id).map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name} · #{candidate.id}</option>)}</select></label>
            <label>Ámbito<textarea value={input.scope || ""} onChange={(event) => update(key, "scope", event.target.value)} style={fieldStyle} /></label>
            <label>Motivo de ausencia<textarea value={input.reason || ""} onChange={(event) => update(key, "reason", event.target.value)} style={fieldStyle} /></label>
            <label>Referencia de evidencia<input value={input.evidence || ""} onChange={(event) => update(key, "evidence", event.target.value)} style={fieldStyle} /></label>
            {input.substitute_id && <p style={mutedStyle}>La facultad temporal queda limitada a consulta de tareas.</p>}
            <label>Vigente desde<input type="datetime-local" value={input.valid_from || ""} onChange={(event) => update(key, "valid_from", event.target.value)} style={fieldStyle} /></label>
            <label>Vigente hasta<input type="datetime-local" value={input.valid_until || ""} onChange={(event) => update(key, "valid_until", event.target.value)} style={fieldStyle} /></label>
            <Button disabled={busy || !input.scope?.trim() || !input.reason?.trim() || !input.evidence?.trim() || !input.valid_from || !input.valid_until} onClick={() => run(() => createProjectSubstitution(coordination.project_id, {
              coordination_id: coordination.id, absent_level: "L3",
              absent_person_id: coordination.coordinator_id,
              substitute_id: input.substitute_id ? Number(input.substitute_id) : null,
              reason: input.reason, evidence: input.evidence, scope: input.scope,
              faculties: input.substitute_id ? ["tasks.view"] : [],
              valid_from: new Date(input.valid_from).toISOString(),
              valid_until: new Date(input.valid_until).toISOString(),
            }))}>Registrar sustitución L1</Button>
            </div>
          </details>}
        </article>;
      })}
    </section>
  </main>;
}
