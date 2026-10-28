import { useEffect, useState } from "react";
import {
  createElomuxPlatform,
  getElomuxPlatforms,
  updateElomuxPlatform,
} from "../../api/elomuxPlatforms";
import normalizeApiError from "../../api/errorMessage";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import Modal from "../../components/ui/Modal";
import { can } from "../../utils/permissions";

const blankForm = { name: "", url: "", is_active: true };

export default function ElomuxPlatformsPanel({ user }) {
  const [platforms, setPlatforms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [formError, setFormError] = useState("");
  const [form, setForm] = useState(blankForm);
  const [editing, setEditing] = useState(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const canManage = can(user, "platforms", "manage");

  const reload = async () => {
    setLoading(true);
    setLoadError("");
    try {
      setPlatforms(await getElomuxPlatforms());
    } catch (error) {
      setLoadError(normalizeApiError(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { reload(); }, []);

  const beginCreate = () => {
    setEditing(null);
    setForm(blankForm);
    setFormError("");
    setOpen(true);
  };

  const beginEdit = (platform) => {
    setEditing(platform);
    setForm({ name: platform.name, url: platform.url, is_active: platform.is_active });
    setFormError("");
    setOpen(true);
  };

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setFormError("");
    try {
      const saved = editing
        ? await updateElomuxPlatform(editing.id, form)
        : await createElomuxPlatform(form);
      setPlatforms((current) => editing
        ? current.map((item) => item.id === saved.id ? saved : item)
        : [...current, saved].sort((a, b) => a.name.localeCompare(b.name, "es")));
      setOpen(false);
    } catch (error) {
      setFormError(normalizeApiError(error));
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (platform) => {
    setLoadError("");
    try {
      const updated = await updateElomuxPlatform(platform.id, { is_active: !platform.is_active });
      setPlatforms((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (error) {
      setLoadError(normalizeApiError(error));
    }
  };

  return <section aria-labelledby="elomux-platforms-title" style={{ background: "#111427", border: "1px solid rgba(63,229,229,0.18)", borderRadius: 12, padding: 24 }}>
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
      <div>
        <h2 id="elomux-platforms-title" style={{ color: "white", margin: 0 }}>Plataformas digitales ELOMUX</h2>
        <p style={{ color: "#8892a4", marginBottom: 0 }}>Canales de captación y marketing</p>
      </div>
      {canManage && <Button onClick={beginCreate}>Registrar plataforma</Button>}
    </header>

    {loadError && <p role="alert" style={{ color: "#ff8899" }}>{loadError}</p>}
    {loading ? <LoadingSpinner label="Cargando plataformas..." /> : platforms.length === 0
      ? <p style={{ color: "#8892a4", padding: "24px 0" }}>Aún no hay plataformas registradas en el sistema.</p>
      : <div style={{ overflowX: "auto", marginTop: 20 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
          <thead><tr style={{ color: "#8892a4" }}>
            <th style={{ padding: 10 }}>Plataforma</th><th style={{ padding: 10 }}>Enlace</th>
            <th style={{ padding: 10 }}>Estado</th>{canManage && <th style={{ padding: 10 }}>Acciones</th>}
          </tr></thead>
          <tbody>{platforms.map((platform) => <tr key={platform.id} style={{ borderTop: "1px solid #34394a", color: "white" }}>
            <td style={{ padding: 10 }}>{platform.name}</td>
            <td style={{ padding: 10 }}><a href={platform.url} target="_blank" rel="noreferrer" style={{ color: "#3fe5e5" }}>{platform.url}</a></td>
            <td style={{ padding: 10 }}><span style={{ color: platform.is_active ? "#00ff88" : "#8892a4" }}>{platform.is_active ? "Activo" : "Inactivo"}</span></td>
            {canManage && <td style={{ padding: 10, display: "flex", gap: 8 }}>
              <Button size="sm" variant="secondary" onClick={() => beginEdit(platform)}>Editar</Button>
              <Button size="sm" variant="ghost" onClick={() => toggleActive(platform)}>{platform.is_active ? "Desactivar" : "Activar"}</Button>
            </td>}
          </tr>)}</tbody>
        </table>
      </div>}

    <Modal isOpen={open} onClose={() => !saving && setOpen(false)}>
      <Modal.Header title={editing ? "Editar plataforma" : "Registrar plataforma"} onClose={() => !saving && setOpen(false)} />
      <form onSubmit={save}>
        <Modal.Body>
          <div style={{ display: "grid", gap: 16 }}>
            <Input label="Nombre" name="name" value={form.name} maxLength={120} required onChange={(event) => setForm({ ...form, name: event.target.value })} />
            <Input label="URL base" name="url" type="url" value={form.url} maxLength={500} required onChange={(event) => setForm({ ...form, url: event.target.value })} />
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} />
              Activa
            </label>
            {formError && <p role="alert" style={{ color: "#ff8899", margin: 0 }}>{formError}</p>}
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Button type="button" variant="secondary" disabled={saving} onClick={() => setOpen(false)}>Cancelar</Button>
          <Button type="submit" disabled={saving} isLoading={saving}>Guardar</Button>
        </Modal.Footer>
      </form>
    </Modal>
  </section>;
}
