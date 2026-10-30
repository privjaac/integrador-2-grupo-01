import { useCallback, useEffect, useState } from "react";
import { getClients } from "../../api/clients";
import ProjectServicesPanel from "./ProjectServicesPanel";
import ProjectCancellationPanel from "./ProjectCancellationPanel";
import ProjectSubstitutionsPanel from "./ProjectSubstitutionsPanel";
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
import "./ProjectsPage.css";

const fieldStyle = {
  boxSizing: "border-box",
  padding: "10px 12px",
  background: "#0b0d1a",
  color: "white",
  border: "1px solid rgba(63,229,229,.28)",
  borderRadius: 6,
  font: "inherit",
};

const authorizationEventLabels = { retirada: "Retirada por L2", sustituida: "Sustituida por otra habilitación" };

function getAuthorizationStatus(item, conditionsField = "conditions_accredited") {
  const event = item.events?.[0];
  if (event?.event_type === "retirada") return "Retirada";
  if (event?.event_type === "sustituida") return "Sustituida";
  if (!item[conditionsField]) return "Condiciones sin acreditar";
  const now = Date.now();
  if (new Date(item.effective_at).getTime() > now) return "Aún no efectiva";
  if (item.expires_at && new Date(item.expires_at).getTime() <= now) return "Vencida";
  return "Vigente";
}

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
  const canRequestCancellation = can(user, "projects", "requestProjectCancellation");
  const canEvaluateCancellation = can(user, "projects", "evaluateProjectCancellation");
  const canResolveCancellation = can(user, "projects", "resolveProjectCancellation");
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
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

  const refresh = useCallback(async () => {
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
      const scopedIds = user?.role === "L3" ? new Set((context.projects || []).map((item) => item.id)) : null;
      const initialProject = projectRows.find((project) => scopedIds?.has(project.id)) || projectRows[0];
      setSelectedProjectId((current) => {
        const currentIsAllowed = projectRows.some((project) => String(project.id) === current)
          && (user?.role !== "L3" || scopedIds.has(Number(current)));
        return currentIsAllowed ? current : String(initialProject?.id || "");
      });
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
  }, [canCreate, user?.role]);

  useEffect(() => { refresh(); }, [refresh]);

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
  const cancellationProjects = canRequestCancellation || canResolveCancellation
    ? projects
    : canEvaluateCancellation ? projects.filter((project) => scopedProjects.has(project.id)) : [];
  const selectedProject = projects.find((project) => String(project.id) === selectedProjectId) || null;
  const workspaceProjects = selectedProject ? [selectedProject] : [];
  const workspaceCancellationProjects = cancellationProjects.filter((project) => project.id === selectedProject?.id);

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

  return <section className="projects-page" style={{ color: "white", margin: "0 auto" }}>
    <header style={{ marginBottom: 20 }}>
      <h1 style={{ marginBottom: 6 }}>Proyectos</h1>
      <p style={{ color: "#aab2c5", margin: 0 }}>Los proyectos nuevos se crean en estado Planificado. Las acciones disponibles dependen del rol, la coordinación y el estado de cada proyecto.</p>
    </header>
    {error && <p role="alert" style={{ color: "#ff718b" }}>{String(error)}</p>}
    {canCreate && <details style={{ margin: "0 0 24px", padding: "14px 16px", background: "#111427", border: "1px solid rgba(63,229,229,.16)", borderRadius: 8 }}>
      <summary style={{ color: "#3fe5e5", cursor: "pointer", fontWeight: 600 }}>Crear proyecto</summary>
      <form onSubmit={submit} style={{ display: "grid", gap: 12, marginTop: 16, maxWidth: 700 }}>
        <h2 style={{ margin: 0 }}>Datos del nuevo proyecto</h2>
        <label>Cliente<select required value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} style={fieldStyle}>
          <option value="">Selecciona un cliente</option>{clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
        </select></label>
        <label>Nombre del proyecto<input required maxLength={200} placeholder="Nombre del proyecto" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={fieldStyle} /></label>
        <label>Objetivo (opcional)<textarea placeholder="Objetivo (opcional)" value={form.objective} onChange={(e) => setForm({ ...form, objective: e.target.value })} style={fieldStyle} /></label>
        <label>Alcance (opcional)<textarea placeholder="Alcance (opcional)" value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })} style={fieldStyle} /></label>
        <button type="submit" style={{ ...fieldStyle, cursor: "pointer" }}>Crear proyecto</button>
      </form>
    </details>}
    <div style={{ marginBottom: 12 }}>
      <h2 style={{ margin: "0 0 4px" }}>Proyectos registrados</h2>
      {!loading && <p style={{ color: "#aab2c5", margin: 0 }}>{projects.length} proyecto{projects.length === 1 ? "" : "s"} en el ámbito disponible</p>}
    </div>
    {loading ? <p>Cargando…</p> : projects.length === 0 ? <p>No hay proyectos registrados.</p> : <div className="project-workspace-table-wrap"><table className="project-workspace-table" aria-label="Proyectos registrados"><thead><tr>{["Nombre", "Cliente", "Estado", "Objetivo", "Alcance", "Expediente"].map((label) => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{projects.map((project) => <tr key={project.id} aria-current={selectedProject?.id === project.id ? "true" : undefined} style={{ background: "#111427" }}>
      {[project.name, project.client_name, project.status, project.objective || "—", project.scope || "—"].map((value, index) => <td key={index} style={{ maxWidth: index >= 3 ? 280 : undefined, whiteSpace: index === 2 ? "nowrap" : "normal", color: index === 2 ? "#3fe5e5" : "#eef1f7" }}>{value}</td>)}
      <td><button type="button" aria-pressed={selectedProject?.id === project.id} onClick={() => setSelectedProjectId(String(project.id))} style={{ ...fieldStyle, padding: "7px 10px", cursor: "pointer" }}>{selectedProject?.id === project.id ? "Abierto" : "Abrir expediente"}</button></td>
    </tr>)}</tbody></table></div>}
    <div className="project-workspace-toolbar">
      <div className="project-workspace-selected"><span>Proyecto en foco</span><strong>{selectedProject?.name || "Selecciona un expediente de la tabla"}</strong></div>
      <p className="project-workspace-hint">El expediente reúne las actuaciones, autorizaciones y antecedentes del proyecto. Usa «Abrir expediente» en la tabla para cambiar de proyecto.</p>
    </div>
    {selectedProject && <article className="project-summary-card" aria-label="Resumen del proyecto seleccionado">
      <div className="project-summary-heading"><h2>{selectedProject.name}</h2><span className="project-summary-status">{selectedProject.status}</span></div>
      <dl className="project-summary-facts"><div><dt>Cliente</dt><dd>{selectedProject.client_name || "—"}</dd></div><div><dt>Objetivo</dt><dd>{selectedProject.objective || "—"}</dd></div><div><dt>Alcance vigente</dt><dd>{selectedProject.scope || "—"}</dd></div></dl>
    </article>}
    {workspaceCancellationProjects.map((project) => <details className="project-area" key={`cancellation-area-${project.id}`}>
      <summary>Actuaciones excepcionales · cancelaciones, reanudaciones e historial</summary>
      <div className="project-area-content"><ProjectCancellationPanel project={project} user={user} canRequest={canRequestCancellation} canEvaluate={canEvaluateCancellation} canResolve={canResolveCancellation} /></div>
    </details>)}
    {user?.role === "L3" && workspaceProjects.filter((project) => scopedProjects.has(project.id)).map((project) => <details className="project-area" key={`substitutions-area-${project.id}`}>
      <summary>Coordinación técnica · suplencias</summary><div className="project-area-content"><ProjectSubstitutionsPanel project={project} taskContext={taskContext} /></div>
    </details>)}
    {user?.role === "L2" && workspaceProjects.map((project) => {
      const assigned = taskContext.coordination_assignments?.filter((item) => item.project_id === project.id) || [];
      return <details className="project-area" key={`coordination-area-${project.id}`}>
        <summary>Coordinación técnica · responsables L3</summary>
        <div className="project-area-content">
          <div className="project-operation-card project-coordination-panel">
            <p className="project-muted">{assigned.length ? "Coordinaciones vigentes del proyecto seleccionado" : "Este proyecto no tiene coordinación L3 vigente."}</p>
            {assigned.map((item) => <div className="project-coordination-row" key={item.coordinator_id}>
              <span>{item.coordinator_name}</span>
              {can(user, "tasks", "withdrawCoordination") && item.can_remove && <button type="button" onClick={() => unassignCoordinator(project.id, item.coordinator_id)} style={{ ...fieldStyle, padding: "5px 8px", cursor: "pointer" }}>Retirar coordinación</button>}
            </div>)}
            {can(user, "tasks", "designate") && <div className="project-coordination-controls">
              <label htmlFor={`project-coordinator-${project.id}`}>Designar coordinación L3</label>
              <select id={`project-coordinator-${project.id}`} aria-label={`Coordinación de ${project.name}`} value={coordinatorSelection[project.id] || ""} onChange={(event) => setCoordinatorSelection({ ...coordinatorSelection, [project.id]: event.target.value })} style={fieldStyle}>
                <option value="">Seleccionar L3</option>{taskContext.coordinators?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
              <button type="button" disabled={!coordinatorSelection[project.id]} onClick={() => assignCoordinator(project.id)} style={{ ...fieldStyle, cursor: "pointer" }}>Designar coordinación</button>
            </div>}
          </div>
        </div>
      </details>;
    })}
    {can(user, "projects", "associateContractedServices") && workspaceProjects.filter((project) => scopedProjects.has(project.id)).map((project) => <details className="project-area" key={`services-area-${project.id}`}>
      <summary>Coordinación técnica · servicios vinculados</summary><div className="project-area-content"><ProjectServicesPanel project={project} canManage={project.status !== "Entregado"} /></div>
    </details>)}
    {canStartValidation && workspaceProjects.some((project) => project.status === "En ejecución" && scopedProjects.has(project.id)) && <details className="project-area">
      <summary>Validación técnica · registrar ingreso</summary><div className="project-area-content">
      <p style={{ color: "#aab2c5" }}>L3 evalúa preparación suficiente para comenzar una validación significativa. Este acto no declara resultados aprobados ni finaliza el proyecto.</p>
      {workspaceProjects.filter((project) => project.status === "En ejecución" && scopedProjects.has(project.id)).map((project) => <article className="project-operation-card" key={project.id}>
        <h3>{project.name}</h3>
        <div style={{ display: "grid", gap: 8, maxWidth: 700 }}>{validationFields.map(([field, label]) => field === "evidence" || field === "reason" ? <label key={field} style={{ display: "grid", gap: 4 }}>{label}<textarea required value={validationInputs[project.id]?.[field] || ""} onChange={(event) => updateValidation(project.id, field, event.target.value)} style={fieldStyle} /></label> : <label key={field} style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" checked={validationInputs[project.id]?.[field] || false} onChange={(event) => updateValidation(project.id, field, event.target.checked)} />{label}</label>)}
          <button type="button" onClick={() => submitValidation(project.id)} disabled={validationFields.some(([field]) => !validationInputs[project.id]?.[field]?.trim())} style={{ ...fieldStyle, cursor: "pointer" }}>Registrar ingreso a validación técnica</button>
        </div>
        {(project.events || []).map((event, index) => <p key={`${event.event_type}-${index}`} style={{ color: "#aab2c5" }}>Historial: {event.previous_status} → {event.new_status} · {event.actor_name} · {new Date(event.occurred_at).toLocaleString()} · {event.reason}</p>)}
      </article>)}
    </div></details>}
    {canReturnToExecution && workspaceProjects.some((project) => project.status === "En validación técnica" && scopedProjects.has(project.id)) && <details className="project-area">
      <summary>Validación técnica · devolución a ejecución</summary><div className="project-area-content">
      <p style={{ color: "#aab2c5" }}>L3 puede devolver el proyecto cuando el trabajo adicional sea necesario para la suficiencia o continuidad de la validación y permanezca dentro del compromiso vigente.</p>
      {workspaceProjects.filter((project) => project.status === "En validación técnica" && scopedProjects.has(project.id)).map((project) => <article className="project-operation-card" key={project.id}>
        <h3>{project.name}</h3>
        <div style={{ display: "grid", gap: 8, maxWidth: 700 }}>
          {[["additional_execution_required", "Se requiere trabajo adicional"], ["materially_affects_validation", "Afecta materialmente la suficiencia o continuidad de la validación"], ["within_current_commitment", "El trabajo permanece dentro del compromiso vigente"]].map(([field, label]) => <label key={field} style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" checked={returnInputs[project.id]?.[field] || false} onChange={(event) => updateReturn(project.id, field, event.target.checked)} />{label}</label>)}
          <label style={{ display: "grid", gap: 4 }}>Evidencia<textarea required value={returnInputs[project.id]?.evidence || ""} onChange={(event) => updateReturn(project.id, "evidence", event.target.value)} style={fieldStyle} /></label>
          <label style={{ display: "grid", gap: 4 }}>Motivo<textarea required value={returnInputs[project.id]?.reason || ""} onChange={(event) => updateReturn(project.id, "reason", event.target.value)} style={fieldStyle} /></label>
          <button type="button" onClick={() => submitReturn(project.id)} disabled={["additional_execution_required", "materially_affects_validation", "within_current_commitment"].some((field) => !returnInputs[project.id]?.[field]) || !returnInputs[project.id]?.evidence?.trim() || !returnInputs[project.id]?.reason?.trim()} style={{ ...fieldStyle, cursor: "pointer" }}>Registrar devolución a ejecución</button>
        </div>
        {(project.events || []).map((event, index) => <p key={`${event.event_type}-${index}`} style={{ color: "#aab2c5" }}>Historial: {event.previous_status} → {event.new_status} · {event.actor_name} · {new Date(event.occurred_at).toLocaleString()} · {event.reason}</p>)}
      </article>)}
    </div></details>}
    {canClassifyTasks && workspaceProjects.some((project) => ["En ejecución", "En validación técnica"].includes(project.status) && scopedProjects.has(project.id)) && <details className="project-area">
      <summary>Validación técnica · clasificación de tareas</summary><div className="project-area-content">
      <p style={{ color: "#aab2c5" }}>L3 clasifica expresamente cada tarea dentro del alcance vigente. Las modificaciones conservan sus antecedentes.</p>
      {workspaceProjects.filter((project) => ["En ejecución", "En validación técnica"].includes(project.status) && scopedProjects.has(project.id)).map((project) => {
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
    </div></details>}
    {canEvaluateClosure && workspaceProjects.some((project) => project.status === "En validación técnica" && scopedProjects.has(project.id)) && <details className="project-area">
      <summary>Validación técnica · evaluación integral</summary><div className="project-area-content">
      <p style={{ color: "#aab2c5" }}>L3 evalúa el alcance completo, el cierre ordinario, las tareas y las obligaciones aplicables. Registrar la evaluación no cambia el estado del proyecto.</p>
      {workspaceProjects.filter((project) => project.status === "En validación técnica" && scopedProjects.has(project.id)).map((project) => {
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
    </div></details>}
    {canMarkReady && workspaceProjects.some((project) => project.status === "En validación técnica" && scopedProjects.has(project.id)) && <details className="project-area">
      <summary>Entrega · preparación</summary><div className="project-area-content">
      <p style={{ color: "#aab2c5" }}>L3 autoriza el cierre ordinario si la evaluación técnica, las tareas y la habilitación comercial específica están vigentes y corresponden al alcance.</p>
      {workspaceProjects.filter((project) => project.status === "En validación técnica" && scopedProjects.has(project.id)).map((project) => {
        const input = readyInputs[project.id] || {};
        const now = Date.now();
        const candidates = (deliveryAuthorizations[project.id] || []).filter((item) => !item.events?.length && item.conditions_accredited && new Date(item.effective_at).getTime() <= now && (!item.expires_at || new Date(item.expires_at).getTime() > now));
        return <article key={project.id} style={{ border: "1px solid #34394a", borderRadius: 8, padding: 16, margin: "12px 0" }}><h3>{project.name}</h3>
          <label>Habilitación L2<select required value={input.delivery_authorization_id || ""} onChange={(event) => updateReady(project.id, "delivery_authorization_id", event.target.value)} style={fieldStyle}><option value="">Seleccionar</option>{candidates.map((item) => <option key={item.id} value={item.id}>#{item.id} · {item.authorized_scope} · {item.evidence_reference}</option>)}</select></label>
          {candidates.length === 0 && <p>No hay habilitación de entrega vigente disponible.</p>}
          <label>Motivo de cierre ordinario<textarea required value={input.reason || ""} onChange={(event) => updateReady(project.id, "reason", event.target.value)} style={fieldStyle} /></label>
          <button type="button" disabled={!input.delivery_authorization_id || !input.reason?.trim()} onClick={() => submitReadyForDelivery(project.id)} style={fieldStyle}>Registrar Listo para entrega</button>
        </article>;
      })}
    </div></details>}
    {canAuthorizeDelivery && <details className="project-area">
      <summary>Entrega · habilitaciones comerciales</summary><div className="project-area-content">
      <p style={{ color: "#aab2c5" }}>L2 registra la autorización específica y su alcance. No cambia el estado del proyecto ni formaliza la entrega.</p>
      {workspaceProjects.map((project) => {
        const rows = deliveryAuthorizations[project.id] || [];
        const startRows = commercialAuthorizations[project.id] || [];
        const input = deliveryAuthorizationInputs[project.id] || {};
        const replaceable = rows.filter((item) => !item.events?.length);
        return <article className="project-operation-card" key={project.id}>
          <h3>{project.name}</h3>
          {rows.map((item) => <div className="project-authorization-record" key={item.id}>
            <p>#{item.id} · {item.authorized_scope} · L2 {item.authorized_by_name} · efectiva {new Date(item.effective_at).toLocaleString()}{item.expires_at ? ` · vence ${new Date(item.expires_at).toLocaleString()}` : " · sin vencimiento específico"}</p>
            <p>Condiciones: {item.effectivity_conditions} · acreditadas: {item.conditions_accredited ? "sí" : "no"} · evidencia: {item.evidence_reference}</p>
            {item.events?.map((event, index) => <p key={index}><strong>{authorizationEventLabels[event.event_type] || event.event_type}:</strong> {event.actor_name} · {new Date(event.occurred_at).toLocaleString()} · {event.reason}</p>)}
            {!item.events?.length && <button type="button" onClick={() => withdrawDelivery(project.id, item.id)} style={fieldStyle}>Retirar habilitación de entrega</button>}
          </div>)}
          <details style={{ marginTop: 12 }}>
            <summary style={{ color: "#3fe5e5", cursor: "pointer", fontWeight: 600 }}>{rows.length ? "Registrar otra habilitación de entrega" : "Registrar habilitación de entrega"}</summary>
            <form onSubmit={(event) => { event.preventDefault(); saveDeliveryAuthorization(project.id); }} style={{ display: "grid", gap: 10, maxWidth: 760, marginTop: 12 }}>
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
          </details>
        </article>;
      })}
    </div></details>}
    {(canRecordDelivery || canReviewDeliveryVersion || canFormalizeDelivery) && <details className="project-area">
      <summary>Entrega · transferencias, constancias y formalización</summary><div className="project-area-content">
      <p style={{ color: "#aab2c5" }}>L2 registra la transferencia efectiva y formaliza cuando las constancias cubren el alcance. La recepción, aceptación y pago permanecen independientes.</p>
      {workspaceProjects.filter((project) => ["En ejecución", "En validación técnica", "Listo para entrega"].includes(project.status) && (user?.role === "L2" || scopedProjects.has(project.id))).map((project) => {
        const rows = projectDeliveries[project.id] || [];
        const input = deliveryInputs[project.id] || {};
        const formInput = formalizationInputs[project.id] || {};
        const allAuthorizations = deliveryAuthorizations[project.id] || [];
        const auths = (deliveryAuthorizations[project.id] || []).filter((item) => item.conditions_accredited && new Date(item.effective_at).getTime() <= Date.now() && (!item.expires_at || new Date(item.expires_at).getTime() > Date.now()) && !item.events?.length);
        return <article className="project-operation-card" key={project.id}>
          <h3>{project.name} · {project.status}</h3>
          <section className="project-delivery-records" aria-label="Habilitaciones y constancias registradas">
            <h4>Habilitaciones comerciales para entrega</h4>
            {allAuthorizations.length === 0 ? <p className="project-muted">No hay habilitaciones registradas.</p> : allAuthorizations.map((item) => {
              const event = item.events?.[0];
              const now = Date.now();
              const status = event?.event_type === "retirada" ? "Retirada"
                : event?.event_type === "sustituida" ? "Sustituida"
                  : !item.conditions_accredited ? "Condiciones sin acreditar"
                    : new Date(item.effective_at).getTime() > now ? "Aún no efectiva"
                      : item.expires_at && new Date(item.expires_at).getTime() <= now ? "Vencida" : "Vigente";
              return <div className="project-authorization-record" key={item.id}>
                <strong>Habilitación #{item.id} · {status}</strong>
                <p><strong>Alcance:</strong> {item.authorized_scope}</p>
                <p><strong>Condiciones:</strong> {item.effectivity_conditions}</p>
                <p><strong>Referencia:</strong> {item.evidence_reference} · <strong>Efectiva:</strong> {new Date(item.effective_at).toLocaleString()}{item.expires_at ? ` · Vence: ${new Date(item.expires_at).toLocaleString()}` : " · Sin vencimiento específico"}</p>
                <p><strong>Registrada por L2:</strong> {item.authorized_by_name} · {new Date(item.authorized_at).toLocaleString()}</p>
                {event && <p><strong>{event.event_type === "retirada" ? "Retirada" : "Sustituida"} por {event.actor_name}:</strong> {event.reason} · {new Date(event.occurred_at).toLocaleString()}</p>}
              </div>;
            })}
            <h4>Transferencias e historial</h4>
            {rows.length === 0 ? <p className="project-muted">Sin constancias de transferencia registradas.</p> : rows.map((delivery) => <div className="project-authorization-record" key={delivery.id}>
              <strong>Constancia #{delivery.id} · {delivery.delivery_type === "integral" ? "Integral" : "Parcial"} · {delivery.formalized ? "Formalizada" : "Pendiente de formalización"}</strong>
              <p><strong>Alcance transferido:</strong> {delivery.scope} · <strong>Versión:</strong> {delivery.version_reference}</p>
              <p><strong>Destinatario:</strong> {delivery.recipient} · <strong>Transferencia:</strong> {delivery.delivery_method} · <strong>Ejecutada por:</strong> {delivery.performed_by}</p>
              <p><strong>Fecha efectiva:</strong> {new Date(delivery.occurred_at).toLocaleString()} · <strong>Registrada por L2:</strong> {delivery.recorded_by_name} · <strong>Evidencia:</strong> {delivery.evidence_reference}</p>
              <p><strong>Habilitación asociada:</strong> #{delivery.preparation_authorization_id}</p>
              {delivery.technical_reviews.map((review, index) => <div className="project-delivery-review" key={`${review.version_reference}-${index}`}>
                <strong>Revisión técnica L3 · {review.version_reference}</strong>
                <p>{review.satisfactory ? "Satisfactoria" : "No satisfactoria"} · habilitación técnica: {review.technical_enablement_status} · responsable: {review.actor_name} · {new Date(review.reviewed_at).toLocaleString()}</p>
                <p><strong>Resultado:</strong> {review.result_summary} · <strong>Evidencia:</strong> {review.evidence}</p>
              </div>)}
            </div>)}
          </section>
          {canRecordDelivery && <details style={{ maxWidth: 760 }}>
            <summary style={{ color: "#3fe5e5", cursor: "pointer", fontWeight: 600 }}>Registrar transferencia efectiva (L2)</summary>
            <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
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
            </div>
          </details>}
          {canReviewDeliveryVersion && project.status === "Listo para entrega" && <details style={{ maxWidth: 760, margin: "14px 0" }}>
            <summary style={{ color: "#3fe5e5", cursor: "pointer", fontWeight: 600 }}>Habilitar versión para entrega (L3)</summary>
            <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
            <p style={{ color: "#aab2c5" }}>Registra la revisión técnica antes de la fecha efectiva de transferencia. Las versiones ya cubiertas por la evaluación integral no requieren otra revisión.</p>
            <label>Versión<input value={deliveryReviewInputs[project.id]?.version_reference || ""} onChange={(e) => updateDeliveryReview(project.id, "version_reference", e.target.value)} style={fieldStyle} /></label>
            <label><input type="checkbox" checked={deliveryReviewInputs[project.id]?.satisfactory || false} onChange={(e) => updateDeliveryReview(project.id, "satisfactory", e.target.checked)} />Resultado técnico satisfactorio</label>
            <label>Estado técnico<select value={deliveryReviewInputs[project.id]?.technical_enablement_status || "Vigente"} onChange={(e) => updateDeliveryReview(project.id, "technical_enablement_status", e.target.value)} style={fieldStyle}><option>Vigente</option><option>En revisión</option><option>No vigente</option></select></label>
            <label>Resultado<input value={deliveryReviewInputs[project.id]?.result_summary || ""} onChange={(e) => updateDeliveryReview(project.id, "result_summary", e.target.value)} style={fieldStyle} /></label>
            <label>Evidencia<input value={deliveryReviewInputs[project.id]?.evidence || ""} onChange={(e) => updateDeliveryReview(project.id, "evidence", e.target.value)} style={fieldStyle} /></label>
            <button type="button" disabled={!deliveryReviewInputs[project.id]?.version_reference?.trim() || !deliveryReviewInputs[project.id]?.result_summary?.trim() || !deliveryReviewInputs[project.id]?.evidence?.trim()} onClick={() => submitDeliveryReview(project.id)} style={fieldStyle}>Registrar revisión técnica previa</button>
            </div>
          </details>}
          {canFormalizeDelivery && project.status === "Listo para entrega" && rows.some((item) => !item.formalized) && <details style={{ maxWidth: 760 }}>
            <summary style={{ color: "#3fe5e5", cursor: "pointer", fontWeight: 600 }}>Formalizar alcance integral (L2)</summary>
            <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
            {rows.filter((item) => !item.formalized).map((item) => <label key={item.id}><input type="checkbox" checked={(formInput.delivery_ids || []).includes(item.id)} onChange={(e) => updateFormalization(project.id, "delivery_ids", e.target.checked ? [...(formInput.delivery_ids || []), item.id] : (formInput.delivery_ids || []).filter((id) => id !== item.id))} />Entrega #{item.id} · {item.delivery_type} · {item.scope}</label>)}
            <label><input type="checkbox" checked={formInput.integral_coverage_confirmed || false} onChange={(e) => updateFormalization(project.id, "integral_coverage_confirmed", e.target.checked)} />Confirmo que las entregas seleccionadas cubren integralmente el alcance vigente</label>
            <label>Evidencia de cobertura<input value={formInput.coverage_evidence || ""} onChange={(e) => updateFormalization(project.id, "coverage_evidence", e.target.value)} style={fieldStyle} /></label>
            <label>Motivo<input value={formInput.reason || ""} onChange={(e) => updateFormalization(project.id, "reason", e.target.value)} style={fieldStyle} /></label>
            <button type="button" disabled={!formInput.delivery_ids?.length || !formInput.integral_coverage_confirmed || !formInput.coverage_evidence?.trim() || !formInput.reason?.trim()} onClick={() => submitFormalization(project.id)} style={fieldStyle}>Formalizar entrega</button>
            </div>
          </details>}
        </article>;
      })}
    </div></details>}
    {canAuthorizeStart && <details className="project-area">
      <summary>Inicio · habilitaciones comerciales</summary><div className="project-area-content">
      <p style={{ color: "#aab2c5" }}>L2 registra la autorización positiva y sus referencias. Este acto no inicia automáticamente el proyecto.</p>
      {workspaceProjects.map((project) => {
        const rows = commercialAuthorizations[project.id] || [];
        const input = authorizationInputs[project.id] || {};
        const replaceable = rows.filter((item) => !item.events?.some((event) => ["retirada", "sustituida"].includes(event.event_type)));
        return <article className="project-operation-card" key={project.id}>
          <h3>{project.name}</h3>
          {rows.map((item) => <div className="project-authorization-record" key={item.id}>
            <strong>Habilitación #{item.id} · {getAuthorizationStatus(item, "start_conditions_accredited")}</strong>
            <p><strong>Alcance:</strong> {item.authorized_scope} · <strong>Registrada por L2:</strong> {item.authorized_by_name} · {new Date(item.authorized_at).toLocaleString()}</p>
            <p><strong>Efectiva:</strong> {new Date(item.effective_at).toLocaleString()}{item.expires_at ? ` · Vence ${new Date(item.expires_at).toLocaleString()}` : " · Sin vencimiento específico"}</p>
            <p>Compromiso: {item.commitment_reference} · Condiciones: {item.start_conditions} · Evidencia: {item.evidence_reference}</p>
            {item.events?.map((event, index) => <p key={index}><strong>{authorizationEventLabels[event.event_type] || event.event_type}:</strong> {event.actor_name} · {new Date(event.occurred_at).toLocaleString()} · {event.reason}</p>)}
            {!item.events?.length && <button type="button" onClick={() => withdrawAuthorization(project.id, item.id)} style={fieldStyle}>Retirar habilitación</button>}
          </div>)}
          <details style={{ marginTop: 12 }}>
            <summary style={{ color: "#3fe5e5", cursor: "pointer", fontWeight: 600 }}>{rows.length ? "Registrar otra habilitación de inicio" : "Registrar habilitación de inicio"}</summary>
            <form onSubmit={(event) => { event.preventDefault(); submitCommercialAuthorization(project.id); }} style={{ display: "grid", gap: 10, maxWidth: 760, marginTop: 12 }}>
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
          </details>
        </article>;
      })}
    </div></details>}
    {canStartProject && workspaceProjects.some((project) => (taskContext.projects || []).some((item) => item.id === project.id) && project.status === "Planificado") && <details className="project-area">
      <summary>Inicio · acción técnica L3</summary><div className="project-area-content">
      <p style={{ color: "#aab2c5" }}>L3 registra la preparación técnica inicial; la información comercial detallada permanece reservada a L2.</p>
      {workspaceProjects.filter((project) => (taskContext.projects || []).some((item) => item.id === project.id) && project.status === "Planificado").map((project) => {
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
    </div></details>}
  </section>;
}
