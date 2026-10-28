import { useCallback, useEffect, useState } from "react";
import { createProjectSubstitution, endProjectSubstitution, getProjectSubstitutions } from "../../api/projects";

const fieldStyle = { padding: "9px 11px", background: "#0b0d1a", color: "white", border: "1px solid #34394a", borderRadius: 6, width: "100%" };
const initialForm = { reason: "", evidence: "", scope: "", valid_from: "", valid_until: "", substitute_id: "", can_review: false };

export default function ProjectSubstitutionsPanel({ project, taskContext }) {
  const [items, setItems] = useState([]);
  const [forms, setForms] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setItems(await getProjectSubstitutions(project.id));
      setError("");
    } catch (requestError) {
      setError(requestError.userMessage || requestError.response?.data?.detail || "No se pudo cargar el historial de sustituciones.");
    }
  }, [project.id]);

  useEffect(() => { refresh(); }, [refresh]);

  const assignments = (taskContext.leadership_assignments || []).filter((item) => item.project_id === project.id);
  const leaders = taskContext.leaders || [];

  function update(leadershipId, field, value) {
    setForms((values) => ({ ...values, [leadershipId]: { ...(values[leadershipId] || initialForm), [field]: value } }));
  }

  async function run(action) {
    setBusy(true);
    setError("");
    try { await action(); await refresh(); }
    catch (requestError) { setError(requestError.userMessage || requestError.response?.data?.detail || "No se pudo registrar la sustitución."); }
    finally { setBusy(false); }
  }

  return <details style={{ margin: "10px 0", border: "1px solid #34394a", borderRadius: 8, padding: 12 }}>
    <summary style={{ cursor: "pointer" }}>Sustituciones temporales L4 · {project.name}</summary>
    <p style={{ color: "#aab2c5" }}>La suplencia requiere evidencia de ausencia y queda limitada a este proyecto, periodo y facultades.</p>
    {error && <p role="alert" style={{ color: "#ff718b" }}>{error}</p>}
    {assignments.length === 0 && <p>No hay designaciones L4 vigentes en tu coordinación.</p>}
    {assignments.map((assignment) => {
      const form = forms[assignment.leadership_id] || initialForm;
      const history = items.filter((item) => item.leadership_id === assignment.leadership_id);
      const active = history.find((item) => item.is_active && new Date(item.valid_until) > new Date());
      return <section key={assignment.leadership_id} style={{ borderTop: "1px solid #34394a", paddingTop: 10, marginTop: 10 }}>
        <h4>{assignment.leader_name} · L4 #{assignment.leader_id}</h4>
        {history.map((item) => <div key={item.id} style={{ color: "#aab2c5" }}>
          <p>Sustitución #{item.id} · {item.is_active && new Date(item.valid_until) <= new Date() ? "vencida" : item.is_active ? "vigente" : "finalizada"} · {new Date(item.valid_from).toLocaleString()} — {new Date(item.valid_until).toLocaleString()}</p>
          <p>Ámbito: {item.scope} · Motivo: {item.reason} · Evidencia: {item.evidence} · Facultades: {item.faculties.join(", ") || "supervisión L3 sin delegación"}</p>
          {item.is_active && <button type="button" style={fieldStyle} disabled={busy || new Date(item.valid_until) <= new Date()} onClick={() => run(() => endProjectSubstitution(project.id, item.id))}>Finalizar sustitución</button>}
        </div>)}
        {!active && <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
          <label>Sustituto L4<select value={form.substitute_id} onChange={(event) => update(assignment.leadership_id, "substitute_id", event.target.value)} style={fieldStyle}>
            <option value="">Supervisión temporal L3 sin sustituto</option>
            {leaders.filter((leader) => leader.id !== assignment.leader_id).map((leader) => <option key={leader.id} value={leader.id}>{leader.name} · #{leader.id}</option>)}
          </select></label>
          {form.substitute_id && <label><input type="checkbox" checked={form.can_review} onChange={(event) => update(assignment.leadership_id, "can_review", event.target.checked)} /> Autorizar revisión de tareas dentro de la responsabilidad L4</label>}
          <label>Ámbito<textarea value={form.scope} onChange={(event) => update(assignment.leadership_id, "scope", event.target.value)} style={fieldStyle} /></label>
          <label>Motivo y circunstancia de ausencia<textarea value={form.reason} onChange={(event) => update(assignment.leadership_id, "reason", event.target.value)} style={fieldStyle} /></label>
          <label>Referencia de evidencia<input value={form.evidence} onChange={(event) => update(assignment.leadership_id, "evidence", event.target.value)} style={fieldStyle} /></label>
          <label>Vigente desde<input type="datetime-local" value={form.valid_from} onChange={(event) => update(assignment.leadership_id, "valid_from", event.target.value)} style={fieldStyle} /></label>
          <label>Vigente hasta<input type="datetime-local" value={form.valid_until} onChange={(event) => update(assignment.leadership_id, "valid_until", event.target.value)} style={fieldStyle} /></label>
          <button type="button" style={fieldStyle} disabled={busy || !form.scope.trim() || !form.reason.trim() || !form.evidence.trim() || !form.valid_from || !form.valid_until} onClick={() => run(async () => {
            await createProjectSubstitution(project.id, {
              coordination_id: assignment.coordination_id, leadership_id: assignment.leadership_id,
              absent_level: "L4", absent_person_id: assignment.leader_id,
              substitute_id: form.substitute_id ? Number(form.substitute_id) : null,
              reason: form.reason, evidence: form.evidence, scope: form.scope,
              faculties: form.substitute_id ? ["tasks.view", ...(form.can_review ? ["tasks.review"] : [])] : [],
              valid_from: new Date(form.valid_from).toISOString(), valid_until: new Date(form.valid_until).toISOString(),
            });
            setForms((values) => ({ ...values, [assignment.leadership_id]: initialForm }));
          })}>Registrar sustitución temporal</button>
        </div>}
      </section>;
    })}
  </details>;
}
