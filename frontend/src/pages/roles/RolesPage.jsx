import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";
import { createRole, deleteRole, getPermissionCatalog, getRoles, updateRole } from "../../api/roles";

const panelStyle = {
  padding: 20, borderRadius: 10, color: "#e8edf5", background: "#111427",
  border: "1px solid rgba(63,229,229,.18)",
};
const fieldStyle = {
  boxSizing: "border-box", width: "100%", padding: 10, color: "white",
  background: "#090d19", border: "1px solid #48516a", borderRadius: 6,
};

const EMPTY_FORM = { name: "", level: "L5", description: "", permissions: [], is_active: true };

export default function RolesPage() {
  const { user } = useAuth();
  const [roles, setRoles] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [editing, setEditing] = useState(null);
  const [showEditor, setShowEditor] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const mayCreate = can(user, "roles", "create");
  const mayEdit = can(user, "roles", "edit");
  const mayDelete = can(user, "roles", "delete");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [roleRows, permissionRows] = await Promise.all([getRoles(), getPermissionCatalog()]);
      setRoles(roleRows);
      setCatalog(permissionRows);
      setError("");
    } catch (e) {
      setError(e.userMessage || e.response?.data?.detail || "No se pudieron cargar los roles.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const levelPermissions = useMemo(
    () => catalog.filter((item) => item.levels.includes(form.level)),
    [catalog, form.level],
  );

  function startCreate() {
    setShowEditor(true);
    setEditing(null);
    setForm({ ...EMPTY_FORM, level: user?.role || "L5" });
    setNotice(""); setError("");
  }

  function startEdit(role) {
    setShowEditor(true);
    setEditing(role);
    setForm({
      name: role.name, level: role.level, description: role.description || "",
      permissions: [...(role.permissions || [])], is_active: role.is_active,
    });
    setNotice(""); setError("");
  }

  function togglePermission(key) {
    setForm((current) => ({
      ...current,
      permissions: current.permissions.includes(key)
        ? current.permissions.filter((item) => item !== key)
        : [...current.permissions, key],
    }));
  }

  async function saveRole(event) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    try {
      const payload = {
        name: form.name.trim(), description: form.description.trim(),
        permissions: form.permissions, is_active: form.is_active,
      };
      if (editing) await updateRole(editing.id, payload);
      else await createRole({ ...payload, level: form.level });
      setEditing(null); setShowEditor(false); setForm(EMPTY_FORM); setNotice("Rol guardado correctamente.");
      await refresh();
    } catch (e) {
      setError(e.userMessage || e.response?.data?.detail || "No se pudo guardar el rol.");
    } finally { setSaving(false); }
  }

  async function removeRole(role) {
    if (!window.confirm(`¿Eliminar el rol “${role.name}”? Se conservará su registro de auditoría.`)) return;
    setError("");
    try { await deleteRole(role.id); setNotice("Rol eliminado; su historial se conserva."); await refresh(); }
    catch (e) { setError(e.userMessage || e.response?.data?.detail || "No se pudo eliminar el rol."); }
  }

  async function toggleActive(role) {
    const next = !role.is_active;
    if (role.level === "L1" && !next) return;
    setError("");
    try { await updateRole(role.id, { is_active: next }); setNotice(next ? "Rol activado." : "Rol desactivado."); await refresh(); }
    catch (e) { setError(e.userMessage || e.response?.data?.detail || "No se pudo cambiar el estado del rol."); }
  }

  return (
    <main style={{ display: "grid", gap: 18 }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        <div><h1 style={{ color: "white", margin: 0 }}>Roles y permisos</h1>
          <p style={{ color: "#9aa5bb" }}>Roles organizacionales asociados a los niveles funcionales fijos L1–L5.</p></div>
        {mayCreate && <button type="button" onClick={startCreate}>Nuevo rol</button>}
      </header>
      {error && <p role="alert" style={{ color: "#ff718c" }}>{error}</p>}
      {notice && <p role="status" style={{ color: "#3fe5e5" }}>{notice}</p>}

      <section style={panelStyle} aria-label="Roles existentes">
        {loading ? <p>Cargando…</p> : roles.length === 0 ? <p>No existen roles registrados.</p> : (
          <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead><tr>{["Nombre", "Nivel", "Estado", "Permisos", "Colaboradores", "Acciones"].map((h) => <th key={h} style={{ textAlign: "left", padding: 10 }}>{h}</th>)}</tr></thead>
            <tbody>{roles.map((role) => <tr key={role.id}>
              <td style={{ padding: 10 }}>{role.name}<small style={{ display: "block", color: "#9aa5bb" }}>{role.description}</small></td>
              <td style={{ padding: 10 }}>{role.level}</td>
              <td style={{ padding: 10 }}>{role.is_active ? "Activo" : "Inactivo"}</td>
              <td style={{ padding: 10, minWidth: 220 }}>{role.permissions?.length ? role.permissions.join(", ") : "Sin permisos"}</td>
              <td style={{ padding: 10 }}>{role.collaborators_count}</td>
              <td style={{ padding: 10, display: "flex", gap: 8 }}>
                {mayEdit && <button type="button" onClick={() => startEdit(role)}>Editar</button>}
                {mayEdit && role.level !== "L1" && <button type="button" onClick={() => toggleActive(role)}>{role.is_active ? "Desactivar" : "Activar"}</button>}
                {mayDelete && role.level !== "L1" && role.collaborators_count === 0 && <button type="button" onClick={() => removeRole(role)}>Eliminar</button>}
              </td>
            </tr>)}</tbody>
          </table></div>
        )}
      </section>

      {showEditor && (editing ? mayEdit : mayCreate) && (
        <form onSubmit={saveRole} style={{ ...panelStyle, display: "grid", gap: 14 }}>
          <h2 style={{ margin: 0 }}>{editing ? `Editar ${editing.name}` : "Crear rol organizacional"}</h2>
          <label>Nombre<input style={fieldStyle} required minLength={2} maxLength={50} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label>Nivel funcional<select style={fieldStyle} value={form.level} disabled={Boolean(editing)} onChange={(e) => setForm({ ...form, level: e.target.value, permissions: [] })}>{["L1", "L2", "L3", "L4", "L5"].map((level) => <option key={level}>{level}</option>)}</select></label>
          <label>Descripción<textarea style={fieldStyle} maxLength={1000} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
          {editing && editing.level !== "L1" && <label><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Rol activo</label>}
          <fieldset disabled={Boolean(editing && !editing.permissions_editable)} style={{ border: "1px solid #48516a", borderRadius: 8, display: "grid", gap: 8 }}>
            <legend>Permisos disponibles para {form.level}</legend>
            {editing && !editing.permissions_editable && <p>Los permisos del rol L1 existente se conservan; aquí solo se editan nombre y descripción.</p>}
            {levelPermissions.length === 0 ? <p>Sin permisos disponibles para el nivel seleccionado.</p> : levelPermissions.map((item) => (
              <label key={item.key}><input type="checkbox" checked={form.permissions.includes(item.key)} onChange={() => togglePermission(item.key)} /> {item.key}</label>
            ))}
          </fieldset>
          <p style={{ color: "#9aa5bb" }}>Los permisos solo reducen las capacidades del nivel y se validan también en el servidor.</p>
          <div style={{ display: "flex", gap: 8 }}><button disabled={saving}>{saving ? "Guardando…" : "Guardar"}</button><button type="button" onClick={() => { setEditing(null); setShowEditor(false); setForm(EMPTY_FORM); }}>Cancelar</button></div>
        </form>
      )}
    </main>
  );
}
