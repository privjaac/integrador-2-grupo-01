import { useEffect, useState } from "react";
import { getClients } from "../../api/clients";
import { createProject, getProjects } from "../../api/projects";

const fieldStyle = { padding: "10px 12px", background: "#0b0d1a", color: "white", border: "1px solid #34394a", borderRadius: 6 };

export default function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [clients, setClients] = useState([]);
  const [form, setForm] = useState({ client_id: "", name: "", objective: "", scope: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    try {
      const [projectRows, clientRows] = await Promise.all([getProjects(), getClients()]);
      setProjects(projectRows);
      setClients(clientRows);
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudieron cargar los proyectos.");
    } finally { setLoading(false); }
  }

  useEffect(() => { refresh(); }, []);

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

  return <section style={{ color: "white", maxWidth: 1050, margin: "0 auto" }}>
    <h1>Proyectos</h1>
    <p style={{ color: "#aab2c5" }}>Los proyectos nuevos se crean en estado Planificado.</p>
    {error && <p role="alert" style={{ color: "#ff718b" }}>{String(error)}</p>}
    <form onSubmit={submit} style={{ display: "grid", gap: 12, margin: "24px 0", maxWidth: 600 }}>
      <h2>Crear proyecto</h2>
      <select required value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} style={fieldStyle}>
        <option value="">Selecciona un cliente</option>{clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
      </select>
      <input required maxLength={200} placeholder="Nombre del proyecto" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={fieldStyle} />
      <textarea placeholder="Objetivo (opcional)" value={form.objective} onChange={(e) => setForm({ ...form, objective: e.target.value })} style={fieldStyle} />
      <textarea placeholder="Alcance (opcional)" value={form.scope} onChange={(e) => setForm({ ...form, scope: e.target.value })} style={fieldStyle} />
      <button type="submit" style={{ ...fieldStyle, cursor: "pointer" }}>Crear proyecto</button>
    </form>
    <h2>Proyectos registrados</h2>
    {loading ? <p>Cargando…</p> : projects.length === 0 ? <p>No hay proyectos registrados.</p> : <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr>{["Nombre", "Cliente", "Estado", "Objetivo", "Alcance"].map((label) => <th key={label} style={{ textAlign: "left", padding: 10, borderBottom: "1px solid #34394a" }}>{label}</th>)}</tr></thead><tbody>{projects.map((project) => <tr key={project.id}>{[project.name, project.client_name, project.status, project.objective || "—", project.scope || "—"].map((value, index) => <td key={index} style={{ padding: 10, borderBottom: "1px solid #202434" }}>{value}</td>)}</tr>)}</tbody></table></div>}
  </section>;
}
