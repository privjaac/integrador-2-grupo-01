import { useCallback, useEffect, useState } from "react";
import {
  decideProjectCancellation, decideProjectResumptionCommercially,
  evaluateProjectCancellation, evaluateProjectCancellationCommercially,
  evaluateProjectResumption, getProjectCancellations, getProjectResumptions,
  openProjectCancellation, recordProjectCancellationEffectivity,
} from "../../api/projects";

const fieldStyle = { padding: "9px 11px", background: "#0b0d1a", color: "white", border: "1px solid #34394a", borderRadius: 6, width: "100%" };
const labels = {
  solicitada: "Solicitud registrada",
  evaluacion_tecnica: "Evaluación técnica L3",
  autorizada: "Autorización ordinaria L2",
  denegada: "Denegación L2",
  decision_l1_autorizada: "Autorización excepcional L1",
  decision_l1_denegada: "Denegación excepcional L1",
  escalamiento_l1: "Escalamiento a L1",
  evaluacion_comercial: "Evaluación comercial L2",
  efectiva: "Cancelación efectiva",
};

export default function ProjectCancellationPanel({ project, user, canRequest, canEvaluate, canResolve }) {
  const [cancellations, setCancellations] = useState([]);
  const [resumptions, setResumptions] = useState([]);
  const [scope, setScope] = useState(project.scope || "");
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState("");
  const [technical, setTechnical] = useState({ affected_tasks_assessment: "", obligations_assessment: "", evidence: "", l1_intervention_required: false, l1_exception_reason: "" });
  const [commercial, setCommercial] = useState({ within_l2_competence: false, commercial_consequences: "", effectivity_conditions: "", evidence: "" });
  const [decision, setDecision] = useState({ authorized: false, reason: "", evidence: "", planned_effective_at: "" });
  const [effectivity, setEffectivity] = useState({ reason: "", evidence: "" });
  const [resumptionTechnical, setResumptionTechnical] = useState({ feasibility: "", pending_work: "", evidence: "" });
  const [resumptionDecision, setResumptionDecision] = useState({ authorized: false, reason: "", conditions: "", evidence: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [cancellationRows, resumptionRows] = await Promise.all([
        getProjectCancellations(project.id), getProjectResumptions(project.id),
      ]);
      setCancellations(cancellationRows);
      setResumptions(resumptionRows);
      setError("");
    } catch (requestError) {
      setError(requestError.userMessage || requestError.response?.data?.detail || "No se pudo cargar el historial de cancelación.");
    }
  }, [project.id]);

  useEffect(() => { refresh(); }, [refresh]);

  const current = [...cancellations].reverse().find((item) => {
    const last = item.events.at(-1)?.event_type;
    return !["denegada", "decision_l1_denegada", "efectiva"].includes(last);
  });
  const latestEvent = current?.events.at(-1);
  const isEffective = cancellations.some((item) => item.events.some((event) => event.event_type === "efectiva"));
  const canOpenCancellation = canRequest && !current && !isEffective && project.status !== "Entregado";
  const canReview = canEvaluate && current && latestEvent?.event_type === "solicitada";
  const canMakeEffective = canResolve && current && latestEvent?.event_type === "autorizada";
  const canEvaluateCommercially = user?.role === "L2" && current && ["evaluacion_tecnica", "escalamiento_l1"].includes(latestEvent?.event_type)
    && !current.events.some((event) => ["evaluacion_comercial", "decision_l1_autorizada", "decision_l1_denegada"].includes(event.event_type));
  const canDecideCommercially = user?.role === "L2" && current && latestEvent?.event_type === "evaluacion_comercial";
  const canApplyEffectivity = canResolve && current && ["autorizada", "decision_l1_autorizada"].includes(latestEvent?.event_type);
  const effectiveCancellation = [...cancellations].reverse().find((item) => item.events.some((event) => event.event_type === "efectiva"));
  const existingResumption = effectiveCancellation && resumptions.find((item) => item.cancellation_id === effectiveCancellation.id);
  const canEvaluateResume = user?.role === "L3" && effectiveCancellation && !existingResumption;
  const canDecideResume = user?.role === "L2" && existingResumption
    && existingResumption.events.some((event) => event.event_type === "evaluacion_tecnica")
    && !existingResumption.events.some((event) => ["decision_comercial_aprobada", "decision_comercial_denegada"].includes(event.event_type));

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
        <label><input type="checkbox" checked={technical.l1_intervention_required} onChange={(event) => setTechnical({ ...technical, l1_intervention_required: event.target.checked, l1_exception_reason: "" })} /> Requiere intervención excepcional L1</label>
        {technical.l1_intervention_required && <label style={{ display: "grid", gap: 4 }}>Circunstancia técnica excepcional<textarea value={technical.l1_exception_reason} onChange={(event) => setTechnical({ ...technical, l1_exception_reason: event.target.value })} style={fieldStyle} /></label>}
        <button type="button" disabled={busy || !technical.affected_tasks_assessment.trim() || !technical.obligations_assessment.trim() || !technical.evidence.trim() || (technical.l1_intervention_required && !technical.l1_exception_reason.trim())} onClick={() => run(async () => {
          await evaluateProjectCancellation(project.id, current.id, {
            ...technical,
            l1_exception_reason: technical.l1_intervention_required ? technical.l1_exception_reason : null,
          });
        })} style={fieldStyle}>Registrar evaluación técnica L3</button>
      </>}
      {canEvaluateCommercially && <div style={{ display: "grid", gap: 8 }}>
        <h4>Evaluación comercial L2</h4>
        <label><input type="checkbox" checked={commercial.within_l2_competence} onChange={(event) => setCommercial({ ...commercial, within_l2_competence: event.target.checked })} /> La evaluación acredita que permanece dentro de la competencia ordinaria L2</label>
        <label>Consecuencias comerciales<textarea value={commercial.commercial_consequences} onChange={(event) => setCommercial({ ...commercial, commercial_consequences: event.target.value })} style={fieldStyle} /></label>
        <label>Condiciones de efectividad<textarea value={commercial.effectivity_conditions} onChange={(event) => setCommercial({ ...commercial, effectivity_conditions: event.target.value })} style={fieldStyle} /></label>
        <label>Evidencia comercial<input value={commercial.evidence} onChange={(event) => setCommercial({ ...commercial, evidence: event.target.value })} style={fieldStyle} /></label>
        <button type="button" disabled={busy || !commercial.commercial_consequences.trim() || !commercial.effectivity_conditions.trim() || !commercial.evidence.trim()} onClick={() => run(async () => {
          await evaluateProjectCancellationCommercially(project.id, current.id, commercial);
          setCommercial({ within_l2_competence: false, commercial_consequences: "", effectivity_conditions: "", evidence: "" });
        })} style={fieldStyle}>Registrar evaluación comercial y escalamiento si corresponde</button>
      </div>}
      {canDecideCommercially && <div style={{ display: "grid", gap: 8 }}>
        <h4>Decisión ordinaria L2</h4>
        <label><input type="checkbox" checked={decision.authorized} onChange={(event) => setDecision({ ...decision, authorized: event.target.checked })} /> Autorizar conforme a la evaluación comercial registrada</label>
        {decision.authorized && <label>Fecha prevista de efectividad<input type="datetime-local" value={decision.planned_effective_at} onChange={(event) => setDecision({ ...decision, planned_effective_at: event.target.value })} style={fieldStyle} /></label>}
        <label>Motivo<textarea value={decision.reason} onChange={(event) => setDecision({ ...decision, reason: event.target.value })} style={fieldStyle} /></label>
        <label>Evidencia<input value={decision.evidence} onChange={(event) => setDecision({ ...decision, evidence: event.target.value })} style={fieldStyle} /></label>
        <button type="button" disabled={busy || !decision.reason.trim() || !decision.evidence.trim() || (decision.authorized && !decision.planned_effective_at)} onClick={() => run(async () => {
          const commercialEvent = [...current.events].reverse().find((event) => event.event_type === "evaluacion_comercial");
          await decideProjectCancellation(project.id, current.id, {
            authorized: Boolean(decision.authorized), reason: decision.reason, evidence: decision.evidence,
            commercial_consequences: decision.authorized ? commercialEvent?.data?.commercial_consequences : null,
            effectivity_conditions: decision.authorized ? commercialEvent?.data?.effectivity_conditions : null,
            planned_effective_at: decision.authorized ? new Date(decision.planned_effective_at).toISOString() : null,
          });
          setDecision({ authorized: false, reason: "", evidence: "", planned_effective_at: "" });
        })} style={fieldStyle}>Registrar decisión L2</button>
      </div>}
      {canMakeEffective && <p role="status">La efectividad L2 solo puede registrarse si se acredita la competencia ordinaria conforme a las decisiones vigentes.</p>}
      {canApplyEffectivity && <div style={{ display: "grid", gap: 8 }}>
        <h4>Constancia de efectividad</h4>
        <label>Motivo<textarea value={effectivity.reason} onChange={(event) => setEffectivity({ ...effectivity, reason: event.target.value })} style={fieldStyle} /></label>
        <label>Evidencia<input value={effectivity.evidence} onChange={(event) => setEffectivity({ ...effectivity, evidence: event.target.value })} style={fieldStyle} /></label>
        <button type="button" disabled={busy || !effectivity.reason.trim() || !effectivity.evidence.trim()} onClick={() => run(async () => {
          await recordProjectCancellationEffectivity(project.id, current.id, { conditions_satisfied: true, ...effectivity });
          setEffectivity({ reason: "", evidence: "" });
        })} style={fieldStyle}>Registrar cancelación efectiva</button>
      </div>}
    </section>}
    {cancellations.map((item) => <section key={item.id} style={{ borderTop: "1px solid #34394a", marginTop: 12, paddingTop: 8 }}>
      <strong>Expediente #{item.id} · {item.cancelled_scope}</strong>
      <p>Registrado por {item.opened_by_name} · {new Date(item.opened_at).toLocaleString()} · {item.reason}</p>
      {item.events.map((event, index) => <p key={`${event.event_type}-${index}`} style={{ color: "#aab2c5" }}>
        {labels[event.event_type] || event.event_type} · {event.actor_name} · {new Date(event.occurred_at).toLocaleString()}
        {event.effective_at ? ` · Efectiva ${new Date(event.effective_at).toLocaleString()}` : ""} · {event.reason} · Evidencia: {event.evidence}
        {event.data && <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{JSON.stringify(event.data, null, 2)}</pre>}
      </p>)}
    </section>)}
    {canEvaluateResume && <section style={{ display: "grid", gap: 8, marginTop: 16, maxWidth: 760 }}>
      <h3>Evaluación técnica para reanudación · cancelación #{effectiveCancellation.id}</h3>
      <label>Viabilidad<textarea value={resumptionTechnical.feasibility} onChange={(event) => setResumptionTechnical({ ...resumptionTechnical, feasibility: event.target.value })} style={fieldStyle} /></label>
      <label>Trabajo pendiente<textarea value={resumptionTechnical.pending_work} onChange={(event) => setResumptionTechnical({ ...resumptionTechnical, pending_work: event.target.value })} style={fieldStyle} /></label>
      <label>Evidencia técnica<input value={resumptionTechnical.evidence} onChange={(event) => setResumptionTechnical({ ...resumptionTechnical, evidence: event.target.value })} style={fieldStyle} /></label>
      <button type="button" disabled={busy || !Object.values(resumptionTechnical).every((value) => value.trim())} onClick={() => run(async () => {
        await evaluateProjectResumption(project.id, effectiveCancellation.id, resumptionTechnical);
        setResumptionTechnical({ feasibility: "", pending_work: "", evidence: "" });
      })} style={fieldStyle}>Registrar evaluación técnica L3</button>
    </section>}
    {canDecideResume && <section style={{ display: "grid", gap: 8, marginTop: 16, maxWidth: 760 }}>
      <h3>Decisión comercial L2 · reanudación #{existingResumption.id}</h3>
      <label><input type="checkbox" checked={resumptionDecision.authorized} onChange={(event) => setResumptionDecision({ ...resumptionDecision, authorized: event.target.checked })} /> Aprobar reanudación comercial</label>
      <label>Motivo<textarea value={resumptionDecision.reason} onChange={(event) => setResumptionDecision({ ...resumptionDecision, reason: event.target.value })} style={fieldStyle} /></label>
      <label>Condiciones<textarea value={resumptionDecision.conditions} onChange={(event) => setResumptionDecision({ ...resumptionDecision, conditions: event.target.value })} style={fieldStyle} /></label>
      <label>Evidencia<input value={resumptionDecision.evidence} onChange={(event) => setResumptionDecision({ ...resumptionDecision, evidence: event.target.value })} style={fieldStyle} /></label>
      <button type="button" disabled={busy || !resumptionDecision.reason.trim() || !resumptionDecision.conditions.trim() || !resumptionDecision.evidence.trim()} onClick={() => run(async () => {
        await decideProjectResumptionCommercially(existingResumption.id, resumptionDecision);
        setResumptionDecision({ authorized: false, reason: "", conditions: "", evidence: "" });
      })} style={fieldStyle}>Registrar decisión comercial L2</button>
    </section>}
    {resumptions.map((item) => <section key={`resume-${item.id}`} style={{ borderTop: "1px solid #34394a", marginTop: 12, paddingTop: 8 }}>
      <strong>Reanudación #{item.id} · cancelación #{item.cancellation_id}</strong>
      {item.events.map((event, index) => <p key={`${event.event_type}-${index}`} style={{ color: "#aab2c5" }}>{event.event_type} · {event.actor_name} · {new Date(event.occurred_at).toLocaleString()} · {event.reason} · {event.evidence}</p>)}
    </section>)}
  </article>;
}
