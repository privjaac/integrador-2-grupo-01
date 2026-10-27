import { useEffect, useMemo, useState } from "react";
import { addTeamMember, assignTask, createTask, designateCoordinator, designateLeader, getTaskContext, removeCoordinator, removeLeader, removeTeamMember, reviewTask, startTask, submitTaskReview } from "../../api/tasks";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Table from "../../components/ui/Table";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";

const blankTask = { project_id: "", title: "", description: "", status: "Pendiente", assignee_id: "" };
const eventLabels = {
  creada: "Tarea creada",
  asignada: "Tarea asignada",
  iniciada: "Ejecución iniciada",
  resultado_presentado: "Resultado presentado para revisión",
  observada: "Resultado observado",
  aprobada_revision: "Revisión aprobada",
  correccion_iniciada: "Corrección iniciada",
};

export default function TasksPage() {
  const { user } = useAuth();
  const [context, setContext] = useState({ projects: [], leaders: [], developers: [], tasks: [] });
  const [form, setForm] = useState(blankTask);
  const [designation, setDesignation] = useState({});
  const [assignment, setAssignment] = useState({});
  const [results, setResults] = useState({});
  const [reviewReasons, setReviewReasons] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const canCreate = can(user, "tasks", "create");

  async function refresh() {
    setLoading(true);
    try {
      setContext(await getTaskContext());
      setError("");
    } catch (err) {
      setError(err.userMessage || "No se pudo cargar el trabajo autorizado.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  const developersForProject = useMemo(() => {
    return context.developers.filter((person) => String(person.project_id) === String(form.project_id));
  }, [context, form.project_id]);

  async function submitTask(event) {
    event.preventDefault();
    setError("");
    try {
      await createTask({
        ...form,
        project_id: Number(form.project_id),
        assignee_id: form.status === "Asignada" ? Number(form.assignee_id) : null,
        description: form.description || null,
      });
      setForm(blankTask);
      setNotice("Tarea registrada.");
      await refresh();
    } catch (err) {
      setError(err.userMessage || "No se pudo crear la tarea.");
    }
  }

  async function submitDesignation(projectId) {
    const collaboratorId = Number(designation[projectId]);
    try {
      await designateLeader(projectId, collaboratorId);
      setDesignation((items) => ({ ...items, [projectId]: "" }));
      setNotice("Líder designado para el proyecto.");
      await refresh();
    } catch (err) {
      setError(err.userMessage || "No se pudo designar al líder.");
    }
  }

  async function submitCoordination(projectId) {
    const collaboratorId = Number(designation[projectId]);
    try {
      await designateCoordinator(projectId, collaboratorId);
      setDesignation((items) => ({ ...items, [projectId]: "" }));
      setNotice("Coordinación L3 designada para el proyecto.");
      await refresh();
    } catch (err) {
      setError(err.userMessage || "No se pudo designar la coordinación.");
    }
  }

  async function submitRemoveCoordinator(projectId, collaboratorId) {
    try {
      await removeCoordinator(projectId, collaboratorId);
      setNotice("Coordinación L3 retirada del proyecto.");
      await refresh();
    } catch (err) {
      setError(err.userMessage || "No se pudo retirar la coordinación.");
    }
  }

  async function submitMember(projectId) {
    const collaboratorId = Number(designation[projectId]);
    try {
      await addTeamMember(projectId, collaboratorId);
      setDesignation((items) => ({ ...items, [projectId]: "" }));
      setNotice("Integrante incorporado al equipo.");
      await refresh();
    } catch (err) {
      setError(err.userMessage || "No se pudo incorporar al integrante.");
    }
  }

  async function submitRemoveLeader(projectId, collaboratorId) {
    try {
      await removeLeader(projectId, collaboratorId);
      setNotice("Líder retirado del proyecto.");
      await refresh();
    } catch (err) {
      setError(err.userMessage || "No se pudo retirar al líder.");
    }
  }

  async function submitRemoveMember(projectId, collaboratorId) {
    try {
      await removeTeamMember(projectId, collaboratorId);
      setNotice("Integrante retirado del equipo.");
      await refresh();
    } catch (err) {
      setError(err.userMessage || "No se pudo retirar al integrante.");
    }
  }

  async function submitAssignment(taskId) {
    try {
      await assignTask(taskId, Number(assignment[taskId]));
      setAssignment((items) => ({ ...items, [taskId]: "" }));
      setNotice("Tarea asignada.");
      await refresh();
    } catch (err) {
      setError(err.userMessage || "No se pudo asignar la tarea.");
    }
  }

  async function startTaskAction(task) {
    try {
      await startTask(task.id);
      setNotice(task.status === "Observada" ? "Corrección iniciada." : "Ejecución iniciada.");
      await refresh();
    } catch (err) {
      setError(err.userMessage || "No se pudo iniciar la tarea.");
    }
  }

  async function submitResult(taskId) {
    setError("");
    try {
      await submitTaskReview(taskId, results[taskId]);
      setResults((items) => ({ ...items, [taskId]: "" }));
      setNotice("Resultado enviado a revisión.");
      await refresh();
    } catch (err) {
      setError(err.userMessage || "No se pudo presentar el resultado.");
    }
  }

  async function resolveReview(taskId, resolution) {
    setError("");
    try {
      await reviewTask(taskId, resolution, resolution === "Observada" ? reviewReasons[taskId] : null);
      setReviewReasons((items) => ({ ...items, [taskId]: "" }));
      setNotice(resolution === "Observada" ? "La tarea quedó observada." : "La tarea fue aprobada.");
      await refresh();
    } catch (err) {
      setError(err.userMessage || "No se pudo resolver la revisión.");
    }
  }

  const selectStyle = { background: "#1a1d30", color: "white", border: "1px solid rgba(63,229,229,0.2)", borderRadius: 4, padding: "8px 10px", width: "100%" };
  const optionsFor = (items) => items.map((item) => ({ value: item.id, label: item.name }));

  return <section style={{ color: "white", maxWidth: 1100, margin: "0 auto" }}>
    <h1>Tareas</h1>
    <p style={{ color: "#aab2c5" }}>{user?.role === "L2" ? "Designa y retira coordinaciones L3 para proyectos; la consulta y operación de tareas corresponde a los niveles autorizados." : "Trabajo disponible según la coordinación, responsabilidad y asignaciones vigentes."}</p>
    {error && <p role="alert" style={{ color: "#ff718b" }}>{String(error)}</p>}
    {notice && <p role="status" style={{ color: "#3fe5e5" }}>{notice}</p>}

    {canCreate && <form onSubmit={submitTask} style={{ display: "grid", gap: 12, margin: "24px 0", maxWidth: 650 }}>
      <h2>Crear tarea</h2>
      <Input label="Proyecto" name="project_id" type="select" value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value, assignee_id: "" })} required options={optionsFor(context.projects)} />
      <Input label="Título" name="title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required maxLength={200} />
      <Input label="Descripción (opcional)" name="description" type="textarea" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
      {user?.role === "L4" && <Input label="Estado inicial" name="status" type="select" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value, assignee_id: "" })} options={[{ value: "Pendiente", label: "Pendiente" }, { value: "Asignada", label: "Asignada" }]} />}
      {user?.role === "L4" && form.status === "Asignada" && <Input label="Ejecutor L5 de mi equipo" name="assignee_id" type="select" value={form.assignee_id} onChange={(e) => setForm({ ...form, assignee_id: e.target.value })} required options={optionsFor(developersForProject)} />}
      <Button type="submit" disabled={!context.projects.length}>Guardar tarea</Button>
    </form>}

    {user?.role === "L2" && context.projects.map((project) => {
      const coordinations = context.coordination_assignments?.filter((item) => item.project_id === project.id) || [];
      return <section key={project.id} style={{ margin: "24px 0", padding: 16, background: "#111427", border: "1px solid rgba(63,229,229,0.12)", borderRadius: 8 }}>
        <h2>{project.name}</h2>
        {can(user, "tasks", "designate") && <div style={{ display: "flex", gap: 10, alignItems: "end", maxWidth: 600 }}>
          <div style={{ flex: 1 }}><Input label="Designar coordinación L3" name={`coordinator-${project.id}`} type="select" value={designation[project.id] || ""} onChange={(e) => setDesignation({ ...designation, [project.id]: e.target.value })} options={optionsFor(context.coordinators || [])} /></div>
          <Button onClick={() => submitCoordination(project.id)} disabled={!designation[project.id]}>Designar</Button>
        </div>}
        {coordinations.map((item) => <div key={`${item.project_id}-${item.coordinator_id}`} style={{ display: "flex", justifyContent: "space-between", gap: 12, maxWidth: 600, color: "#8892a4", paddingTop: 8 }}>
          <span>Coordinación L3 vigente: {item.coordinator_name}</span>
          {item.can_remove && <Button size="sm" variant="ghost" onClick={() => submitRemoveCoordinator(project.id, item.coordinator_id)}>Retirar</Button>}
        </div>)}
      </section>;
    })}

    {(user?.role === "L3" || user?.role === "L4") && context.projects.map((project) => {
      const projectDevelopers = context.developers.filter((person) => person.project_id === project.id);
      return <section key={project.id} style={{ margin: "24px 0", padding: 16, background: "#111427", border: "1px solid rgba(63,229,229,0.12)", borderRadius: 8 }}>
        <h2>{project.name}</h2>
        {user.role === "L3" && can(user, "tasks", "delegate") && <div style={{ display: "flex", gap: 10, alignItems: "end", maxWidth: 600 }}>
          <div style={{ flex: 1 }}><Input label="Designar líder L4" name={`leader-${project.id}`} type="select" value={designation[project.id] || ""} onChange={(e) => setDesignation({ ...designation, [project.id]: e.target.value })} options={optionsFor(context.leaders)} /></div>
          <Button onClick={() => submitDesignation(project.id)} disabled={!designation[project.id]}>Designar</Button>
        </div>}
        {user.role === "L4" && can(user, "tasks", "manageTeam") && <div style={{ display: "flex", gap: 10, alignItems: "end", maxWidth: 600 }}>
          <div style={{ flex: 1 }}><Input label="Incorporar L5 al equipo" name={`member-${project.id}`} type="select" value={designation[project.id] || ""} onChange={(e) => setDesignation({ ...designation, [project.id]: e.target.value })} options={optionsFor(context.all_developers || [])} /></div>
          <Button onClick={() => submitMember(project.id)} disabled={!designation[project.id]}>Incorporar</Button>
        </div>}
        {user.role === "L3" && can(user, "tasks", "withdrawLeadership") && context.leadership_assignments?.filter((item) => item.project_id === project.id).map((item) => <div key={item.leader_id} style={{ display: "flex", justifyContent: "space-between", gap: 12, maxWidth: 600, color: "#8892a4", paddingTop: 8 }}><span>Líder vigente: {item.leader_name}</span>{item.can_remove && <Button size="sm" variant="ghost" onClick={() => submitRemoveLeader(project.id, item.leader_id)}>Retirar</Button>}</div>)}
        {user.role === "L4" && can(user, "tasks", "withdrawTeam") && projectDevelopers.map((person) => <div key={person.id} style={{ display: "flex", justifyContent: "space-between", gap: 12, maxWidth: 600, color: "#8892a4", paddingTop: 8 }}><span>Integrante vigente: {person.name}</span>{person.can_remove && <Button size="sm" variant="ghost" onClick={() => submitRemoveMember(project.id, person.id)}>Retirar</Button>}</div>)}
      </section>;
    })}

    {user?.role !== "L2" && <>
    <h2>Trabajo autorizado</h2>
    <Table isLoading={loading}>
      <Table.Head><Table.Row><Table.HeadCell>Proyecto</Table.HeadCell><Table.HeadCell>Tarea</Table.HeadCell><Table.HeadCell>Estado</Table.HeadCell><Table.HeadCell>Ejecutor</Table.HeadCell><Table.HeadCell>Acción</Table.HeadCell></Table.Row></Table.Head>
      <Table.Body>{context.tasks.length === 0 ? <Table.Empty colSpan={5} message="No hay tareas en tu ámbito." /> : context.tasks.map((task, index) => {
        const options = context.developers.filter((person) => person.project_id === task.project_id);
        return <Table.Row key={task.id} index={index}>
          <Table.Cell>{task.project_name}</Table.Cell><Table.Cell><strong>{task.title}</strong>{task.description && <div style={{ color: "#8892a4", marginTop: 4 }}>{task.description}</div>}<details style={{ color: "#8892a4", fontSize: 12, marginTop: 6 }}><summary style={{ cursor: "pointer" }}>Responsables e historial</summary><p>Responsable actual: {task.responsible_name || "—"}<br />Creada por: {task.created_by_name || "—"}<br />Registro: {new Date(task.created_at).toLocaleString()}</p>{task.assigned_at && <p>Asignada: {new Date(task.assigned_at).toLocaleString()}</p>}{task.events?.map((event, eventIndex) => <div key={`${event.event_type}-${eventIndex}`} style={{ padding: "4px 0" }}><p>{eventLabels[event.event_type] || event.event_type} por {event.actor_name} · {new Date(event.occurred_at).toLocaleString()}{event.assignee_name ? ` · Ejecutor ${event.assignee_name}` : ""}{event.previous_status && event.new_status ? ` · ${event.previous_status} → ${event.new_status}` : ""}</p>{event.result_text && <p>Resultado presentado: {event.result_text}</p>}{event.reason && <p>Motivo de revisión: {event.reason}</p>}</div>)}</details></Table.Cell><Table.Cell>{task.status}</Table.Cell><Table.Cell>{task.assignee_name || "Sin asignar"}</Table.Cell>
          <Table.Cell>
            {user?.role === "L4" && task.status === "Pendiente" && <div style={{ display: "flex", gap: 8 }}><select aria-label={`Ejecutor para ${task.title}`} style={selectStyle} value={assignment[task.id] || ""} onChange={(e) => setAssignment({ ...assignment, [task.id]: e.target.value })}><option value="">Selecciona L5</option>{options.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}</select><Button size="sm" disabled={!assignment[task.id]} onClick={() => submitAssignment(task.id)}>Asignar</Button></div>}
            {can(user, "tasks", "start") && task.actions?.can_start && <Button size="sm" onClick={() => startTaskAction(task)}>{task.status === "Observada" ? "Iniciar corrección" : "Iniciar tarea"}</Button>}
            {can(user, "tasks", "submitReview") && task.actions?.can_submit_result && <div style={{ display: "grid", gap: 8, minWidth: 220 }}><Input label="Resultado presentado" name={`result-${task.id}`} type="textarea" value={results[task.id] || ""} onChange={(e) => setResults({ ...results, [task.id]: e.target.value })} required /><Button size="sm" disabled={!results[task.id]?.trim()} onClick={() => submitResult(task.id)}>Enviar a revisión</Button></div>}
            {can(user, "tasks", "review") && task.actions?.can_review && <div style={{ display: "grid", gap: 8, minWidth: 220 }}><Input label="Motivo de observación" name={`reason-${task.id}`} type="textarea" value={reviewReasons[task.id] || ""} onChange={(e) => setReviewReasons({ ...reviewReasons, [task.id]: e.target.value })} /><Button size="sm" variant="ghost" disabled={!reviewReasons[task.id]?.trim()} onClick={() => resolveReview(task.id, "Observada")}>Devolver con observaciones</Button><Button size="sm" onClick={() => resolveReview(task.id, "Finalizada")}>Aprobar resultado</Button></div>}
          </Table.Cell>
        </Table.Row>;
      })}</Table.Body>
    </Table>
    </>}
  </section>;
}
