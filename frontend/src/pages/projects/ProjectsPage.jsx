import { useEffect, useState } from "react";
import { getClients } from "../../api/clients";
import { designateCoordinator, getTaskContext, removeCoordinator } from "../../api/tasks";
import {
  classifyProjectTask, createCommercialAuthorization, createDeliveryAuthorization,
  createProject, enterTechnicalValidation, getCommercialAuthorizations,
  getDeliveryAuthorizations, getDeliveryContext, getProjects,
  markProjectReadyForDelivery, recordTechnicalEvaluation, returnProjectToExecution,
  formalizeProjectDelivery, getProjectDeliveries, recordProjectDelivery, reviewProjectDeliveryVersion,
  startProject, withdrawCommercialAuthorization, withdrawDeliveryAuthorization,
} from "../../api/projects";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";

const fieldStyle = { padding: "10px 12px", background: "#0b0d1a", color: "white", border: "1px solid #34394a", borderRadius: 6 };

export default function ProjectsPage() {
  const { user } = useAuth();
  const canCreate = can(user, "projects", "create");
  const canStartValidation = can(user, "projects", "enterTechnicalValidation");
  const canReturnToExecution = can(user, "projects", "returnProjectToExecution");
  const canAuthorizeStart = can(user, "projects", "authorizeProjectStart");
  const canStartProject = can(user, "projects", "startProject");
  const canClassifyTasks = can(user, "projects", "classifyProjectTasks");
  const canEvaluateClosure = can(user, "projects", "evaluateProjectClosure");
  const canMarkReady = can(user, "projects", "markProjectReadyForDelivery");
  const canAuthorizeDelivery = can(user, "projects", "authorizeProjectDelivery");
  const canRecordDelivery = can(user, "projects", "recordProjectDelivery");
  const canFormalizeDelivery = can(user, "projects", "formalizeProjectDelivery");
  const canReviewDeliveryVersion = can(user, "projects", "reviewProjectDeliveryVersion");
  const [projects, setProjects] = useState([]);
  const [clients, setClients] = useState([]);
  const [commercialAuthorizations, setCommercialAuthorizations] = useState({});
  const [taskContext, setTaskContext] = useState({ coordinators: [], coordination_assignments: [] });
  const [coordinatorSelection, setCoordinatorSelection] = useState({});
  const [validationInputs, setValidationInputs] = useState({});
  const [returnInputs, setReturnInputs] = useState({});
  const [authorizationInputs, setAuthorizationInputs] = useState({});
  const [startInputs, setStartInputs] = useState({});
  const [deliveryContexts, setDeliveryContexts] = useState({});
  const [deliveryAuthorizations, setDeliveryAuthorizations] = useState({});
  const [projectDeliveries, setProjectDeliveries] = useState({});
  const [deliveryInputs, setDeliveryInputs] = useState({});
  const [deliveryReviewInputs, setDeliveryReviewInputs] = useState({});
  const [formalizationInputs, setFormalizationInputs] = useState({});
  const [classificationInputs, setClassificationInputs] = useState({});
  const [evaluationInputs, setEvaluationInputs] = useState({});
  const [deliveryAuthorizationInputs, setDeliveryAuthorizationInputs] = useState({});
  const [readyInputs, setReadyInputs] = useState({});
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
      const deliveryProjectIds = user?.role === "L3"
        ? [...authorizationProjectIds]
        : user?.role === "L2" ? projectRows.map((project) => project.id) : [];
      const deliveryRows = await Promise.all(deliveryProjectIds.map(async (projectId) => [
        projectId, await getDeliveryAuthorizations(projectId),
      ]));
      setDeliveryAuthorizations(Object.fromEntries(deliveryRows));
      const deliveryRecordRows = await Promise.all(deliveryProjectIds.map(async (projectId) => [
        projectId, await getProjectDeliveries(projectId),
      ]));
      setProjectDeliveries(Object.fromEntries(deliveryRecordRows));
      const deliveryContextRows = user?.role === "L3"
        ? await Promise.all(deliveryProjectIds.map(async (projectId) => [projectId, await getDeliveryContext(projectId)]))
        : [];
      setDeliveryContexts(Object.fromEntries(deliveryContextRows));
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

  async function submitReturn(projectId) {
    setError("");
    try {
      const updated = await returnProjectToExecution(projectId, returnInputs[projectId] || {});
      setProjects((items) => items.map((item) => item.id === projectId ? updated : item));
      setReturnInputs((items) => ({ ...items, [projectId]: {} }));
    } catch (err) {
      setError(err.userMessage || err.response?.data?.detail || "No se pudo registrar la devolución a ejecución.");
    }
  }

  async function saveTaskClassification(projectId, taskId) {
    setError("");
    try {
      await classifyProjectTask(projectId, taskId, classificationInputs[taskId] || {});
      await refresh();
      setClassificationInputs((items) => ({ ...items, [taskId]: {} }));
    } catch (err) {
      setError(err.userMessage || err.response?.data?.detail || "No se pudo registrar la clasificación de la tarea.");
    }
  }

  async function saveTechnicalEvaluation(projectId) {
    setError("");
    try {
      const input = evaluationInputs[projectId] || {};
      const context = deliveryContexts[projectId];
      const optionalTaskAssessments = (context?.tasks || [])
        .filter((task) => task.is_mandatory === false && task.status !== "Finalizada")
        .map((task) => ({ task_id: task.task_id, ...(input.optionalTasks?.[task.task_id] || {}) }));
      await recordTechnicalEvaluation(projectId, {
        ...input,
        optional_task_assessments: optionalTaskAssessments,
        validated_versions: (input.validated_versions_text || "").split("\n").map((item) => item.trim()).filter(Boolean),
      });
      await refresh();
      setEvaluationInputs((items) => ({ ...items, [projectId]: {} }));
    } catch (err) {
      setError(err.userMessage || err.response?.data?.detail || "No se pudo registrar la evaluación técnica.");
    }
  }

  async function submitDelivery(projectId) {
    setError("");
    try {
      const input = deliveryInputs[projectId] || {};
      await recordProjectDelivery(projectId, {
        ...input,
        preparation_authorization_id: Number(input.preparation_authorization_id),
        occurred_at: new Date(input.occurred_at || localDateTime(0)).toISOString(),
        covers_project_scope: input.delivery_type === "integral",
      });
      await refresh();
      setDeliveryInputs((items) => ({ ...items, [projectId]: {} }));
    } catch (err) {
      setError(err.userMessage || err.response?.data?.detail || "No se pudo registrar la constancia de entrega.");
    }
  }

  async function submitDeliveryReview(projectId) {
    setError("");
    try {
      await reviewProjectDeliveryVersion(projectId, deliveryReviewInputs[projectId] || {});
      await refresh();
      setDeliveryReviewInputs((items) => ({ ...items, [projectId]: {} }));
    } catch (err) {
      setError(err.userMessage || err.response?.data?.detail || "No se pudo registrar la revisión de versión.");
    }
  }

  async function submitFormalization(projectId) {
    setError("");
    try {
      const input = formalizationInputs[projectId] || {};
      const updated = await formalizeProjectDelivery(projectId, {
        delivery_ids: input.delivery_ids || [],
        integral_coverage_confirmed: Boolean(input.integral_coverage_confirmed),
        coverage_evidence: input.coverage_evidence,
        reason: input.reason,
      });
      setProjects((items) => items.map((item) => item.id === projectId ? updated : item));
      await refresh();
      setFormalizationInputs((items) => ({ ...items, [projectId]: {} }));
    } catch (err) {
      setError(err.userMessage || err.response?.data?.detail || "No se pudo formalizar la entrega.");
    }
  }

  async function saveDeliveryAuthorization(projectId) {
    setError("");
    try {
      const input = deliveryAuthorizationInputs[projectId] || {};
      const effectiveAt = input.effective_at || localDateTime();
      await createDeliveryAuthorization(projectId, {
        ...input,
        effective_at: new Date(effectiveAt).toISOString(),
        expires_at: input.expires_at ? new Date(input.expires_at).toISOString() : null,
        replaces_authorization_id: input.replaces_authorization_id ? Number(input.replaces_authorization_id) : null,
        replacement_reason: input.replaces_authorization_id ? input.replacement_reason : null,
      });
      await refresh();
      setDeliveryAuthorizationInputs((items) => ({ ...items, [projectId]: {} }));
    } catch (err) {
      setError(err.userMessage || err.response?.data?.detail || "No se pudo registrar la habilitación de entrega.");
    }
  }

  async function withdrawDelivery(projectId, authorizationId) {
    const reason = window.prompt("Motivo para retirar la habilitación para preparar entrega:");
    if (!reason?.trim()) return;
    setError("");
    try {
      await withdrawDeliveryAuthorization(projectId, authorizationId, reason.trim());
      await refresh();
    } catch (err) {
      setError(err.userMessage || err.response?.data?.detail || "No se pudo retirar la habilitación de entrega.");
    }
  }

  async function submitReadyForDelivery(projectId) {
    setError("");
    try {
      const input = readyInputs[projectId] || {};
      const updated = await markProjectReadyForDelivery(projectId, {
        delivery_authorization_id: Number(input.delivery_authorization_id),
        reason: input.reason,
      });
      setProjects((items) => items.map((item) => item.id === projectId ? updated : item));
      setReadyInputs((items) => ({ ...items, [projectId]: {} }));
      await refresh();
    } catch (err) {
      setError(err.userMessage || err.response?.data?.detail || "No se pudo registrar Listo para entrega.");
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
  function updateReturn(projectId, field, value) {
    setReturnInputs((items) => ({ ...items, [projectId]: { ...items[projectId], [field]: value } }));
  }
  function updateClassification(taskId, field, value) {
    setClassificationInputs((items) => ({ ...items, [taskId]: { ...items[taskId], [field]: value } }));
  }
  function updateEvaluation(projectId, field, value) {
    setEvaluationInputs((items) => ({ ...items, [projectId]: { ...items[projectId], [field]: value } }));
  }
  function updateOptionalAssessment(projectId, taskId, field, value) {
    setEvaluationInputs((items) => ({
      ...items,
      [projectId]: {
        ...items[projectId],
        optionalTasks: {
          ...items[projectId]?.optionalTasks,
          [taskId]: { ...items[projectId]?.optionalTasks?.[taskId], [field]: value },
        },
      },
    }));
  }
  function updateDeliveryAuthorization(projectId, field, value) {
    setDeliveryAuthorizationInputs((items) => ({ ...items, [projectId]: { ...items[projectId], [field]: value } }));
  }
  function updateReady(projectId, field, value) {
    setReadyInputs((items) => ({ ...items, [projectId]: { ...items[projectId], [field]: value } }));
  }

  function updateDelivery(projectId, field, value) {
    setDeliveryInputs((items) => ({ ...items, [projectId]: { ...items[projectId], [field]: value } }));
  }
  function updateDeliveryReview(deliveryId, field, value) {
    setDeliveryReviewInputs((items) => ({ ...items, [deliveryId]: { ...items[deliveryId], [field]: value } }));
  }
  function updateFormalization(projectId, field, value) {
    setFormalizationInputs((items) => ({ ...items, [projectId]: { ...items[projectId], [field]: value } }));
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
    {canStartValidation && projects.some((project) => project.status === "En ejecución" && scopedProjects.has(project.id)) && <section style={{ marginTop: 28 }}>
      <h2>Ingreso a validación técnica</h2>
      <p style={{ color: "#aab2c5" }}>L3 evalúa preparación suficiente para comenzar una validación significativa. Este acto no declara resultados aprobados ni finaliza el proyecto.</p>
      {projects.filter((project) => project.status === "En ejecución" && scopedProjects.has(project.id)).map((project) => <article key={project.id} style={{ border: "1px solid #34394a", borderRadius: 8, padding: 16, margin: "12px 0" }}>
        <h3>{project.name}</h3>
        <div style={{ display: "grid", gap: 8, maxWidth: 700 }}>{validationFields.map(([field, label]) => field === "evidence" || field === "reason" ? <label key={field} style={{ display: "grid", gap: 4 }}>{label}<textarea required value={validationInputs[project.id]?.[field] || ""} onChange={(event) => updateValidation(project.id, field, event.target.value)} style={fieldStyle} /></label> : <label key={field} style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" checked={validationInputs[project.id]?.[field] || false} onChange={(event) => updateValidation(project.id, field, event.target.checked)} />{label}</label>)}
          <button type="button" onClick={() => submitValidation(project.id)} disabled={validationFields.some(([field]) => !validationInputs[project.id]?.[field]?.trim())} style={{ ...fieldStyle, cursor: "pointer" }}>Registrar ingreso a validación técnica</button>
        </div>
        {(project.events || []).map((event, index) => <p key={`${event.event_type}-${index}`} style={{ color: "#aab2c5" }}>Historial: {event.previous_status} → {event.new_status} · {event.actor_name} · {new Date(event.occurred_at).toLocaleString()} · {event.reason}</p>)}
      </article>)}
    </section>}
    {canReturnToExecution && projects.some((project) => project.status === "En validación técnica" && scopedProjects.has(project.id)) && <section style={{ marginTop: 28 }}>
      <h2>Devolución a ejecución</h2>
      <p style={{ color: "#aab2c5" }}>L3 puede devolver el proyecto cuando el trabajo adicional sea necesario para la suficiencia o continuidad de la validación y permanezca dentro del compromiso vigente.</p>
      {projects.filter((project) => project.status === "En validación técnica" && scopedProjects.has(project.id)).map((project) => <article key={project.id} style={{ border: "1px solid #34394a", borderRadius: 8, padding: 16, margin: "12px 0" }}>
        <h3>{project.name}</h3>
        <div style={{ display: "grid", gap: 8, maxWidth: 700 }}>
          {[["additional_execution_required", "Se requiere trabajo adicional"], ["materially_affects_validation", "Afecta materialmente la suficiencia o continuidad de la validación"], ["within_current_commitment", "El trabajo permanece dentro del compromiso vigente"]].map(([field, label]) => <label key={field} style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" checked={returnInputs[project.id]?.[field] || false} onChange={(event) => updateReturn(project.id, field, event.target.checked)} />{label}</label>)}
          <label style={{ display: "grid", gap: 4 }}>Evidencia<textarea required value={returnInputs[project.id]?.evidence || ""} onChange={(event) => updateReturn(project.id, "evidence", event.target.value)} style={fieldStyle} /></label>
          <label style={{ display: "grid", gap: 4 }}>Motivo<textarea required value={returnInputs[project.id]?.reason || ""} onChange={(event) => updateReturn(project.id, "reason", event.target.value)} style={fieldStyle} /></label>
          <button type="button" onClick={() => submitReturn(project.id)} disabled={["additional_execution_required", "materially_affects_validation", "within_current_commitment"].some((field) => !returnInputs[project.id]?.[field]) || !returnInputs[project.id]?.evidence?.trim() || !returnInputs[project.id]?.reason?.trim()} style={{ ...fieldStyle, cursor: "pointer" }}>Registrar devolución a ejecución</button>
        </div>
        {(project.events || []).map((event, index) => <p key={`${event.event_type}-${index}`} style={{ color: "#aab2c5" }}>Historial: {event.previous_status} → {event.new_status} · {event.actor_name} · {new Date(event.occurred_at).toLocaleString()} · {event.reason}</p>)}
      </article>)}
    </section>}
    {canClassifyTasks && <section style={{ marginTop: 28 }}>
      <h2>Clasificación de tareas para el cierre ordinario</h2>
      <p style={{ color: "#aab2c5" }}>L3 clasifica expresamente cada tarea dentro del alcance vigente. Las modificaciones conservan sus antecedentes.</p>
      {projects.filter((project) => ["En ejecución", "En validación técnica"].includes(project.status) && scopedProjects.has(project.id)).map((project) => {
        const context = deliveryContexts[project.id];
        return <article key={project.id} style={{ border: "1px solid #34394a", borderRadius: 8, padding: 16, margin: "12px 0" }}>
          <h3>{project.name}</h3>
          {!context ? <p>Cargando tareas y clasificaciones…</p> : context.tasks.length === 0 ? <p>El proyecto no tiene tareas registradas.</p> : context.tasks.map((task) => {
            const input = classificationInputs[task.task_id] || {};
            const current = task.classification_history?.find((item) => item.is_current);
            return <div key={task.task_id} style={{ borderTop: "1px solid #34394a", padding: "10px 0" }}>
              <strong>{task.title}</strong> · {task.status}{task.is_blocked ? " · Bloqueada" : ""}
              {task.classification_history?.map((item, index) => <p key={index} style={{ color: "#aab2c5", margin: "4px 0" }}>{item.is_current ? "Vigente" : "Antecedente"}: {item.is_mandatory ? "Obligatoria" : "Opcional"} · {item.actor_name} · {new Date(item.occurred_at).toLocaleString()} · {item.reason} · Alcance: {item.scope_snapshot}</p>)}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "end" }}>
                <label>Clasificación<select value={input.is_mandatory === undefined ? "" : String(input.is_mandatory)} onChange={(event) => updateClassification(task.task_id, "is_mandatory", event.target.value === "" ? undefined : event.target.value === "true")} style={fieldStyle}><option value="">Selecciona</option><option value="true">Obligatoria</option><option value="false">Opcional</option></select></label>
                <label>Justificación<input value={input.reason || ""} onChange={(event) => updateClassification(task.task_id, "reason", event.target.value)} style={fieldStyle} /></label>
                <button type="button" disabled={input.is_mandatory === undefined || !input.reason?.trim()} onClick={() => saveTaskClassification(project.id, task.task_id)} style={fieldStyle}>{current ? "Registrar modificación" : "Registrar clasificación"}</button>
              </div>
            </div>;
          })}
        </article>;
      })}
    </section>}
    {canEvaluateClosure && projects.some((project) => project.status === "En validación técnica" && scopedProjects.has(project.id)) && <section style={{ marginTop: 28 }}>
      <h2>Evaluación técnica integral</h2>
      <p style={{ color: "#aab2c5" }}>L3 evalúa el alcance completo, el cierre ordinario, las tareas y las obligaciones aplicables. Registrar la evaluación no cambia el estado del proyecto.</p>
      {projects.filter((project) => project.status === "En validación técnica" && scopedProjects.has(project.id)).map((project) => {
        const input = evaluationInputs[project.id] || {};
        const context = deliveryContexts[project.id];
        const pendingOptional = (context?.tasks || []).filter((task) => task.is_mandatory === false && task.status !== "Finalizada");
        return <article key={project.id} style={{ border: "1px solid #34394a", borderRadius: 8, padding: 16, margin: "12px 0" }}>
          <h3>{project.name}</h3><p>Alcance evaluado: {context?.scope_snapshot || project.scope || "No disponible"}</p>
          <div style={{ display: "grid", gap: 8, maxWidth: 760 }}>
            <label style={{ display: "flex", gap: 8 }}><input type="checkbox" checked={input.satisfactory || false} onChange={(event) => updateEvaluation(project.id, "satisfactory", event.target.checked)} />La validación integral es satisfactoria con evidencia suficiente</label>
            <label>Estado de habilitación técnica<select value={input.technical_enablement_status || "En revisión"} onChange={(event) => updateEvaluation(project.id, "technical_enablement_status", event.target.value)} style={fieldStyle}><option>Vigente</option><option>En revisión</option><option>No vigente</option></select></label>
            <label style={{ display: "flex", gap: 8 }}><input type="checkbox" checked={input.ordinary_close_valid || false} onChange={(event) => updateEvaluation(project.id, "ordinary_close_valid", event.target.checked)} />El cierre técnico ordinario es válido</label>
            <label style={{ display: "flex", gap: 8 }}><input type="checkbox" checked={input.obligations_compatible || false} onChange={(event) => updateEvaluation(project.id, "obligations_compatible", event.target.checked)} />Las obligaciones evaluadas son compatibles con el cierre y la habilitación</label>
            <label>Versiones técnicas verificadas, una por línea<textarea value={input.validated_versions_text || ""} onChange={(event) => updateEvaluation(project.id, "validated_versions_text", event.target.value)} style={fieldStyle} /></label>
            {[["result_summary", "Resultado y requisitos evaluados"], ["evidence", "Evidencia de validación integral"], ["ordinary_close_evidence", "Fundamento del cierre ordinario"], ["obligations_assessment", "Obligaciones pendientes y seguimiento"]].map(([field, label]) => <label key={field} style={{ display: "grid", gap: 4 }}>{label}<textarea required value={input[field] || ""} onChange={(event) => updateEvaluation(project.id, field, event.target.value)} style={fieldStyle} /></label>)}
            {pendingOptional.map((task) => <div key={task.task_id} style={{ borderTop: "1px solid #34394a", paddingTop: 8 }}><strong>Tarea opcional pendiente: {task.title}</strong>
              <label style={{ display: "grid", gap: 4 }}>Evaluación de impacto<textarea required value={input.optionalTasks?.[task.task_id]?.impact_assessment || ""} onChange={(event) => updateOptionalAssessment(project.id, task.task_id, "impact_assessment", event.target.value)} style={fieldStyle} /></label>
              <label style={{ display: "grid", gap: 4 }}>Evidencia<textarea required value={input.optionalTasks?.[task.task_id]?.evidence || ""} onChange={(event) => updateOptionalAssessment(project.id, task.task_id, "evidence", event.target.value)} style={fieldStyle} /></label>
            </div>)}
            <button type="button" onClick={() => saveTechnicalEvaluation(project.id)} disabled={["result_summary", "evidence", "ordinary_close_evidence", "obligations_assessment"].some((field) => !input[field]?.trim()) || pendingOptional.some((task) => !input.optionalTasks?.[task.task_id]?.impact_assessment?.trim() || !input.optionalTasks?.[task.task_id]?.evidence?.trim())} style={fieldStyle}>Registrar evaluación técnica</button>
          </div>
          {(context?.technical_evaluations || []).filter((item) => item.validation_event_id === context.current_validation_event_id).map((item) => <p key={item.id} style={{ color: "#aab2c5" }}>Evaluación #{item.id} · {item.satisfactory ? "satisfactoria" : "no satisfactoria"} · habilitación técnica {item.technical_enablement_status} · cierre ordinario {item.ordinary_close_valid ? "válido" : "no acreditado"} · {item.actor_name} · {new Date(item.evaluated_at).toLocaleString()}</p>)}
        </article>;
      })}
    </section>}
    {canMarkReady && projects.some((project) => project.status === "En validación técnica" && scopedProjects.has(project.id)) && <section style={{ marginTop: 28 }}>
      <h2>Preparación para entrega</h2>
      <p style={{ color: "#aab2c5" }}>L3 autoriza el cierre ordinario si la evaluación técnica, las tareas y la habilitación comercial específica están vigentes y corresponden al alcance.</p>
      {projects.filter((project) => project.status === "En validación técnica" && scopedProjects.has(project.id)).map((project) => {
        const input = readyInputs[project.id] || {};
        const context = deliveryContexts[project.id];
        const now = Date.now();
        const candidates = (deliveryAuthorizations[project.id] || []).filter((item) => !item.events?.length && item.conditions_accredited && new Date(item.effective_at).getTime() <= now && (!item.expires_at || new Date(item.expires_at).getTime() > now));
        return <article key={project.id} style={{ border: "1px solid #34394a", borderRadius: 8, padding: 16, margin: "12px 0" }}><h3>{project.name}</h3>
          <label>Habilitación L2<select required value={input.delivery_authorization_id || ""} onChange={(event) => updateReady(project.id, "delivery_authorization_id", event.target.value)} style={fieldStyle}><option value="">Seleccionar</option>{candidates.map((item) => <option key={item.id} value={item.id}>#{item.id} · {item.authorized_scope} · {item.evidence_reference}</option>)}</select></label>
          {candidates.length === 0 && <p>No hay habilitación de entrega vigente disponible.</p>}
          <label>Motivo de cierre ordinario<textarea required value={input.reason || ""} onChange={(event) => updateReady(project.id, "reason", event.target.value)} style={fieldStyle} /></label>
          <button type="button" disabled={!input.delivery_authorization_id || !input.reason?.trim()} onClick={() => submitReadyForDelivery(project.id)} style={fieldStyle}>Registrar Listo para entrega</button>
        </article>;
      })}
    </section>}
    {canAuthorizeDelivery && <section style={{ marginTop: 28 }}>
      <h2>Habilitación comercial para preparar la entrega</h2>
      <p style={{ color: "#aab2c5" }}>L2 registra la autorización específica y su alcance. No cambia el estado del proyecto ni formaliza la entrega.</p>
      {projects.map((project) => {
        const rows = deliveryAuthorizations[project.id] || [];
        const startRows = commercialAuthorizations[project.id] || [];
        const input = deliveryAuthorizationInputs[project.id] || {};
        const replaceable = rows.filter((item) => !item.events?.length);
        return <article key={project.id} style={{ border: "1px solid #34394a", borderRadius: 8, padding: 16, margin: "12px 0" }}>
          <h3>{project.name}</h3>
          {rows.map((item) => <div key={item.id} style={{ color: "#aab2c5", marginBottom: 8 }}>
            <p>#{item.id} · {item.authorized_scope} · L2 {item.authorized_by_name} · efectiva {new Date(item.effective_at).toLocaleString()}{item.expires_at ? ` · vence ${new Date(item.expires_at).toLocaleString()}` : " · sin vencimiento específico"}</p>
            <p>Condiciones: {item.effectivity_conditions} · acreditadas: {item.conditions_accredited ? "sí" : "no"} · evidencia: {item.evidence_reference}</p>
            {item.events?.map((event, index) => <p key={index}>{event.event_type} por {event.actor_name} · {event.reason}</p>)}
            {!item.events?.length && <button type="button" onClick={() => withdrawDelivery(project.id, item.id)} style={fieldStyle}>Retirar habilitación de entrega</button>}
          </div>)}
          <form onSubmit={(event) => { event.preventDefault(); saveDeliveryAuthorization(project.id); }} style={{ display: "grid", gap: 8, maxWidth: 700 }}>
            <label>Alcance autorizado<input required value={input.authorized_scope ?? project.scope ?? startRows[0]?.authorized_scope ?? ""} onChange={(event) => updateDeliveryAuthorization(project.id, "authorized_scope", event.target.value)} style={fieldStyle} /></label>
            <label>Condiciones de efectividad<textarea required value={input.effectivity_conditions || ""} onChange={(event) => updateDeliveryAuthorization(project.id, "effectivity_conditions", event.target.value)} style={fieldStyle} /></label>
            <label style={{ display: "flex", gap: 8 }}><input type="checkbox" checked={input.conditions_accredited || false} onChange={(event) => updateDeliveryAuthorization(project.id, "conditions_accredited", event.target.checked)} />Acredito las condiciones de efectividad de esta habilitación</label>
            <label>Referencia comercial o documental<input required value={input.evidence_reference || ""} onChange={(event) => updateDeliveryAuthorization(project.id, "evidence_reference", event.target.value)} style={fieldStyle} /></label>
            <label>Efectiva desde<input type="datetime-local" required value={input.effective_at || localDateTime()} onChange={(event) => updateDeliveryAuthorization(project.id, "effective_at", event.target.value)} style={fieldStyle} /></label>
            <label>Vencimiento específico documentado (opcional)<input type="datetime-local" value={input.expires_at || ""} onChange={(event) => updateDeliveryAuthorization(project.id, "expires_at", event.target.value)} style={fieldStyle} /></label>
            {replaceable.length > 0 && <label>Sustituir habilitación<select value={input.replaces_authorization_id || ""} onChange={(event) => updateDeliveryAuthorization(project.id, "replaces_authorization_id", event.target.value)} style={fieldStyle}><option value="">Nueva habilitación independiente</option>{replaceable.map((item) => <option key={item.id} value={item.id}>#{item.id} · {item.authorized_scope}</option>)}</select></label>}
            {input.replaces_authorization_id && <label>Motivo de sustitución<input required value={input.replacement_reason || ""} onChange={(event) => updateDeliveryAuthorization(project.id, "replacement_reason", event.target.value)} style={fieldStyle} /></label>}
            <button type="submit" disabled={!input.conditions_accredited} style={fieldStyle}>Registrar habilitación de entrega</button>
          </form>
        </article>;
      })}
    </section>}
    {(canRecordDelivery || canReviewDeliveryVersion || canFormalizeDelivery) && <section style={{ marginTop: 28 }}>
      <h2>Formalización de entrega</h2>
      <p style={{ color: "#aab2c5" }}>L2 registra la transferencia efectiva y formaliza cuando las constancias cubren el alcance. La recepción, aceptación y pago permanecen independientes.</p>
      {projects.filter((project) => ["En ejecución", "En validación técnica", "Listo para entrega"].includes(project.status) && (user?.role === "L2" || scopedProjects.has(project.id))).map((project) => {
        const rows = projectDeliveries[project.id] || [];
        const input = deliveryInputs[project.id] || {};
        const formInput = formalizationInputs[project.id] || {};
        const auths = (deliveryAuthorizations[project.id] || []).filter((item) => item.conditions_accredited && new Date(item.effective_at).getTime() <= Date.now() && (!item.expires_at || new Date(item.expires_at).getTime() > Date.now()) && !item.events?.length);
        return <article key={project.id} style={{ border: "1px solid #34394a", borderRadius: 8, padding: 16, margin: "12px 0" }}>
          <h3>{project.name} · {project.status}</h3>
          {canRecordDelivery && <div style={{ display: "grid", gap: 8, maxWidth: 760 }}>
            <h4>Registrar transferencia efectiva (L2)</h4>
            {auths.length === 0 ? <p>No hay habilitación de preparación vigente.</p> : <>
              <label>Habilitación<select value={input.preparation_authorization_id || ""} onChange={(e) => updateDelivery(project.id, "preparation_authorization_id", e.target.value)} style={fieldStyle}><option value="">Seleccionar</option>{auths.map((a) => <option key={a.id} value={a.id}>#{a.id} · {a.authorized_scope}</option>)}</select></label>
              <label>Tipo<select value={input.delivery_type || "parcial"} onChange={(e) => updateDelivery(project.id, "delivery_type", e.target.value)} style={fieldStyle}><option value="parcial">Parcial</option><option value="integral" disabled={project.status !== "Listo para entrega"}>Integral</option></select></label>
              <label>Alcance transferido<textarea value={input.scope || project.scope || ""} onChange={(e) => updateDelivery(project.id, "scope", e.target.value)} style={fieldStyle} /></label>
              <label><input type="checkbox" checked={input.scope_within_authorization || false} onChange={(e) => updateDelivery(project.id, "scope_within_authorization", e.target.checked)} />Confirmo que el alcance transferido está dentro de la habilitación L2</label>
              <label>Versión<input value={input.version_reference || ""} onChange={(e) => updateDelivery(project.id, "version_reference", e.target.value)} style={fieldStyle} /></label>
              <label>Destinatario<input value={input.recipient || ""} onChange={(e) => updateDelivery(project.id, "recipient", e.target.value)} style={fieldStyle} /></label>
              <label>Método de transferencia<input value={input.delivery_method || ""} onChange={(e) => updateDelivery(project.id, "delivery_method", e.target.value)} style={fieldStyle} /></label>
              <label>Responsable de ejecutar la transferencia<input value={input.performed_by || ""} onChange={(e) => updateDelivery(project.id, "performed_by", e.target.value)} style={fieldStyle} /></label>
              <label>Referencia de evidencia<input value={input.evidence_reference || ""} onChange={(e) => updateDelivery(project.id, "evidence_reference", e.target.value)} style={fieldStyle} /></label>
              <label>Fecha efectiva<input type="datetime-local" value={input.occurred_at || localDateTime(0)} onChange={(e) => updateDelivery(project.id, "occurred_at", e.target.value)} style={fieldStyle} /></label>
              <button type="button" disabled={!input.preparation_authorization_id || !input.scope?.trim() || !input.scope_within_authorization || !input.version_reference?.trim() || !input.recipient?.trim() || !input.delivery_method?.trim() || !input.performed_by?.trim() || !input.evidence_reference?.trim()} onClick={() => submitDelivery(project.id)} style={fieldStyle}>Registrar constancia</button>
            </>}
          </div>}
          {canReviewDeliveryVersion && project.status === "Listo para entrega" && <div style={{ display: "grid", gap: 6, maxWidth: 700, margin: "14px 0" }}>
            <h4>Habilitar versión para entrega (L3)</h4>
            <p style={{ color: "#aab2c5" }}>Registra la revisión técnica antes de la fecha efectiva de transferencia. Las versiones ya cubiertas por la evaluación integral no requieren otra revisión.</p>
            <label>Versión<input value={deliveryReviewInputs[project.id]?.version_reference || ""} onChange={(e) => updateDeliveryReview(project.id, "version_reference", e.target.value)} style={fieldStyle} /></label>
            <label><input type="checkbox" checked={deliveryReviewInputs[project.id]?.satisfactory || false} onChange={(e) => updateDeliveryReview(project.id, "satisfactory", e.target.checked)} />Resultado técnico satisfactorio</label>
            <label>Estado técnico<select value={deliveryReviewInputs[project.id]?.technical_enablement_status || "Vigente"} onChange={(e) => updateDeliveryReview(project.id, "technical_enablement_status", e.target.value)} style={fieldStyle}><option>Vigente</option><option>En revisión</option><option>No vigente</option></select></label>
            <label>Resultado<input value={deliveryReviewInputs[project.id]?.result_summary || ""} onChange={(e) => updateDeliveryReview(project.id, "result_summary", e.target.value)} style={fieldStyle} /></label>
            <label>Evidencia<input value={deliveryReviewInputs[project.id]?.evidence || ""} onChange={(e) => updateDeliveryReview(project.id, "evidence", e.target.value)} style={fieldStyle} /></label>
            <button type="button" disabled={!deliveryReviewInputs[project.id]?.version_reference?.trim() || !deliveryReviewInputs[project.id]?.result_summary?.trim() || !deliveryReviewInputs[project.id]?.evidence?.trim()} onClick={() => submitDeliveryReview(project.id)} style={fieldStyle}>Registrar revisión técnica previa</button>
          </div>}
          <h4>Constancias e historial</h4>
          {rows.length === 0 ? <p>Sin constancias registradas.</p> : rows.map((delivery) => {
            return <div key={delivery.id} style={{ borderTop: "1px solid #34394a", padding: "8px 0" }}>
              <p>#{delivery.id} {delivery.delivery_type} · {delivery.scope} · versión {delivery.version_reference} · destinatario {delivery.recipient} · transferencia por {delivery.performed_by} mediante {delivery.delivery_method} · {new Date(delivery.occurred_at).toLocaleString()} · evidencia {delivery.evidence_reference} · L2 {delivery.recorded_by_name}{delivery.formalized ? " · formalizada" : ""}</p>
              {delivery.technical_reviews.map((review, index) => <p key={index}>Revisión L3 de {review.version_reference} {review.actor_name}: {review.satisfactory ? "satisfactoria" : "no satisfactoria"}, habilitación {review.technical_enablement_status} · {review.evidence}</p>)}
            </div>;
          })}
          {canFormalizeDelivery && project.status === "Listo para entrega" && rows.some((item) => !item.formalized) && <div style={{ display: "grid", gap: 8, maxWidth: 760 }}>
            <h4>Formalizar alcance integral (L2)</h4>
            {rows.filter((item) => !item.formalized).map((item) => <label key={item.id}><input type="checkbox" checked={(formInput.delivery_ids || []).includes(item.id)} onChange={(e) => updateFormalization(project.id, "delivery_ids", e.target.checked ? [...(formInput.delivery_ids || []), item.id] : (formInput.delivery_ids || []).filter((id) => id !== item.id))} />Entrega #{item.id} · {item.delivery_type} · {item.scope}</label>)}
            <label><input type="checkbox" checked={formInput.integral_coverage_confirmed || false} onChange={(e) => updateFormalization(project.id, "integral_coverage_confirmed", e.target.checked)} />Confirmo que las entregas seleccionadas cubren integralmente el alcance vigente</label>
            <label>Evidencia de cobertura<input value={formInput.coverage_evidence || ""} onChange={(e) => updateFormalization(project.id, "coverage_evidence", e.target.value)} style={fieldStyle} /></label>
            <label>Motivo<input value={formInput.reason || ""} onChange={(e) => updateFormalization(project.id, "reason", e.target.value)} style={fieldStyle} /></label>
            <button type="button" disabled={!formInput.delivery_ids?.length || !formInput.integral_coverage_confirmed || !formInput.coverage_evidence?.trim() || !formInput.reason?.trim()} onClick={() => submitFormalization(project.id)} style={fieldStyle}>Formalizar entrega</button>
          </div>}
        </article>;
      })}
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
