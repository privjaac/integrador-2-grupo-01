import { useEffect, useState } from "react";
import { getClients } from "../../api/clients";
import { designateCoordinator, getTaskContext, removeCoordinator } from "../../api/tasks";
import { createProject, enterTechnicalValidation, getProjects } from "../../api/projects";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";

const fieldStyle = { padding: "10px 12px", background: "#0b0d1a", color: "white", border: "1px solid #34394a", borderRadius: 6 };

export default function ProjectsPage() {
  const { user } = useAuth();
  const canCreate = can(user, "projects", "create");
  const canStartValidation = can(user, "projects", "enterTechnicalValidation");
  const [projects, setProjects] = useState([]);
  const [clients, setClients] = useState([]);
  const [taskContext, setTaskContext] = useState({ coordinators: [], coordination_assignments: [] });
  const [coordinatorSelection, setCoordinatorSelection] = useState({});
  const [validationInputs, setValidationInputs] = useState({});
  const [form, setForm] = useState({ client_id: "", name: "", objective: "", scope: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    try {
      const [projectRows, clientRows] = await Promise.all([
        getProjects(),
        canCreate ? getClients() : Promise.resolve([]),
      ]);
      setProjects(projectRows);
      setClients(clientRows);
      if (user?.role === "L2") setTaskContext(await getTaskContext());
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudieron cargar los proyectos.");
    } finally { setLoading(false); }
  }

  useEffect(() => { refresh(); }, [canCreate]);

  async function assignCoordinator(projectId) {
    setError("");
    try {
      await designateCoordinator(projectId, Number(coordinatorSelection[projectId]));
      setCoordinatorSelection((items) => ({ ...items, [projectId]: "" }));
      setTaskContext(await getTaskContext());
    } catch (err) {
      setError(err.userMessage || "No se pudo designar la coordinación del proyecto.");
    }
  }

  async function unassignCoordinator(projectId, coordinatorId) {
    setError("");
    try {
      await removeCoordinator(projectId, coordinatorId);
      setTaskContext(await getTaskContext());
    } catch (err) {
      setError(err.userMessage || "No se pudo retirar la coordinación.");
    }
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    try {
      const created = await createProject({ ...form, client_id: Number(form.client_id), objective: form.objective || null, scope: form.scope || null });
      setProjects((items) => [...items, created]);
      setForm({ client_id: "", name: "", objective: "", scope: "" });
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo crear el proyecto.");
    }
  }

  async function submitValidation(projectId) {
    setError("");
    try {
      const updated = await enterTechnicalValidation(projectId, validationInputs[projectId] || {});
      setProjects((items) => items.map((item) => item.id === projectId ? updated : item));
      setValidationInputs((items) => ({ ...items, [projectId]: {} }));
    } catch (err) {
      setError(err.userMessage || err.response?.data?.detail || "No se pudo registrar el ingreso a validación técnica.");
    }
  }

  const validationFields = [
    ["scope_within_current_commitment", "El alcance está incluido en el compromiso vigente"],
    ["criteria_identifiable", "Los requisitos y criterios de validación son identificables"],
    ["results_and_evidence_available", "Hay resultados y evidencia disponibles para validar"],
    ["validation_conditions_ready", "El entorno, recursos y condiciones permiten validar"],
    ["responsible_parties_identified", "Los responsables adecuados están identificados"],
    ["dependencies_ready", "Las dependencias indispensables permiten validar"],
    ["pending_obligations_assessed", "Los pendientes y obligaciones fueron evaluados"],
    ["evidence", "Referencia de evidencia técnica"], ["reason", "Motivo de ingreso"],
  ];
  function updateValidation(projectId, field, value) {
    setValidationInputs((items) => ({ ...items, [projectId]: { ...items[projectId], [field]: value } }));
  }

  return <section style={{ color: "white", maxWidth: 1050, margin: "0 auto" }}>
    <h1>Proyectos</h1>
    <p style={{ color: "#aab2c5" }}>Los proyectos nuevos se crean en estado Planificado.</p>
    {error && <p role="alert" style={{ color: "#ff718b" }}>{String(error)}</p>}
    {canCreate && <form onSubmit={submit} style={{ display: "grid", gap: 12, margin: "24px 0", maxWidth: 600 }}>
      <h2>Crear proyecto</h2>
      <select required value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} style={fieldStyle}>
        <option value="">Selecciona un cliente</option>{clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
      </select>
      <input required maxLength={200} placeholder="Nombre del proyecto" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={fieldStyle} />
      <textarea placeholder="Objetivo (opcional)" value={form.objective} onChange={(e) => setForm({ ...form, objective: e.target.value })} style={fieldStyle} />
      <textarea placeholder="Alcance (opcional)" value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })} style={fieldStyle} />
      <button type="submit" style={{ ...fieldStyle, cursor: "pointer" }}>Crear proyecto</button>
    </form>}
    <h2>Proyectos registrados</h2>
    {loading ? <p>Cargando…</p> : projects.length === 0 ? <p>No hay proyectos registrados.</p> : <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr>{["Nombre", "Cliente", "Estado", "Objetivo", "Alcance", ...(user?.role === "L2" ? ["Coordinación L3"] : [])].map((label) => <th key={label} style={{ textAlign: "left", padding: 10, borderBottom: "1px solid #34394a" }}>{label}</th>)}</tr></thead><tbody>{projects.map((project) => {
      const assigned = taskContext.coordination_assignments?.filter((item) => item.project_id === project.id) || [];
      return <tr key={project.id}>{[project.name, project.client_name, project.status, project.objective || "—", project.scope || "—"].map((value, index) => <td key={index} style={{ padding: 10, borderBottom: "1px solid #202434" }}>{value}</td>)}{user?.role === "L2" && <td style={{ padding: 10, borderBottom: "1px solid #202434", minWidth: 240 }}>
        <div style={{ color: "#aab2c5", marginBottom: 6 }}>{assigned.length ? assigned.map((item) => <div key={item.coordinator_id} style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}><span>{item.coordinator_name}</span>{can(user, "tasks", "withdrawCoordination") && item.can_remove && <button type="button" onClick={() => unassignCoordinator(project.id, item.coordinator_id)} style={{ ...fieldStyle, padding: "5px 8px", cursor: "pointer" }}>Retirar</button>}</div>) : "Sin coordinación"}</div>
        <div style={{ display: "flex", gap: 6 }}><select aria-label={`Coordinación de ${project.name}`} value={coordinatorSelection[project.id] || ""} onChange={(event) => setCoordinatorSelection({ ...coordinatorSelection, [project.id]: event.target.value })} style={fieldStyle}><option value="">Seleccionar L3</option>{taskContext.coordinators?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><button type="button" disabled={!coordinatorSelection[project.id]} onClick={() => assignCoordinator(project.id)} style={{ ...fieldStyle, cursor: "pointer" }}>Designar</button></div>
      </td>}</tr>;
    })}</tbody></table></div>}
    {canStartValidation && projects.some((project) => project.status === "En ejecución") && <section style={{ marginTop: 28 }}>
      <h2>Ingreso a validación técnica</h2>
      <p style={{ color: "#aab2c5" }}>L3 evalúa preparación suficiente para comenzar una validación significativa. Este acto no declara resultados aprobados ni finaliza el proyecto.</p>
      {projects.filter((project) => project.status === "En ejecución").map((project) => <article key={project.id} style={{ border: "1px solid #34394a", borderRadius: 8, padding: 16, margin: "12px 0" }}>
        <h3>{project.name}</h3>
        <div style={{ display: "grid", gap: 8, maxWidth: 700 }}>{validationFields.map(([field, label]) => field === "evidence" || field === "reason" ? <label key={field} style={{ display: "grid", gap: 4 }}>{label}<textarea required value={validationInputs[project.id]?.[field] || ""} onChange={(event) => updateValidation(project.id, field, event.target.value)} style={fieldStyle} /></label> : <label key={field} style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" checked={validationInputs[project.id]?.[field] || false} onChange={(event) => updateValidation(project.id, field, event.target.checked)} />{label}</label>)}
          <button type="button" onClick={() => submitValidation(project.id)} disabled={validationFields.some(([field]) => !validationInputs[project.id]?.[field]?.trim())} style={{ ...fieldStyle, cursor: "pointer" }}>Registrar ingreso a validación técnica</button>
        </div>
        {(project.events || []).map((event, index) => <p key={`${event.event_type}-${index}`} style={{ color: "#aab2c5" }}>Historial: {event.previous_status} → {event.new_status} · {event.actor_name} · {new Date(event.occurred_at).toLocaleString()} · {event.reason}</p>)}
      </article>)}
    </section>}
  </section>;
}
