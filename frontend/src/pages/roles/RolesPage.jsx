import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../../hooks/useAuth";
import { can } from "../../utils/permissions";
import { createRole, deleteRole, getPermissionCatalog, getRoles, updateRole } from "../../api/roles";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Table from "../../components/ui/Table";
import { groupPermissionsByModule, permissionActionLabel } from "../../utils/rolePermissionLabels";

const PANEL_STYLE = {
  padding: 20,
  borderRadius: 12,
  color: "#e8edf5",
  background: "#111427",
  border: "1px solid rgba(63,229,229,.14)",
};
const FIELD_STYLE = {
  boxSizing: "border-box",
  width: "100%",
  padding: "10px 12px",
  color: "white",
  background: "#0b0d1a",
  border: "1px solid rgba(63,229,229,.22)",
  borderRadius: 6,
  font: "inherit",
};
const LEVEL_COLORS = {
  L1: ["#ff3366", "#ff6688", "#05060f"],
  L2: ["#8235f2", "#a066ff", "white"],
  L3: ["#4540d9", "#6b6fff", "white"],
  L4: ["#3fe5e5", "#44ddff", "#05060f"],
  L5: ["#8892a4", "#aabbcc", "#05060f"],
};
const EMPTY_FORM = { name: "", level: "L5", description: "", permissions: [], is_active: true };

function LevelMark({ level, size = 40 }) {
  const [start, end, color] = LEVEL_COLORS[level] || LEVEL_COLORS.L5;
  return (
    <span
      aria-label={`Nivel ${level}`}
      style={{
        width: size,
        height: size,
        flex: `0 0 ${size}px`,
        display: "inline-grid",
        placeItems: "center",
        clipPath: "polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%)",
        background: `linear-gradient(135deg, ${start}, ${end})`,
        color,
        fontFamily: "'Orbitron', monospace",
        fontSize: 12,
        fontWeight: 700,
      }}
    >
      {level}
    </span>
  );
}

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
  const editorHeadingRef = useRef(null);

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
    } catch (requestError) {
      setError(requestError.userMessage || requestError.response?.data?.detail || "No se pudieron cargar los roles.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    if (!showEditor) return;
    editorHeadingRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    editorHeadingRef.current?.focus({ preventScroll: true });
  }, [showEditor, editing]);

  const levelPermissions = useMemo(
    () => catalog.filter((item) => item.levels.includes(form.level)),
    [catalog, form.level],
  );

  function startCreate() {
    setShowEditor(true);
    setEditing(null);
    setForm({ ...EMPTY_FORM, level: user?.role || "L5" });
    setNotice("");
    setError("");
  }

  function startEdit(role) {
    setShowEditor(true);
    setEditing(role);
    setForm({
      name: role.name,
      level: role.level,
      description: role.description || "",
      permissions: [...(role.permissions || [])],
      is_active: role.is_active,
    });
    setNotice("");
    setError("");
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
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim(),
        permissions: form.permissions,
        is_active: form.is_active,
      };
      if (editing) await updateRole(editing.id, payload);
      else await createRole({ ...payload, level: form.level });
      setEditing(null);
      setShowEditor(false);
      setForm(EMPTY_FORM);
      setNotice("Rol guardado correctamente.");
      await refresh();
    } catch (requestError) {
      setError(requestError.userMessage || requestError.response?.data?.detail || "No se pudo guardar el rol.");
    } finally {
      setSaving(false);
    }
  }

  async function removeRole(role) {
    if (!window.confirm(`¿Eliminar el rol “${role.name}”? Se conservará su registro de auditoría.`)) return;
    setError("");
    try {
      await deleteRole(role.id);
      setNotice("Rol eliminado; su historial se conserva.");
      await refresh();
    } catch (requestError) {
      setError(requestError.userMessage || requestError.response?.data?.detail || "No se pudo eliminar el rol.");
    }
  }

  async function toggleActive(role) {
    const next = !role.is_active;
    if (role.level === "L1" && !next) return;
    setError("");
    try {
      await updateRole(role.id, { is_active: next });
      setNotice(next ? "Rol activado." : "Rol desactivado.");
      await refresh();
    } catch (requestError) {
      setError(requestError.userMessage || requestError.response?.data?.detail || "No se pudo cambiar el estado del rol.");
    }
  }

  return (
    <main style={{ display: "grid", gap: 20, maxWidth: 1200, margin: "0 auto", color: "white" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ color: "white", margin: 0, fontFamily: "'Rajdhani', sans-serif", fontSize: 28, letterSpacing: ".04em" }}>Roles y permisos</h1>
          <p style={{ color: "#9aa5bb", margin: "6px 0 0" }}>Roles organizacionales asociados a los niveles funcionales fijos L1–L5.</p>
        </div>
        {mayCreate && <Button type="button" onClick={startCreate}>Nuevo rol</Button>}
      </header>

      {error && <div role="alert" style={{ ...PANEL_STYLE, borderColor: "rgba(255,51,102,.4)", color: "#ff8ba5" }}>{error}</div>}
      {notice && <div role="status" style={{ ...PANEL_STYLE, borderColor: "rgba(63,229,229,.28)", color: "#3fe5e5" }}>{notice}</div>}

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }} aria-label="Niveles organizacionales">
        {["L1", "L2", "L3", "L4", "L5"].map((level) => {
          const role = roles.find((item) => item.level === level);
          return (
            <article key={level} style={{ ...PANEL_STYLE, padding: 14, display: "flex", alignItems: "center", gap: 12 }}>
              <LevelMark level={level} size={34} />
              <div style={{ minWidth: 0 }}>
                <strong style={{ display: "block", color: "white", fontFamily: "'Rajdhani', sans-serif", fontSize: 16 }}>{role?.name || `Nivel ${level}`}</strong>
                <span style={{ color: "#9aa5bb", fontSize: 12 }}>{role ? `${role.collaborators_count} colaboradores` : "Sin rol asignado"}</span>
              </div>
            </article>
          );
        })}
      </section>

      <section style={PANEL_STYLE} aria-label="Roles existentes">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
          <div>
            <h2 style={{ margin: 0, color: "white", fontFamily: "'Rajdhani', sans-serif", fontSize: 20 }}>Roles registrados</h2>
            <p style={{ margin: "4px 0 0", color: "#9aa5bb", fontSize: 13 }}>Los permisos configurables solo reducen las capacidades permitidas para cada nivel.</p>
          </div>
          <Badge variant="cyan" dot={false}>{loading ? "Cargando" : `${roles.length} roles`}</Badge>
        </div>
        <Table isLoading={loading} aria-label="Tabla de roles y permisos">
          <Table.Head>
            <Table.Row>
              <Table.HeadCell>Nivel</Table.HeadCell>
              <Table.HeadCell>Rol</Table.HeadCell>
              <Table.HeadCell>Estado</Table.HeadCell>
              <Table.HeadCell>Permisos habilitados</Table.HeadCell>
              <Table.HeadCell>Colaboradores</Table.HeadCell>
              {(mayEdit || mayDelete) && <Table.HeadCell>Acciones</Table.HeadCell>}
            </Table.Row>
          </Table.Head>
          <Table.Body>
            {!loading && roles.length === 0 ? <Table.Empty colSpan={(mayEdit || mayDelete) ? 6 : 5} message="No existen roles registrados." /> : roles.map((role, index) => (
              <Table.Row key={role.id} index={index}>
                <Table.Cell><LevelMark level={role.level} size={36} /></Table.Cell>
                <Table.Cell>
                  <strong style={{ color: "white", fontWeight: 600 }}>{role.name}</strong>
                  {role.description && <p style={{ color: "#9aa5bb", margin: "4px 0 0", fontSize: 12, maxWidth: 320 }}>{role.description}</p>}
                </Table.Cell>
                <Table.Cell><Badge status={role.is_active ? "activo" : "inactivo"} /></Table.Cell>
                <Table.Cell style={{ minWidth: 240 }}>
                  {role.permissions?.length ? (
                    <details>
                      <summary style={{ color: "#3fe5e5", cursor: "pointer", fontSize: 13 }}>
                        Consultar {role.permissions.length} capacidades
                      </summary>
                      <div style={{ display: "grid", gap: 8, marginTop: 8, minWidth: 230, maxWidth: 360, whiteSpace: "normal" }}>
                        {Object.entries(groupPermissionsByModule(role.permissions)).map(([module, permissions]) => (
                          <section key={module} aria-label={module}>
                            <strong style={{ display: "block", color: "#cbd5e1", fontSize: 12, marginBottom: 4 }}>{module}</strong>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                              {permissions.map((permission) => <Badge key={permission} variant="gray" dot={false}>{permissionActionLabel(permission)}</Badge>)}
                            </div>
                          </section>
                        ))}
                      </div>
                    </details>
                  ) : <span style={{ color: "#9aa5bb" }}>Sin capacidades adicionales</span>}
                </Table.Cell>
                <Table.Cell><span style={{ fontFamily: "'Share Tech Mono', monospace", color: "#c5cdd8" }}>{role.collaborators_count}</span></Table.Cell>
                {(mayEdit || mayDelete) && <Table.Cell>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 7, minWidth: 190 }}>
                    {mayEdit && <Button type="button" variant="secondary" size="sm" onClick={() => startEdit(role)}>Editar</Button>}
                    {mayEdit && role.level !== "L1" && <Button type="button" variant="ghost" size="sm" onClick={() => toggleActive(role)}>{role.is_active ? "Desactivar" : "Activar"}</Button>}
                    {mayDelete && role.level !== "L1" && role.collaborators_count === 0 && <Button type="button" variant="danger" size="sm" onClick={() => removeRole(role)}>Eliminar</Button>}
                  </div>
                </Table.Cell>}
              </Table.Row>
            ))}
          </Table.Body>
        </Table>
      </section>

      {showEditor && (editing ? mayEdit : mayCreate) && (
        <form onSubmit={saveRole} style={{ ...PANEL_STYLE, display: "grid", gap: 16 }}>
          <header>
            <h2 ref={editorHeadingRef} tabIndex={-1} style={{ margin: 0, color: "white", fontFamily: "'Rajdhani', sans-serif", fontSize: 22, outlineColor: "#3fe5e5" }}>{editing ? `Editar ${editing.name}` : "Crear rol organizacional"}</h2>
            <p style={{ color: "#9aa5bb", margin: "4px 0 0", fontSize: 13 }}>El nivel funcional es fijo; los permisos seleccionados se validan también en el servidor.</p>
          </header>
          <label style={{ display: "grid", gap: 6, color: "#cbd5e1" }}>Nombre
            <input style={FIELD_STYLE} required minLength={2} maxLength={50} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          </label>
          <label style={{ display: "grid", gap: 6, color: "#cbd5e1" }}>Nivel funcional
            <select style={FIELD_STYLE} value={form.level} disabled={Boolean(editing)} onChange={(event) => setForm({ ...form, level: event.target.value, permissions: [] })}>
              {["L1", "L2", "L3", "L4", "L5"].map((level) => <option key={level} value={level}>{level}</option>)}
            </select>
          </label>
          <label style={{ display: "grid", gap: 6, color: "#cbd5e1" }}>Descripción
            <textarea style={{ ...FIELD_STYLE, minHeight: 84, resize: "vertical" }} maxLength={1000} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
          </label>
          {editing && editing.level !== "L1" && <label style={{ display: "flex", gap: 8, alignItems: "center", color: "#cbd5e1" }}><input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} /> Rol activo</label>}
          <fieldset disabled={Boolean(editing && !editing.permissions_editable)} style={{ border: "1px solid rgba(63,229,229,.2)", borderRadius: 8, display: "grid", gap: 8, padding: 14 }}>
            <legend style={{ padding: "0 6px", color: "#3fe5e5" }}>Permisos disponibles para {form.level}</legend>
            {editing && !editing.permissions_editable && <p style={{ margin: 0, color: "#9aa5bb" }}>Los permisos del rol L1 existente se conservan; aquí solo se editan nombre y descripción.</p>}
            {levelPermissions.length === 0 ? <p style={{ margin: 0, color: "#9aa5bb" }}>Sin capacidades disponibles para este nivel.</p> : Object.entries(groupPermissionsByModule(levelPermissions.map((item) => item.key))).map(([module, permissions]) => (
              <section key={module} style={{ display: "grid", gap: 5, padding: "8px 0", borderTop: "1px solid rgba(255,255,255,.06)" }}>
                <strong style={{ color: "#cbd5e1", fontSize: 13 }}>{module}</strong>
                {permissions.map((key) => (
                  <label key={key} style={{ display: "flex", gap: 8, alignItems: "flex-start", color: "#cbd5e1" }}>
                    <input type="checkbox" checked={form.permissions.includes(key)} onChange={() => togglePermission(key)} />
                    <span>{permissionActionLabel(key)}</span>
                  </label>
                ))}
              </section>
            ))}
          </fieldset>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, flexWrap: "wrap" }}>
            <Button type="button" variant="secondary" disabled={saving} onClick={() => { setEditing(null); setShowEditor(false); setForm(EMPTY_FORM); }}>Cancelar</Button>
            <Button type="submit" isLoading={saving}>{saving ? "Guardando…" : "Guardar"}</Button>
          </div>
        </form>
      )}
    </main>
  );
}
