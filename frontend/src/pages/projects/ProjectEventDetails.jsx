import { fieldLabels, valueLabels } from "./projectEventLabels";


function humanizeKey(key) {
  return String(key)
    .replaceAll("_", " ")
    .replace(/\b\p{L}/gu, (letter) => letter.toLocaleUpperCase());
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function EventValue({ field, value }) {
  if (value === null || value === undefined || value === "") return <span>—</span>;
  if (typeof value === "boolean") return <span>{value ? "Sí" : "No"}</span>;
  if (typeof value === "number") return <span>{value}</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span>Sin elementos</span>;
    if (value.every((item) => item === null || ["string", "number", "boolean"].includes(typeof item))) {
      return <ul className="project-event-value-list">{value.map((item, index) => <li key={`${index}-${String(item)}`}><EventValue field={field} value={item} /></li>)}</ul>;
    }
    return <div className="project-event-nested-list">{value.map((item, index) => <article className="project-event-nested-item" key={index}>
      {item && typeof item === "object" ? <EventFields data={item} /> : <EventValue field={field} value={item} />}
    </article>)}</div>;
  }
  if (typeof value === "object") return <EventFields data={value} />;
  if (typeof value === "string") {
    const display = valueLabels[field]?.[value] || (field.endsWith("_at") ? formatDate(value) : value);
    return <span className="project-event-value">{display}</span>;
  }
  return <span>{String(value)}</span>;
}

function EventFields({ data }) {
  const entries = Object.entries(data || {});
  if (!entries.length) return <span>Sin datos adicionales</span>;
  return <dl className="project-event-fields">
    {entries.map(([key, value]) => <div className="project-event-field" key={key}>
      <dt>{fieldLabels[key] || humanizeKey(key)}</dt>
      <dd><EventValue field={key} value={value} /></dd>
    </div>)}
  </dl>;
}

export function ProjectEventData({ data, label = "Ver datos de la actuación" }) {
  if (!data || typeof data !== "object" || Object.keys(data).length === 0) return null;
  return <details className="project-event-data">
    <summary>{label}</summary>
    <EventFields data={data} />
  </details>;
}

export function ProjectTimeline({ events, labels = {} }) {
  if (!events?.length) return <p className="project-muted">Sin actuaciones registradas.</p>;
  return <ol className="project-timeline">
    {events.map((event, index) => <li className="project-timeline-event" key={`${event.event_type}-${event.id || index}`}>
      <article className="project-event-card">
        <header className="project-event-heading">
          <strong>{labels[event.event_type] || humanizeKey(event.event_type)}</strong>
          <span>{event.actor_name || "Actor no disponible"}</span>
          <time dateTime={event.occurred_at}>{formatDate(event.occurred_at)}</time>
        </header>
        {event.reason && <p><strong>Motivo o decisión:</strong> {event.reason}</p>}
        {event.evidence && <p><strong>Evidencia:</strong> {event.evidence}</p>}
        {event.effective_at && <p><strong>Fecha efectiva:</strong> {formatDate(event.effective_at)}</p>}
        <ProjectEventData data={event.data} />
      </article>
    </li>)}
  </ol>;
}
