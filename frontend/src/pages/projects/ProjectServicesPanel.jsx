import { useEffect, useState } from "react";
import { getContractedServices } from "../../api/clients";
import { getProjectContractedServices, linkContractedService, unlinkContractedService } from "../../api/projects";

const fieldStyle = { padding: "8px 10px", background: "#0b0d1a", color: "white", border: "1px solid #34394a", borderRadius: 6 };

export default function ProjectServicesPanel({ project, canManage }) {
  const [links, setLinks] = useState([]);
  const [services, setServices] = useState([]);
  const [serviceId, setServiceId] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    const [linkRows, serviceRows] = await Promise.all([
      getProjectContractedServices(project.id), getContractedServices(project.client_id),
    ]);
    setLinks(linkRows);
    setServices(serviceRows);
  }

  useEffect(() => { refresh().catch(() => setError("No se pudieron cargar los servicios asociados.")); }, [project.id]);

  async function submitLink(event) {
    event.preventDefault();
    setError("");
    try {
      await linkContractedService(project.id, { service_id: Number(serviceId), reason });
      setServiceId(""); setReason(""); await refresh();
    } catch (err) { setError(err.response?.data?.detail || "No se pudo asociar el servicio."); }
  }

  async function submitUnlink(link) {
    const unlinkReason = window.prompt("Motivo de desvinculación:");
    if (!unlinkReason?.trim()) return;
    setError("");
    try {
      await unlinkContractedService(project.id, link.id, { service_id: link.service_id, reason: unlinkReason.trim() });
      await refresh();
    } catch (err) { setError(err.response?.data?.detail || "No se pudo desvincular el servicio."); }
  }

  return <section style={{ display: "grid", gap: 8, marginTop: 12 }}>
    <h4>Servicios contratados</h4>
    {error && <p role="alert">{error}</p>}
    {links.length === 0 ? <p>No hay vínculos registrados para este proyecto.</p> : links.map((link) => <div key={link.id}>
      <p>{link.service_name} · {link.commitment_reference} · {link.frequency} · alcance: {link.scope}</p>
      <small>Vínculo {link.is_active ? "vigente" : "histórico"}, registrado {new Date(link.linked_at).toLocaleString()} · {link.link_reason}</small>
      {canManage && link.is_active && <button type="button" onClick={() => submitUnlink(link)} style={fieldStyle}>Desvincular</button>}
    </div>)}
    {canManage && <form onSubmit={submitLink} style={{ display: "grid", gap: 8, maxWidth: 620 }}>
      <label>Servicio del mismo cliente<select required value={serviceId} onChange={(event) => setServiceId(event.target.value)} style={fieldStyle}>
        <option value="">Seleccionar servicio contratado</option>
        {services.filter((service) => !service.active_project_id).map((service) => <option key={service.id} value={service.id}>{service.service_name} · {service.commitment_reference} · {service.frequency}</option>)}
      </select></label>
      <label>Motivo del vínculo<textarea required value={reason} onChange={(event) => setReason(event.target.value)} style={fieldStyle} /></label>
      <button type="submit" disabled={!serviceId || !reason.trim()} style={fieldStyle}>Asociar servicio contratado</button>
    </form>}
  </section>;
}
