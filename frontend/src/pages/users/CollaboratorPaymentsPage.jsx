import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCollaboratorPayments, recordCollaboratorPayment } from "../../api/collaboratorPayments";
import axiosInstance from "../../api/axios";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";
import { useToast } from "../../components/ui/Toast";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import Table from "../../components/ui/Table";

const emptyForm = { collaborator_id: "", payment_date: "", amount: "", concept: "", observation: "" };
const fieldStyle = {
  width: "100%", boxSizing: "border-box", padding: "0.7rem 0.85rem", borderRadius: "0.45rem",
  border: "1px solid rgba(63,229,229,0.22)", background: "#0b0d1a", color: "white", font: "inherit",
};

function money(value) {
  return `S/ ${Number(value || 0).toFixed(2)}`;
}

function dateText(value) {
  if (!value) return "—";
  const parsed = new Date(`${value}T00:00:00Z`);
  return parsed.toLocaleDateString("es-PE", { timeZone: "UTC" });
}

function dateTimeText(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("es-PE", { dateStyle: "short", timeStyle: "short" });
}

export default function CollaboratorPaymentsPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [payments, setPayments] = useState([]);
  const [summary, setSummary] = useState({ total_paid: "0.00", count: 0, last_payment_date: null });
  const [collaborators, setCollaborators] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const [filters, setFilters] = useState({ collaborator_id: "", payment_date: "", concept: "" });
  const [collaboratorSearch, setCollaboratorSearch] = useState("");
  const canView = can(user, "collaboratorPayments", "view");
  const canRecord = can(user, "collaboratorPayments", "record");

  const filteredCollaborators = useMemo(() => {
    const needle = collaboratorSearch.trim().toLowerCase();
    if (!needle) return collaborators;
    return collaborators.filter((item) =>
      [item.first_name, item.last_name, item.email, item.cupe]
        .some((value) => String(value || "").toLowerCase().includes(needle)),
    );
  }, [collaborators, collaboratorSearch]);

  const loadPayments = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getCollaboratorPayments({
        collaborator_id: filters.collaborator_id || undefined,
        payment_date: filters.payment_date || undefined,
        concept: filters.concept.trim() || undefined,
      });
      setPayments(result.items || []);
      setSummary(result.summary || { total_paid: "0.00", count: 0, last_payment_date: null });
    } catch (error) {
      showToast("error", "ERROR AL CARGAR PAGOS", error.userMessage || "No se pudo consultar el historial.");
    } finally {
      setLoading(false);
    }
  }, [filters, showToast]);

  useEffect(() => {
    const timer = window.setTimeout(loadPayments, 250);
    return () => window.clearTimeout(timer);
  }, [loadPayments]);

  useEffect(() => {
    if (!canView) return;
    axiosInstance.get("/api/collaborators/payments/collaborators")
      .then((response) => setCollaborators(response.data || []))
      .catch((error) => showToast("error", "ERROR AL CARGAR COLABORADORES", error.userMessage || "No se pudieron consultar los colaboradores."));
  }, [canView, showToast]);

  const updateForm = (key) => (event) => {
    setForm((previous) => ({ ...previous, [key]: event.target.value }));
    setRequestKey(crypto.randomUUID());
  };
  const hasValidAmount = /^\d+(\.\d{1,2})?$/.test(form.amount) && Number(form.amount) > 0;
  const formValid = Boolean(
    form.collaborator_id && form.payment_date && hasValidAmount
    && form.concept.trim() && form.concept.trim().length <= 150
    && form.observation.length <= 300,
  );

  async function submitPayment(event) {
    event.preventDefault();
    if (!formValid || submitting) return;
    setSubmitting(true);
    try {
      await recordCollaboratorPayment({
        collaborator_id: Number(form.collaborator_id),
        payment_date: form.payment_date,
        amount: form.amount,
        concept: form.concept.trim(),
        observation: form.observation.trim(),
      }, requestKey);
      setModalOpen(false);
      setForm(emptyForm);
      setRequestKey(crypto.randomUUID());
      showToast("success", "PAGO REGISTRADO", "Pago registrado correctamente.");
      await loadPayments();
    } catch (error) {
      showToast("error", "ERROR AL REGISTRAR PAGO", error.userMessage || "Error al registrar pago.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem", flexWrap: "wrap" }}>
        <div>
          <button type="button" onClick={() => navigate("/usuarios")} style={{ border: 0, background: "transparent", color: "#3fe5e5", cursor: "pointer", padding: 0, marginBottom: "0.65rem" }}>
            ← Colaboradores
          </button>
          <h1 style={{ color: "white", margin: 0, fontFamily: "'Rajdhani', sans-serif" }}>Pagos a colaboradores</h1>
          <p style={{ color: "#8892a4", margin: "0.35rem 0 0" }}>Historial de egresos registrados para el personal.</p>
        </div>
        {canRecord && <Button size="lg" onClick={() => { setRequestKey(crypto.randomUUID()); setModalOpen(true); }}>＋ Registrar pago</Button>}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: "1rem" }}>
        {[
          ["Total pagado", money(summary.total_paid)],
          ["Último pago", dateText(summary.last_payment_date)],
          ["Cantidad de pagos", summary.count],
        ].map(([label, value]) => (
          <section key={label} style={{ padding: "1.15rem 1.35rem", borderRadius: "0.6rem", background: "#111427", border: "1px solid rgba(63,229,229,0.14)" }}>
            <p style={{ color: "#8892a4", margin: "0 0 0.4rem", fontSize: "0.85rem" }}>{label}</p>
            <strong style={{ color: "white", fontSize: "1.35rem" }}>{value}</strong>
          </section>
        ))}
      </div>

      <section style={{ display: "flex", flexWrap: "wrap", gap: "0.8rem", padding: "1rem", borderRadius: "0.55rem", background: "#111427", border: "1px solid rgba(63,229,229,0.12)" }}>
        <label style={{ flex: "1 1 210px", color: "#aab2c5", fontSize: "0.85rem" }}>
          Colaborador
          <select style={{ ...fieldStyle, marginTop: "0.35rem" }} value={filters.collaborator_id} onChange={(event) => setFilters((old) => ({ ...old, collaborator_id: event.target.value }))}>
            <option value="">Todos</option>
            {collaborators.map((item) => <option key={item.id} value={item.id}>{item.first_name} {item.last_name} · {item.cupe || "Sin CUPE"}</option>)}
          </select>
        </label>
        <label style={{ flex: "1 1 170px", color: "#aab2c5", fontSize: "0.85rem" }}>
          Fecha de pago
          <input type="date" style={{ ...fieldStyle, marginTop: "0.35rem" }} value={filters.payment_date} onChange={(event) => setFilters((old) => ({ ...old, payment_date: event.target.value }))} />
        </label>
        <label style={{ flex: "1 1 210px", color: "#aab2c5", fontSize: "0.85rem" }}>
          Concepto
          <input style={{ ...fieldStyle, marginTop: "0.35rem" }} value={filters.concept} maxLength={150} onChange={(event) => setFilters((old) => ({ ...old, concept: event.target.value }))} placeholder="Buscar concepto" />
        </label>
        <div style={{ alignSelf: "end" }}>
          <Button variant="secondary" onClick={() => setFilters({ collaborator_id: "", payment_date: "", concept: "" })}>Limpiar</Button>
        </div>
      </section>

      <Table isLoading={loading}>
        <Table.Head><Table.Row>
          <Table.HeadCell>Colaborador</Table.HeadCell><Table.HeadCell>CUPE</Table.HeadCell>
          <Table.HeadCell>Fecha de pago</Table.HeadCell><Table.HeadCell>Monto</Table.HeadCell>
          <Table.HeadCell>Concepto</Table.HeadCell><Table.HeadCell>Observación</Table.HeadCell>
          <Table.HeadCell>Registrado por</Table.HeadCell><Table.HeadCell>Fecha de registro</Table.HeadCell>
          <Table.HeadCell>Referencia</Table.HeadCell>
        </Table.Row></Table.Head>
        <Table.Body>
          {payments.length === 0 ? <Table.Empty colSpan={9} message="No existen pagos registrados" /> : payments.map((payment, index) => (
            <Table.Row key={payment.id} index={index}>
              <Table.Cell>{payment.collaborator_name}</Table.Cell><Table.Cell>{payment.collaborator_cupe || "—"}</Table.Cell>
              <Table.Cell>{dateText(payment.payment_date)}</Table.Cell><Table.Cell>{money(payment.amount)}</Table.Cell>
              <Table.Cell>{payment.concept}</Table.Cell><Table.Cell>{payment.observation || "—"}</Table.Cell>
              <Table.Cell>{payment.registered_by_name}</Table.Cell><Table.Cell>{dateTimeText(payment.registered_at)}</Table.Cell>
              <Table.Cell>{payment.reference || "—"}</Table.Cell>
            </Table.Row>
          ))}
        </Table.Body>
      </Table>

      <Modal isOpen={modalOpen} onClose={() => !submitting && setModalOpen(false)}>
        <Modal.Header title="Registrar pago" onClose={() => !submitting && setModalOpen(false)} />
        <form onSubmit={submitPayment}>
          <Modal.Body>
            <div style={{ display: "grid", gap: "1rem" }}>
              <label style={{ color: "#aab2c5", fontSize: "0.9rem" }}>
                Buscar colaborador
                <input style={{ ...fieldStyle, marginTop: "0.35rem" }} value={collaboratorSearch} onChange={(event) => setCollaboratorSearch(event.target.value)} placeholder="Nombre, correo o CUPE" />
              </label>
              <label style={{ color: "#aab2c5", fontSize: "0.9rem" }}>
                Colaborador
                <select required style={{ ...fieldStyle, marginTop: "0.35rem" }} value={form.collaborator_id} onChange={updateForm("collaborator_id")}>
                  <option value="">Selecciona un colaborador</option>
                  {filteredCollaborators.map((item) => <option key={item.id} value={item.id}>{item.first_name} {item.last_name} · {item.email} · {item.cupe || "Sin CUPE"}</option>)}
                </select>
              </label>
              <label style={{ color: "#aab2c5", fontSize: "0.9rem" }}>Fecha de pago<input required type="date" style={{ ...fieldStyle, marginTop: "0.35rem" }} value={form.payment_date} onChange={updateForm("payment_date")} /></label>
              <label style={{ color: "#aab2c5", fontSize: "0.9rem" }}>Monto (S/)<input required type="number" min="0.01" step="0.01" style={{ ...fieldStyle, marginTop: "0.35rem" }} value={form.amount} onChange={updateForm("amount")} /></label>
              <label style={{ color: "#aab2c5", fontSize: "0.9rem" }}>Concepto<input required maxLength={150} style={{ ...fieldStyle, marginTop: "0.35rem" }} value={form.concept} onChange={updateForm("concept")} /></label>
              <label style={{ color: "#aab2c5", fontSize: "0.9rem" }}>Observación (opcional)<textarea maxLength={300} rows={3} style={{ ...fieldStyle, marginTop: "0.35rem", resize: "vertical" }} value={form.observation} onChange={updateForm("observation")} /></label>
            </div>
          </Modal.Body>
          <Modal.Footer>
            <Button type="button" variant="secondary" disabled={submitting} onClick={() => setModalOpen(false)}>Cancelar</Button>
            <Button type="submit" isLoading={submitting} disabled={!formValid || submitting}>Guardar pago</Button>
          </Modal.Footer>
        </form>
      </Modal>
    </div>
  );
}
