import { useMemo, useState } from "react";

export default function ActiveServicesList({ services = [], onClientClick }) {
  const [query, setQuery] = useState("");
  const visible = useMemo(() => {
    const term = query.trim().toLocaleLowerCase("es-PE");
    if (!term) return services;
    return services.filter((item) =>
      [item.name, item.cupe, item.web_type_name, item.service_name, ...(item.features || [])]
        .some((value) => String(value || "").toLocaleLowerCase("es-PE").includes(term)),
    );
  }, [services, query]);

  return <section style={{ background: "#111427", border: "1px solid rgba(63,229,229,0.12)", borderRadius: 12, padding: 20 }}>
    <h3 style={{ color: "#3fe5e5", marginTop: 0 }}>Servicios activos</h3>
    <input aria-label="Buscar servicios activos" placeholder="Buscar por nombre, CUPE o tipo de web" value={query} onChange={(event) => setQuery(event.target.value)} style={{ width: "100%", boxSizing: "border-box", padding: 9, marginBottom: 10, color: "white", background: "#0b0d1a", border: "1px solid #34394a", borderRadius: 6 }} />
    {visible.length === 0 ? <p style={{ color: "#8892a4" }}>{services.length ? "No se encontraron coincidencias" : "Aún no hay servicios activos en el sistema"}</p> : <div style={{ maxHeight: 400, overflowY: "auto" }}>
      {visible.map((item) => <article key={item.service_id} onClick={() => onClientClick(item.client_id)} style={{ borderTop: "1px solid #34394a", padding: "12px 4px", cursor: "pointer" }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><strong>{item.name}</strong><span style={{ color: "#3fe5e5" }}>{item.web_type_name || item.service_name}</span></div>
        <small style={{ color: "#8892a4" }}>{item.cupe || "Sin CUPE"} · {item.service_name}</small>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>{(item.features || []).map((feature) => <span key={feature} style={{ border: "1px solid #8235f2", borderRadius: 12, padding: "2px 8px", fontSize: 11 }}>{feature}</span>)}</div>
      </article>)}
    </div>}
  </section>;
}
