import { useEffect, useState } from "react";
import { getClients } from "../../api/clients";
import { designateCoordinator, getTaskContext, removeCoordinator } from "../../api/tasks";
import {
  createCommercialAuthorization, createProject, enterTechnicalValidation,
  getCommercialAuthorizations, getProjects, startProject, withdrawCommercialAuthorization,
} from "../../api/projects";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";

const fieldStyle = { padding: "10px 12px", background: "#0b0d1a", color: "white", border: "1px solid #34394a", borderRadius: 6 };

export default function ProjectsPage() {
  const { user } = useAuth();
  const canCreate = can(user, "projects", "create");
  const canStartValidation = can(user, "projects", "enterTechnicalValidation");
  const canAuthorizeStart = can(user, "projects", "authorizeProjectStart");
  const canStartProject = can(user, "projects", "startProject");
  const [projects, setProjects] = useState([]);
  const [clients, setClients] = useState([]);
  const [commercialAuthorizations, setCommercialAuthorizations] = useState({});
  const [taskContext, setTaskContext] = useState({ coordinators: [], coordination_assignments: [] });
  const [coordinatorSelection, setCoordinatorSelection] = useState({});
  const [validationInputs, setValidationInputs] = useState({});
  const [authorizationInputs, setAuthorizationInputs] = useState({});
  const [startInputs, setStartInputs] = useState({});
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
      const context = ["L2", "L3"].includes(user?.role)
        ? await getTaskContext()
        : { coordinators: [], coordination_assignments: [], projects: [] };
      setProjects(projectRows);
      setClients(clientRows);
      setTaskContext(context);
      const authorizationProjectIds = user?.role === "L3"
        ? new Set((context.projects || []).map((item) => item.id))
        : user?.role === "L2" ? new Set(projectRows.map((item) => item.id)) : new Set();
      const authorizationRows = await Promise.all(
        projectRows.filter((project) => authorizationProjectIds.has(project.id)).map(async (project) => [
          project.id, await getCommercialAuthorizations(project.id),
        ]),
      );
      setCommercialAuthorizations(Object.fromEntries(authorizationRows));
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

  async function submitCommercialAuthorization(projectId) {
    setError("");
    try {
      const input = authorizationInputs[projectId] || {};
      await createCommercialAuthorization(projectId, {
        ...input,
        effective_at: new Date(input.effective_at).toISOString(),
        expires_at: input.expires_at ? new Date(input.expires_at).toISOString() : null,
        replaces_authorization_id: input.replaces_authorization_id ? Number(input.replaces_authorization_id) : null,
        replacement_reason: input.replaces_authorization_id ? input.replacement_reason : null,
      });
      await refresh();
      setAuthorizationInputs((items) => ({ ...items, [projectId]: {} }));
    } catch (err) {
      setError(err.userMessage || err.response?.data?.detail || "No se pudo registrar la habilitación comercial.");
    }
  }

  async function withdrawAuthorization(projectId, authorizationId) {
    const reason = window.prompt("Motivo para retirar esta habilitación comercial:");
    if (!reason?.trim()) return;
    setError("");
    try {
      await withdrawCommercialAuthorization(projectId, authorizationId, reason.trim());
      await refresh();
    } catch (err) {
      setError(err.userMessage || err.response?.data?.detail || "No se pudo retirar la habilitación comercial.");
    }
  }

  async function submitProjectStart(projectId) {
    setError("");
    try {
      const input = startInputs[projectId] || {};
      const updated = await startProject(projectId, {
        ...input,
        commercial_authorization_id: Number(input.commercial_authorization_id),
      });
      setProjects((items) => items.map((item) => item.id === projectId ? updated : item));
      setStartInputs((items) => ({ ...items, [projectId]: {} }));
      await refresh();
    } catch (err) {
      setError(err.userMessage || err.response?.data?.detail || "No se pudo registrar el inicio del proyecto.");
    }
  }

  function updateAuthorization(projectId, field, value) {
    setAuthorizationInputs((items) => ({ ...items, [projectId]: { ...items[projectId], [field]: value } }));
  }

  function updateStart(projectId, field, value) {
    setStartInputs((items) => ({ ...items, [projectId]: { ...items[projectId], [field]: value } }));
  }

  function localDateTime(minutesAhead = 10) {
    const value = new Date(Date.now() + minutesAhead * 60_000);
    value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
    return value.toISOString().slice(0, 16);
  }

  const scopedProjects = user?.role === "L3"
    ? new Set((taskContext.projects || []).map((item) => item.id))
    : new Set();

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
    {canAuthorizeStart && <section style={{ marginTop: 28 }}>
      <h2>Habilitación comercial para iniciar</h2>
      <p style={{ color: "#aab2c5" }}>L2 registra la autorización positiva y sus referencias. Este acto no inicia automáticamente el proyecto.</p>
      {projects.map((project) => {
        const rows = commercialAuthorizations[project.id] || [];
        const input = authorizationInputs[project.id] || {};
        const replaceable = rows.filter((item) => !item.events?.some((event) => ["retirada", "sustituida"].includes(event.event_type)));
        return <article key={project.id} style={{ border: "1px solid #34394a", borderRadius: 8, padding: 16, margin: "12px 0" }}>
          <h3>{project.name}</h3>
          {rows.map((item) => <div key={item.id} style={{ color: "#aab2c5", marginBottom: 8 }}>
            <p>#{item.id} · {item.authorized_scope} · L2 {item.authorized_by_name} · efectiva {new Date(item.effective_at).toLocaleString()}{item.expires_at ? ` · vence ${new Date(item.expires_at).toLocaleString()}` : " · sin vencimiento específico"}</p>
            <p>Compromiso: {item.commitment_reference} · Condiciones: {item.start_conditions} · Evidencia: {item.evidence_reference}</p>
            {item.events?.map((event, index) => <p key={index}>{event.event_type} por {event.actor_name} · {event.reason}</p>)}
            {!item.events?.length && <button type="button" onClick={() => withdrawAuthorization(project.id, item.id)} style={fieldStyle}>Retirar habilitación</button>}
          </div>)}
          <form onSubmit={(event) => { event.preventDefault(); submitCommercialAuthorization(project.id); }} style={{ display: "grid", gap: 8, maxWidth: 700 }}>
            <label>Alcance autorizado<textarea required value={input.authorized_scope || ""} onChange={(event) => updateAuthorization(project.id, "authorized_scope", event.target.value)} style={fieldStyle} /></label>
            <label>Referencia del compromiso<input required value={input.commitment_reference || ""} onChange={(event) => updateAuthorization(project.id, "commitment_reference", event.target.value)} style={fieldStyle} /></label>
            <label>Condiciones de inicio acreditadas<textarea required value={input.start_conditions || ""} onChange={(event) => updateAuthorization(project.id, "start_conditions", event.target.value)} style={fieldStyle} /></label>
            <label style={{ display: "flex", gap: 8 }}><input type="checkbox" checked={input.start_conditions_accredited || false} onChange={(event) => updateAuthorization(project.id, "start_conditions_accredited", event.target.checked)} />Confirmo que las condiciones de inicio documentadas están satisfechas</label>
            <label>Referencia documental<input required value={input.evidence_reference || ""} onChange={(event) => updateAuthorization(project.id, "evidence_reference", event.target.value)} style={fieldStyle} /></label>
            <label>Efectiva desde<input type="datetime-local" required value={input.effective_at || localDateTime()} onChange={(event) => updateAuthorization(project.id, "effective_at", event.target.value)} style={fieldStyle} /></label>
            <label>Vencimiento específico documentado (opcional)<input type="datetime-local" value={input.expires_at || ""} onChange={(event) => updateAuthorization(project.id, "expires_at", event.target.value)} style={fieldStyle} /></label>
            {replaceable.length > 0 && <label>Sustituir habilitación (opcional)<select value={input.replaces_authorization_id || ""} onChange={(event) => updateAuthorization(project.id, "replaces_authorization_id", event.target.value)} style={fieldStyle}><option value="">Nueva habilitación independiente</option>{replaceable.map((item) => <option key={item.id} value={item.id}>#{item.id} · {item.authorized_scope}</option>)}</select></label>}
            {input.replaces_authorization_id && <label>Motivo de sustitución<input required value={input.replacement_reason || ""} onChange={(event) => updateAuthorization(project.id, "replacement_reason", event.target.value)} style={fieldStyle} /></label>}
            <button type="submit" disabled={!input.start_conditions_accredited} style={fieldStyle}>Registrar habilitación positiva</button>
          </form>
        </article>;
      })}
    </section>}
    {canStartProject && projects.some((project) => (taskContext.projects || []).some((item) => item.id === project.id) && project.status === "Planificado") && <section style={{ marginTop: 28 }}>
      <h2>Inicio de ejecución</h2>
      <p style={{ color: "#aab2c5" }}>L3 registra la preparación técnica inicial; la información comercial detallada permanece reservada a L2.</p>
      {projects.filter((project) => (taskContext.projects || []).some((item) => item.id === project.id) && project.status === "Planificado").map((project) => {
        const rows = commercialAuthorizations[project.id] || [];
        const input = startInputs[project.id] || {};
        return <article key={project.id} style={{ border: "1px solid #34394a", borderRadius: 8, padding: 16, margin: "12px 0" }}><h3>{project.name}</h3>
          {rows.length === 0 ? <p>No hay habilitación comercial aplicable disponible.</p> : <div style={{ display: "grid", gap: 8, maxWidth: 700 }}>
            <label>Habilitación L2<select required value={input.commercial_authorization_id || ""} onChange={(event) => updateStart(project.id, "commercial_authorization_id", event.target.value)} style={fieldStyle}><option value="">Seleccionar</option>{rows.map((item) => <option key={item.id} value={item.id}>#{item.id} · {item.authorized_scope} · efectiva {new Date(item.effective_at).toLocaleString()}</option>)}</select></label>
            <label>Actividades iniciales<textarea required value={input.initial_activities || ""} onChange={(event) => updateStart(project.id, "initial_activities", event.target.value)} style={fieldStyle} /></label>
            <label><input type="checkbox" checked={input.initial_scope_within_authorization || false} onChange={(event) => updateStart(project.id, "initial_scope_within_authorization", event.target.checked)} />Confirmo que las actividades iniciales están comprendidas en el alcance autorizado</label>
            {[["responsible_parties_identified", "Responsables identificados"], ["resources_ready", "Recursos listos"], ["dependencies_ready", "Dependencias iniciales listas"]].map(([field, label]) => <label key={field}><input type="checkbox" checked={input[field] || false} onChange={(event) => updateStart(project.id, field, event.target.checked)} /> {label}</label>)}
            <label><input type="checkbox" checked={input.restrictions_assessed || false} onChange={(event) => updateStart(project.id, "restrictions_assessed", event.target.checked)} />Evalué las restricciones relevantes para el inicio</label>
            <label>Motivo<textarea required value={input.reason || ""} onChange={(event) => updateStart(project.id, "reason", event.target.value)} style={fieldStyle} /></label>
            <label>Evidencia técnica<input required value={input.evidence || ""} onChange={(event) => updateStart(project.id, "evidence", event.target.value)} style={fieldStyle} /></label>
            <button type="button" disabled={!input.commercial_authorization_id || !input.initial_activities?.trim() || !input.reason?.trim() || !input.evidence?.trim() || !input.initial_scope_within_authorization || !input.responsible_parties_identified || !input.resources_ready || !input.dependencies_ready || !input.restrictions_assessed} onClick={() => submitProjectStart(project.id)} style={fieldStyle}>Iniciar ejecución</button>
          </div>}
        </article>;
      })}
    </section>}
  </section>;
}
