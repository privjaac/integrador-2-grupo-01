import { useEffect, useState } from "react";
import { amendContractedService, getContractedServices, recordContractedService } from "../../api/clients";
import { getWebTypes } from "../../api/catalog";

const initialForm = { service_name: "", catalog_service_id: "", commitment_reference: "", scope: "", agreed_amount: "", currency: "PEN", frequency: "mensual", effective_start: "", contracted_duration: "", documented_expiration: "", terms: "", evidence_reference: "", reason: "", impact_assessment: "" };
const fieldStyle = { padding: "8px 10px", background: "#0b0d1a", color: "white", border: "1px solid #34394a", borderRadius: 6, width: "100%" };

export default function ContractedServicesPanel({ clientId, canManage }) {
  const [services, setServices] = useState([]);
  const [offers, setOffers] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh() {
    const [serviceRows, offerRows] = await Promise.all([getContractedServices(clientId), getWebTypes()]);
    setServices(serviceRows); setOffers(offerRows);
  }
  useEffect(() => { refresh().catch(() => setError("No se pudieron cargar los compromisos contratados.")).finally(() => setLoading(false)); }, [clientId]);

  function edit(service) {
    setEditingId(service.id);
    setForm({ ...initialForm, ...service, catalog_service_id: service.catalog_service_id ? String(service.catalog_service_id) : "", agreed_amount: service.agreed_amount ?? "", effective_start: service.effective_start || "", documented_expiration: service.documented_expiration || "", reason: "Modificación comercial autorizada" });
  }

  async function submit(event) {
    event.preventDefault(); setError("");
    const payload = { ...form, catalog_service_id: form.catalog_service_id ? Number(form.catalog_service_id) : null, agreed_amount: form.agreed_amount || null, effective_start: form.effective_start || null, documented_expiration: form.documented_expiration || null };
    try {
      if (editingId) await amendContractedService(clientId, editingId, payload);
      else await recordContractedService(clientId, payload);
      setForm(initialForm); setEditingId(null); await refresh();
    } catch (err) { setError(err.response?.data?.detail || err.userMessage || "No se pudo guardar el compromiso."); }
  }

  return <section style={{ background: "#111427", border: "1px solid rgba(63,229,229,0.08)", borderRadius: 12, padding: 20 }}>
    <h3 style={{ color: "#3fe5e5" }}>Compromisos de servicio contratados</h3>
    <p style={{ color: "#aab2c5" }}>La oferta del catálogo y el compromiso comercial se conservan por separado. Las fechas proceden de la vigencia registrada.</p>
    {error && <p role="alert" style={{ color: "#ff8888" }}>{error}</p>}
    {loading ? <p>Cargando…</p> : services.length === 0 ? <p>No hay compromisos registrados.</p> : services.map((service) => <article key={service.id} style={{ borderTop: "1px solid #34394a", padding: "12px 0" }}>
      <strong>{service.service_name}{service.catalog_service_name ? ` (${service.catalog_service_name})` : ""} · {service.commitment_reference}</strong>
      <p>{service.scope}</p>
      <p>Frecuencia: {service.frequency} · Vigente desde: {service.effective_start || "pendiente de acreditar"} · Duración: {service.contracted_duration || "no especificada"} · Vencimiento documentado: {service.documented_expiration || "no documentado"} · Próxima fecha calculable: {service.next_due_date || "no determinada"}</p>
      {canManage && <button type="button" onClick={() => edit(service)} style={fieldStyle}>Registrar modificación comercial</button>}
      <details><summary>Historial</summary>{service.history.map((item) => <div key={item.id}><p>{item.action} · L2 #{item.actor_id} · {new Date(item.occurred_at).toLocaleString()} · {item.reason} · {item.evidence_reference}</p>{item.before && <p>Anterior: {JSON.stringify(item.before)}</p>}<p>Registrado: {JSON.stringify(item.after)}</p>{item.impact_assessment && <p>Impacto evaluado: {item.impact_assessment}</p>}</div>)}</details>
    </article>)}
    {canManage && <form onSubmit={submit} style={{ display: "grid", gap: 9, maxWidth: 680, marginTop: 16 }}>
      <h4>{editingId ? "Modificar compromiso" : "Registrar servicio contratado"}</h4>
      <label>Servicio contratado<input required value={form.service_name} onChange={(e) => setForm({ ...form, service_name: e.target.value })} style={fieldStyle} /></label>
      <label>Oferta del catálogo relacionada (opcional)<select value={form.catalog_service_id} onChange={(e) => setForm({ ...form, catalog_service_id: e.target.value })} style={fieldStyle}><option value="">Sin referencia de tipo web</option>{offers.map((offer) => <option key={offer.id} value={offer.id}>{offer.name}</option>)}</select></label>
      <label>Referencia de contratación<input required value={form.commitment_reference} onChange={(e) => setForm({ ...form, commitment_reference: e.target.value })} style={fieldStyle} /></label>
      <label>Compromiso y alcance<textarea required value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })} style={fieldStyle} /></label>
      <label>Importe acordado (si está documentado)<input type="number" min="0" step="0.01" value={form.agreed_amount} onChange={(e) => setForm({ ...form, agreed_amount: e.target.value })} style={fieldStyle} /></label>
      {form.agreed_amount && <label>Moneda<input maxLength={3} value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} style={fieldStyle} /></label>}
      <label>Frecuencia<select value={form.frequency} onChange={(e) => setForm({ ...form, frequency: e.target.value })} style={fieldStyle}><option value="unica">Pago único</option><option value="mensual">Mensual</option><option value="anual">Anual</option></select></label>
      <label>Inicio de vigencia<input type="date" value={form.effective_start} onChange={(e) => setForm({ ...form, effective_start: e.target.value })} style={fieldStyle} /></label>
      <label>Duración documentada<input maxLength={120} value={form.contracted_duration} onChange={(e) => setForm({ ...form, contracted_duration: e.target.value })} style={fieldStyle} /></label>
      <label>Vencimiento específico documentado<input type="date" value={form.documented_expiration} onChange={(e) => setForm({ ...form, documented_expiration: e.target.value })} style={fieldStyle} /></label>
      <label>Otras condiciones<textarea value={form.terms} onChange={(e) => setForm({ ...form, terms: e.target.value })} style={fieldStyle} /></label>
      <label>Referencia de evidencia<input required value={form.evidence_reference} onChange={(e) => setForm({ ...form, evidence_reference: e.target.value })} style={fieldStyle} /></label>
      <label>Motivo comercial<input required value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} style={fieldStyle} /></label>
      {editingId && <label>Evaluación de obligaciones afectadas<textarea required value={form.impact_assessment} onChange={(e) => setForm({ ...form, impact_assessment: e.target.value })} style={fieldStyle} /></label>}
      <div style={{ display: "flex", gap: 8 }}><button type="submit" style={fieldStyle}>{editingId ? "Guardar modificación" : "Registrar compromiso"}</button>{editingId && <button type="button" onClick={() => { setEditingId(null); setForm(initialForm); }} style={fieldStyle}>Cancelar edición</button>}</div>
    </form>}
  </section>;
}
