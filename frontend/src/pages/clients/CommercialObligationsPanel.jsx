import { useCallback, useEffect, useState } from 'react';
import {
  getContractedServices,
  getDocumentedPaymentDues,
  getEligibleCommercialResponsibles,
  recordDocumentedPaymentDue,
  requestClientChange,
} from '../../api/clients';
import { can } from '../../utils/permissions';

const panelStyle = {
  backgroundColor: '#111427', border: '1px solid rgba(63,229,229,0.08)',
  borderRadius: '0.75rem', padding: '1.25rem 1.5rem', color: '#c5cdd8',
};
const fieldStyle = {
  padding: '0.55rem 0.7rem', background: '#171b2e', color: 'white',
  border: '1px solid rgba(63,229,229,0.2)', borderRadius: 5,
};

export default function CommercialObligationsPanel({ client, user, onUpdated }) {
  const canManageOwner = ['L1', 'L2'].includes(user?.role) && can(user, 'clients', 'resolveChange');
  const canManageDue = user?.role === 'L2' && can(user, 'clients', 'edit');
  const canViewDues = ['L1', 'L2'].includes(user?.role) && can(user, 'clients', 'view');
  const [people, setPeople] = useState([]);
  const [services, setServices] = useState([]);
  const [dues, setDues] = useState([]);
  const [ownerId, setOwnerId] = useState('');
  const [ownerReason, setOwnerReason] = useState('');
  const [due, setDue] = useState({ service_id: '', due_date: '', obligation_reference: '', evidence_reference: '' });
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const results = await Promise.all([
      canManageOwner ? getEligibleCommercialResponsibles() : Promise.resolve([]),
      canManageDue ? getContractedServices(client.id) : Promise.resolve([]),
      canViewDues ? getDocumentedPaymentDues(client.id) : Promise.resolve([]),
    ]);
    setPeople(results[0]);
    setServices(results[1]);
    setDues(results[2]);
    setOwnerId(client.commercial_responsible_id ? String(client.commercial_responsible_id) : '');
  }, [canManageDue, canManageOwner, canViewDues, client.id, client.commercial_responsible_id]);

  useEffect(() => {
    load().catch((error) => setFeedback(error.userMessage || 'No se pudo cargar la información comercial.'));
  }, [load]);

  const submitOwner = async (event) => {
    event.preventDefault();
    if (!ownerReason.trim()) return setFeedback('Indica el motivo de la designación o retiro.');
    setBusy(true);
    try {
      await requestClientChange(client.id, {
        commercial_responsible_id: ownerId ? Number(ownerId) : null,
      }, ownerReason.trim());
      setOwnerReason('');
      setFeedback('Solicitud enviada al flujo de aprobación del CRM.');
      await onUpdated();
    } catch (error) {
      setFeedback(error.userMessage || 'No se pudo registrar la solicitud.');
    } finally {
      setBusy(false);
    }
  };

  const submitDue = async (event) => {
    event.preventDefault();
    if (!due.obligation_reference.trim() && !due.evidence_reference.trim()) {
      setFeedback('Indica una referencia de obligación o evidencia documental.');
      return;
    }
    setBusy(true);
    try {
      await recordDocumentedPaymentDue(client.id, { ...due, service_id: Number(due.service_id) });
      setDue({ service_id: '', due_date: '', obligation_reference: '', evidence_reference: '' });
      setFeedback('Vencimiento documentado registrado.');
      await load();
    } catch (error) {
      setFeedback(error.userMessage || 'No se pudo registrar el vencimiento.');
    } finally {
      setBusy(false);
    }
  };

  if (!canManageOwner && !canManageDue) return null;

  return (
    <section style={panelStyle} aria-label="Gestión comercial autorizada">
      <h2 style={{ color: '#3fe5e5', fontSize: 13, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
        Seguimiento comercial documentado
      </h2>
      {canManageOwner && (
        <form onSubmit={submitOwner} style={{ display: 'grid', gap: 9, margin: '1rem 0' }}>
          <strong>Responsable comercial: {client.commercial_responsible_active
            ? client.commercial_responsible_name
            : client.commercial_responsible_id ? 'Designación sin responsable vigente' : 'Sin designación'}</strong>
          <label htmlFor="commercial-owner">Responsable autorizado</label>
          <select id="commercial-owner" style={fieldStyle} value={ownerId} onChange={(event) => setOwnerId(event.target.value)}>
            <option value="">Sin responsable</option>
            {people.map((person) => <option key={person.id} value={person.id}>{person.name} ({person.role})</option>)}
          </select>
          <input style={fieldStyle} value={ownerReason} onChange={(event) => setOwnerReason(event.target.value)} placeholder="Motivo de la solicitud" aria-label="Motivo de designación" />
          <button disabled={busy} style={fieldStyle}>Solicitar cambio de responsable</button>
        </form>
      )}

      {canManageDue && (
        <form onSubmit={submitDue} style={{ display: 'grid', gap: 9, margin: '1rem 0' }}>
          <strong>Registrar vencimiento de pago acreditado por documento (L2)</strong>
          <select required aria-label="Servicio contratado" style={fieldStyle} value={due.service_id} onChange={(event) => setDue({ ...due, service_id: event.target.value })}>
            <option value="">Selecciona el servicio contratado</option>
            {services.map((service) => <option key={service.id} value={service.id}>{service.service_name} · #{service.id}</option>)}
          </select>
          <input required type="date" aria-label="Fecha de vencimiento" style={fieldStyle} value={due.due_date} onChange={(event) => setDue({ ...due, due_date: event.target.value })} />
          <input maxLength={200} aria-label="Referencia de obligación (opcional)" style={fieldStyle} placeholder="Referencia de la obligación (opcional)" value={due.obligation_reference} onChange={(event) => setDue({ ...due, obligation_reference: event.target.value })} />
          <input maxLength={300} aria-label="Referencia de evidencia (opcional)" style={fieldStyle} placeholder="Referencia documental o evidencia (opcional)" value={due.evidence_reference} onChange={(event) => setDue({ ...due, evidence_reference: event.target.value })} />
          <small>Es necesario indicar una referencia o una evidencia.</small>
          <button disabled={busy || !services.length || (!due.obligation_reference.trim() && !due.evidence_reference.trim())} style={fieldStyle}>Registrar vencimiento documentado</button>
        </form>
      )}

      {canViewDues && dues.length > 0 && (
        <div>
          <strong>Vencimientos documentados</strong>
          {dues.map((item) => <p key={item.id} style={{ borderTop: '1px solid rgba(63,229,229,0.12)', paddingTop: 8 }}>
            {item.service_name} · {item.due_date} · {item.obligation_reference} · evidencia: {item.evidence_reference}
          </p>)}
        </div>
      )}
      {feedback && <p role="status">{feedback}</p>}
      <small>La designación no concede acceso financiero. Los avisos externos preparados no significan que hayan sido enviados.</small>
    </section>
  );
}
