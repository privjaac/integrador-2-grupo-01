// ==============================================================================
// DASHBOARDPAGE.JSX v4
// Cambios:
//   - Gráficos de línea a ancho completo en su cuadrante
//   - Eje Y dinámico con ticks limpios
//   - Filtros por año Y mes para cada gráfico de línea
//   - Datos multi-año (agrega meses de todos los años disponibles)
//   - Mocks ampliados → datos reales en todos los gráficos
// ==============================================================================

import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { getClients } from "../../api/clients";
import { getCollaborators } from "../../api/users";
import { formatPrice } from "../../utils/formatPrice";
import { formatDate } from "../../utils/formatDate";
import Badge from "../../components/ui/Badge";
import LoadingSpinner from "../../components/ui/LoadingSpinner";

const MONTHS_SHORT = [
  "Ene",
  "Feb",
  "Mar",
  "Abr",
  "May",
  "Jun",
  "Jul",
  "Ago",
  "Sep",
  "Oct",
  "Nov",
  "Dic",
];
const MONTHS_FULL = [
  "Enero",
  "Febrero",
  "Marzo",
  "Abril",
  "Mayo",
  "Junio",
  "Julio",
  "Agosto",
  "Septiembre",
  "Octubre",
  "Noviembre",
  "Diciembre",
];
const PIE_COLORS = [
  "#3fe5e5",
  "#8235f2",
  "#4540d9",
  "#ffb800",
  "#00ff88",
  "#ff3366",
  "#00c8ff",
  "#f97316",
  "#a855f7",
  "#06b6d4",
];

// ── UTILIDADES EJE Y ─────────────────────────────────────────────────────────

function getYTicks(maxVal) {
  if (maxVal === 0) return [0, 1, 2, 3];
  const target = 5;
  const rawStep = maxVal / target;
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const niceSteps = [1, 2, 2.5, 5, 10];
  const step =
    niceSteps.map((s) => s * mag).find((s) => s >= rawStep) || rawStep;
  const ticks = [];
  for (let i = 0; i * step <= maxVal * 1.3; i++)
    ticks.push(Math.round(i * step * 100) / 100);
  return ticks;
}

function fmtY(v, isPrice) {
  if (isPrice) {
    if (v >= 1000000) return `S/${(v / 1000000).toFixed(1)}M`;
    if (v >= 1000) return `S/${(v / 1000).toFixed(0)}k`;
    return `S/${v}`;
  }
  return String(Math.round(v));
}

// ── COMPONENTES BASE ──────────────────────────────────────────────────────────

function SectionTitle({ children }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.75rem",
        marginBottom: "1rem",
      }}
    >
      <h3
        style={{
          fontFamily: "'Share Tech Mono', monospace",
          fontSize: "11px",
          fontWeight: 700,
          color: "#3fe5e5",
          textTransform: "uppercase",
          letterSpacing: "0.12em",
          margin: 0,
        }}
      >
        {children}
      </h3>
      <div
        style={{
          flex: 1,
          height: "1px",
          background:
            "linear-gradient(90deg, rgba(63,229,229,0.3), transparent)",
        }}
      />
    </div>
  );
}

function KpiCard({ label, value, color = "#3fe5e5", sub }) {
  return (
    <div
      style={{
        backgroundColor: "#0b0d1a",
        border: `1px solid ${color}22`,
        borderRadius: "0.75rem",
        padding: "1.25rem 1.5rem",
        borderTop: `2px solid ${color}`,
      }}
    >
      <p
        style={{
          fontFamily: "'Share Tech Mono', monospace",
          fontSize: "9px",
          color: "#8892a4",
          letterSpacing: "0.15em",
          textTransform: "uppercase",
          margin: "0 0 0.5rem 0",
        }}
      >
        {label}
      </p>
      <p
        style={{
          fontFamily: "'Orbitron', monospace",
          fontSize: "26px",
          fontWeight: 700,
          color,
          margin: 0,
          lineHeight: 1,
        }}
      >
        {value}
      </p>
      {sub && (
        <p
          style={{
            fontFamily: "'Rajdhani', sans-serif",
            fontSize: "12px",
            color: "#8892a4",
            margin: "0.375rem 0 0 0",
          }}
        >
          {sub}
        </p>
      )}
    </div>
  );
}

// ── GRÁFICO DE TORTA ──────────────────────────────────────────────────────────

function PieChart({ data, size = 160 }) {
  const [order, setOrder] = useState("desc");

  const sorted = useMemo(
    () =>
      [...data].sort((a, b) =>
        order === "desc" ? b.value - a.value : a.value - b.value,
      ),
    [data, order],
  );

  // Torta muestra solo top 6, leyenda muestra todos con scroll
  const top6 = sorted.slice(0, 6);
  const total = sorted.reduce((s, d) => s + d.value, 0);

  if (!sorted.length || total === 0)
    return (
      <div
        style={{
          height: size,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#8892a4",
          fontSize: "13px",
          fontFamily: "'Rajdhani', sans-serif",
        }}
      >
        Sin datos
      </div>
    );

  const cx = size / 2,
    cy = size / 2,
    r = size / 2 - 10;
  let startAngle = -Math.PI / 2;

  const slices = top6.map((d) => {
    const angle = (d.value / total) * 2 * Math.PI;
    const end = startAngle + angle;
    const x1 = cx + r * Math.cos(startAngle),
      y1 = cy + r * Math.sin(startAngle);
    const x2 = cx + r * Math.cos(end),
      y2 = cy + r * Math.sin(end);
    const mid = startAngle + angle / 2;
    const lx = cx + r * 0.65 * Math.cos(mid),
      ly = cy + r * 0.65 * Math.sin(mid);
    startAngle = end;
    return {
      ...d,
      path: `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${angle > Math.PI ? 1 : 0} 1 ${x2} ${y2} Z`,
      lx,
      ly,
      pct: Math.round((d.value / total) * 100),
    };
  });

  // Si hay más de 6, agrupa el resto como "Otros"
  if (sorted.length > 6) {
    const othersVal = sorted.slice(6).reduce((s, d) => s + d.value, 0);
    const angle = (othersVal / total) * 2 * Math.PI;
    const end = startAngle + angle;
    const x1 = cx + r * Math.cos(startAngle),
      y1 = cy + r * Math.sin(startAngle);
    const x2 = cx + r * Math.cos(end),
      y2 = cy + r * Math.sin(end);
    const mid = startAngle + angle / 2;
    const lx = cx + r * 0.65 * Math.cos(mid),
      ly = cy + r * 0.65 * Math.sin(mid);
    slices.push({
      label: "Otros",
      value: othersVal,
      color: "#374151",
      path: `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${angle > Math.PI ? 1 : 0} 1 ${x2} ${y2} Z`,
      lx,
      ly,
      pct: Math.round((othersVal / total) * 100),
    });
  }

  return (
    <div>
      {/* Botón de orden */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "0.875rem",
          paddingBottom: "0.75rem",
          borderBottom: "1px solid rgba(63,229,229,0.08)",
        }}
      >
        <span
          style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: "9px",
            color: "#8892a4",
          }}
        >
          {sorted.length} tipo{sorted.length !== 1 ? "s" : ""} · top 6 en torta
        </span>
        <button
          onClick={() => setOrder((o) => (o === "desc" ? "asc" : "desc"))}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.375rem",
            padding: "0.375rem 0.875rem",
            borderRadius: "0.375rem",
            backgroundColor: "rgba(63,229,229,0.08)",
            border: "1px solid rgba(63,229,229,0.25)",
            color: "#3fe5e5",
            fontSize: "11px",
            fontFamily: "'Share Tech Mono', monospace",
            cursor: "pointer",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.backgroundColor = "rgba(63,229,229,0.15)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.backgroundColor = "rgba(63,229,229,0.08)")
          }
        >
          {order === "desc" ? "↓ Mayor a menor" : "↑ Menor a mayor"}
        </button>
      </div>

      <div
        style={{ display: "flex", alignItems: "flex-start", gap: "1.25rem" }}
      >
        {/* Torta */}
        <svg width={size} height={size} style={{ flexShrink: 0 }}>
          {slices.map((s, i) => (
            <g key={i}>
              <path
                d={s.path}
                fill={s.color}
                opacity={0.9}
                stroke="#111427"
                strokeWidth="2"
              />
              {s.pct > 5 && (
                <text
                  x={s.lx}
                  y={s.ly}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  style={{
                    fontFamily: "'Orbitron', monospace",
                    fontSize: "9px",
                    fontWeight: 700,
                    fill: "#05060f",
                  }}
                >
                  {s.pct}%
                </text>
              )}
            </g>
          ))}
          <circle cx={cx} cy={cy} r={r * 0.38} fill="#111427" />
          <text
            x={cx}
            y={cy - 7}
            textAnchor="middle"
            style={{
              fontFamily: "'Orbitron', monospace",
              fontSize: "14px",
              fontWeight: 700,
              fill: "white",
            }}
          >
            {total}
          </text>
          <text
            x={cx}
            y={cy + 9}
            textAnchor="middle"
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: "7px",
              fill: "#8892a4",
            }}
          >
            TOTAL
          </text>
        </svg>

        {/* Leyenda con scroll — muestra TODOS ordenados */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: "0.35rem",
            maxHeight: `${size}px`,
            overflowY: "auto",
            overflowX: "hidden",
            scrollbarWidth: "thin",
            scrollbarColor: "rgba(63,229,229,0.3) transparent",
            paddingRight: "4px",
          }}
        >
          {sorted.map((s, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                flexShrink: 0,
              }}
            >
              <span
                style={{
                  fontFamily: "'Share Tech Mono', monospace",
                  fontSize: "9px",
                  color: "#8892a4",
                  width: "16px",
                  textAlign: "right",
                  flexShrink: 0,
                }}
              >
                #{i + 1}
              </span>
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "2px",
                  backgroundColor: s.color || "#374151",
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontFamily: "'Rajdhani', sans-serif",
                  fontSize: "12px",
                  color: "#c5cdd8",
                  flex: 1,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {s.label}
              </span>
              <span
                style={{
                  fontFamily: "'Share Tech Mono', monospace",
                  fontSize: "11px",
                  color: s.color || "#8892a4",
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                {s.value}
              </span>
            </div>
          ))}
          {sorted.length > 6 && (
            <div
              style={{
                textAlign: "center",
                padding: "0.25rem 0",
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "9px",
                color: "rgba(63,229,229,0.4)",
                letterSpacing: "0.08em",
              }}
            >
              ↑↓ scroll
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── GRÁFICO DE LÍNEA — ANCHO COMPLETO CON EJE Y ───────────────────────────────

function LineChart({
  data,
  color = "#3fe5e5",
  height = 180,
  isPrice = false,
  chartId = "lc",
}) {
  if (!data?.length || data.length < 2)
    return (
      <div
        style={{
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#8892a4",
          fontSize: "13px",
          fontFamily: "'Rajdhani', sans-serif",
        }}
      >
        Sin datos suficientes
      </div>
    );

  const values = data.map((d) => d.value);
  const maxVal = Math.max(...values);
  const ticks = getYTicks(maxVal);
  const yMax = ticks[ticks.length - 1] || 1;

  // Dimensiones viewBox (porcentuales para que se estire con width:100%)
  const VW = 600,
    VH = height;
  const padL = isPrice ? 60 : 36,
    padR = 16,
    padT = 12,
    padB = 28;
  const cW = VW - padL - padR,
    cH = VH - padT - padB;

  const pts = data.map((d, i) => ({
    x: padL + (i / (data.length - 1)) * cW,
    y: padT + cH - (d.value / yMax) * cH,
    ...d,
  }));

  const pathD = pts
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
    .join(" ");
  const areaD = `${pathD} L ${pts[pts.length - 1].x} ${padT + cH} L ${pts[0].x} ${padT + cH} Z`;
  const step = Math.max(1, Math.ceil(data.length / 8));
  const xLbls = data.filter((_, i) => i % step === 0 || i === data.length - 1);

  return (
    <svg
      viewBox={`0 0 ${VW} ${VH}`}
      style={{ width: "100%", height, display: "block" }}
    >
      <defs>
        <linearGradient id={`g_${chartId}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.2" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* Grid + eje Y */}
      {ticks.map((tick, i) => {
        const y = padT + cH - (tick / yMax) * cH;
        return (
          <g key={i}>
            <line
              x1={padL}
              y1={y}
              x2={padL + cW}
              y2={y}
              stroke="rgba(255,255,255,0.05)"
              strokeWidth="0.8"
            />
            <text
              x={padL - 5}
              y={y}
              textAnchor="end"
              dominantBaseline="middle"
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "10px",
                fill: "#8892a4",
              }}
            >
              {fmtY(tick, isPrice)}
            </text>
          </g>
        );
      })}

      {/* Área */}
      <path d={areaD} fill={`url(#g_${chartId})`} />
      {/* Línea */}
      <path
        d={pathD}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Puntos */}
      {pts.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="3" fill={color} />
      ))}

      {/* Eje X */}
      <line
        x1={padL}
        y1={padT + cH}
        x2={padL + cW}
        y2={padT + cH}
        stroke="rgba(255,255,255,0.1)"
        strokeWidth="1"
      />
      {xLbls.map((d, i) => {
        const idx = data.indexOf(d);
        const x = padL + (idx / (data.length - 1)) * cW;
        return (
          <text
            key={i}
            x={x}
            y={padT + cH + 16}
            textAnchor="middle"
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: "9px",
              fill: "#8892a4",
            }}
          >
            {d.label}
          </text>
        );
      })}
    </svg>
  );
}

// ── FILTRO DE AÑO Y MES PARA GRÁFICOS ────────────────────────────────────────

function ChartFilter({
  years,
  selectedYear,
  selectedMonthFrom,
  selectedMonthTo,
  onChange,
}) {
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "0.5rem",
        alignItems: "flex-end",
        marginBottom: "0.875rem",
        padding: "0.625rem 0.875rem",
        backgroundColor: "rgba(63,229,229,0.03)",
        border: "1px solid rgba(63,229,229,0.1)",
        borderRadius: "0.375rem",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
        <label
          style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: "8px",
            color: "#3fe5e5",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          Año
        </label>
        <select
          value={selectedYear}
          onChange={(e) => onChange("year", e.target.value)}
          style={{
            padding: "0.35rem 0.625rem",
            borderRadius: "0.25rem",
            fontSize: "12px",
            color: "white",
            backgroundColor: "#1a1d30",
            border: "1px solid rgba(63,229,229,0.2)",
            outline: "none",
            fontFamily: "'Rajdhani', sans-serif",
            cursor: "pointer",
          }}
        >
          <option value="all">Todos</option>
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
        <label
          style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: "8px",
            color: "#8892a4",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          Desde mes
        </label>
        <select
          value={selectedMonthFrom}
          onChange={(e) => onChange("from", Number(e.target.value))}
          style={{
            padding: "0.35rem 0.625rem",
            borderRadius: "0.25rem",
            fontSize: "12px",
            color: "white",
            backgroundColor: "#1a1d30",
            border: "1px solid rgba(63,229,229,0.2)",
            outline: "none",
            fontFamily: "'Rajdhani', sans-serif",
            cursor: "pointer",
            minWidth: "100px",
          }}
        >
          {MONTHS_FULL.map((m, i) => (
            <option key={i} value={i}>
              {m}
            </option>
          ))}
        </select>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
        <label
          style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: "8px",
            color: "#8892a4",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          Hasta mes
        </label>
        <select
          value={selectedMonthTo}
          onChange={(e) => onChange("to", Number(e.target.value))}
          style={{
            padding: "0.35rem 0.625rem",
            borderRadius: "0.25rem",
            fontSize: "12px",
            color: "white",
            backgroundColor: "#1a1d30",
            border: "1px solid rgba(63,229,229,0.2)",
            outline: "none",
            fontFamily: "'Rajdhani', sans-serif",
            cursor: "pointer",
            minWidth: "100px",
          }}
        >
          {MONTHS_FULL.map((m, i) => (
            <option key={i} value={i}>
              {m}
            </option>
          ))}
        </select>
      </div>
      <button
        onClick={() => onChange("reset")}
        style={{
          padding: "0.35rem 0.75rem",
          borderRadius: "0.25rem",
          fontSize: "11px",
          fontFamily: "'Rajdhani', sans-serif",
          backgroundColor: "transparent",
          border: "1px solid rgba(255,51,102,0.3)",
          color: "#ff3366",
          cursor: "pointer",
        }}
      >
        Reset
      </button>
    </div>
  );
}

// ── LISTA ORDENABLE ───────────────────────────────────────────────────────────

function BarList({ data, color = "#3fe5e5" }) {
  const [order, setOrder] = useState("desc");
  const sorted = useMemo(
    () =>
      [...data]
        .sort((a, b) =>
          order === "desc" ? b.value - a.value : a.value - b.value,
        )
        .slice(0, 10),
    [data, order],
  );
  const maxVal =
    sorted.length > 0 ? Math.max(...sorted.map((d) => d.value)) : 1;
  return (
    <div>
      {/* Botón de orden — siempre visible */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "0.875rem",
          paddingBottom: "0.75rem",
          borderBottom: "1px solid rgba(63,229,229,0.08)",
        }}
      >
        <span
          style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: "9px",
            color: "#8892a4",
            letterSpacing: "0.1em",
          }}
        >
          {sorted.length} tipo{sorted.length !== 1 ? "s" : ""} de web
        </span>
        <button
          onClick={() => setOrder((o) => (o === "desc" ? "asc" : "desc"))}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.375rem",
            padding: "0.375rem 0.875rem",
            borderRadius: "0.375rem",
            backgroundColor: "rgba(63,229,229,0.08)",
            border: "1px solid rgba(63,229,229,0.25)",
            color: "#3fe5e5",
            fontSize: "11px",
            fontFamily: "'Share Tech Mono', monospace",
            cursor: "pointer",
            letterSpacing: "0.05em",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.backgroundColor = "rgba(63,229,229,0.15)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.backgroundColor = "rgba(63,229,229,0.08)")
          }
        >
          {order === "desc" ? "↓ Mayor a menor" : "↑ Menor a mayor"}
        </button>
      </div>
      {sorted.length === 0 ? (
        <p
          style={{
            color: "#8892a4",
            fontSize: "13px",
            textAlign: "center",
            fontFamily: "'Rajdhani', sans-serif",
            padding: "1rem 0",
          }}
        >
          Sin datos en el período seleccionado
        </p>
      ) : (
        <div
          style={{ display: "flex", flexDirection: "column", gap: "0.625rem" }}
        >
          {sorted.map((item, i) => (
            <div
              key={i}
              style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}
            >
              <span
                style={{
                  fontFamily: "'Share Tech Mono', monospace",
                  fontSize: "10px",
                  color: "#3fe5e5",
                  width: "20px",
                  textAlign: "right",
                  flexShrink: 0,
                }}
              >
                #{i + 1}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: "3px",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "'Rajdhani', sans-serif",
                      fontSize: "13px",
                      color: "white",
                      fontWeight: 500,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {item.label}
                  </span>
                  <span
                    style={{
                      fontFamily: "'Share Tech Mono', monospace",
                      fontSize: "12px",
                      color,
                      flexShrink: 0,
                      marginLeft: "0.5rem",
                      fontWeight: 700,
                    }}
                  >
                    {item.valueLabel || item.value}
                  </span>
                </div>
                <div
                  style={{
                    height: "5px",
                    borderRadius: "3px",
                    backgroundColor: "rgba(255,255,255,0.06)",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${(item.value / maxVal) * 100}%`,
                      backgroundColor: color,
                      borderRadius: "3px",
                      transition: "width 0.6s ease",
                      boxShadow: `0 0 6px ${color}60`,
                    }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── LISTA DE CLIENTES ─────────────────────────────────────────────────────────

function ClientList({ clients, navigate }) {
  const [order, setOrder] = useState("desc");
  const sorted = useMemo(
    () =>
      [...clients].sort((a, b) => {
        const da = new Date(a.registration_date || 0),
          db = new Date(b.registration_date || 0);
        return order === "desc" ? db - da : da - db;
      }),
    [clients, order],
  );

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          marginBottom: "0.75rem",
        }}
      >
        <button
          onClick={() => setOrder((o) => (o === "desc" ? "asc" : "desc"))}
          style={{
            padding: "0.375rem 0.75rem",
            borderRadius: "0.375rem",
            backgroundColor: "rgba(63,229,229,0.06)",
            border: "1px solid rgba(63,229,229,0.2)",
            color: "#3fe5e5",
            fontSize: "11px",
            fontFamily: "'Share Tech Mono', monospace",
            cursor: "pointer",
          }}
        >
          {order === "desc" ? "↓ Más nuevo primero" : "↑ Más antiguo primero"}
        </button>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid rgba(63,229,229,0.08)" }}>
              {["#", "CUPE", "Nombre", "Plan", "Estado", "Registro"].map(
                (h) => (
                  <th
                    key={h}
                    style={{
                      padding: "0.625rem 0.875rem",
                      textAlign: "left",
                      fontFamily: "'Share Tech Mono', monospace",
                      fontSize: "9px",
                      color: "#8892a4",
                      letterSpacing: "0.1em",
                      textTransform: "uppercase",
                      fontWeight: 400,
                    }}
                  >
                    {h}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {sorted.map((c, i) => (
              <tr
                key={c.id}
                onClick={() => navigate(`/clientes/${c.id}`)}
                style={{
                  borderBottom: "1px solid rgba(255,255,255,0.03)",
                  cursor: "pointer",
                  backgroundColor:
                    i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.015)",
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.backgroundColor =
                    "rgba(63,229,229,0.05)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.backgroundColor =
                    i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.015)")
                }
              >
                <td style={{ padding: "0.625rem 0.875rem" }}>
                  <span
                    style={{
                      fontFamily: "'Share Tech Mono', monospace",
                      fontSize: "10px",
                      color: "#8892a4",
                    }}
                  >
                    {i + 1}
                  </span>
                </td>
                <td style={{ padding: "0.625rem 0.875rem" }}>
                  <span
                    style={{
                      fontFamily: "'Share Tech Mono', monospace",
                      color: "#3fe5e5",
                      fontSize: "11px",
                    }}
                  >
                    {c.cupe}
                  </span>
                </td>
                <td style={{ padding: "0.625rem 0.875rem" }}>
                  <span
                    style={{
                      fontFamily: "'Rajdhani', sans-serif",
                      color: "white",
                      fontWeight: 600,
                      fontSize: "13px",
                    }}
                  >
                    {c.name}
                  </span>
                </td>
                <td style={{ padding: "0.625rem 0.875rem" }}>
                  <Badge status={c.plan} />
                </td>
                <td style={{ padding: "0.625rem 0.875rem" }}>
                  <Badge status={c.status} />
                </td>
                <td style={{ padding: "0.625rem 0.875rem" }}>
                  <span
                    style={{
                      fontFamily: "'Share Tech Mono', monospace",
                      color: "#8892a4",
                      fontSize: "11px",
                    }}
                  >
                    {formatDate(c.registration_date)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── COMPONENTE PRINCIPAL ──────────────────────────────────────────────────────

export default function DashboardPage() {
  const navigate = useNavigate();
  const [clients, setClients] = useState([]);
  const [collaborators, setCollaborators] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth();

  // Filtros globales
  const [gYear, setGYear] = useState(0); // 0 = todos los años
  const [gMonth, setGMonth] = useState(0);
  const [gFrom, setGFrom] = useState("");
  const [gTo, setGTo] = useState("");

  // Filtros gráfico clientes nuevos
  const [ncYear, setNcYear] = useState("all");
  const [ncFrom, setNcFrom] = useState(0);
  const [ncTo, setNcTo] = useState(11);

  // Filtros gráfico ingresos
  const [incYear, setIncYear] = useState("all");
  const [incFrom, setIncFrom] = useState(0);
  const [incTo, setIncTo] = useState(11);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      try {
        const [c, col] = await Promise.all([getClients(), getCollaborators()]);
        setClients(c.clients || c);
        setCollaborators(col);
      } catch {
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, []);

  // Años disponibles en los datos
  const availableYears = useMemo(() => {
    const years = new Set(
      clients
        .map((c) =>
          c.registration_date
            ? new Date(c.registration_date).getFullYear()
            : null,
        )
        .filter(Boolean),
    );
    return [...years].sort();
  }, [clients]);

  // Filtro global
  const filtered = useMemo(
    () =>
      clients.filter((c) => {
        const d = c.registration_date ? new Date(c.registration_date) : null;
        if (!d) return true;
        if (gFrom && d < new Date(gFrom)) return false;
        if (gTo && d > new Date(gTo)) return false;
        if (gYear && d.getFullYear() !== gYear) return false;
        if (gMonth && d.getMonth() + 1 !== gMonth) return false;
        return true;
      }),
    [clients, gYear, gMonth, gFrom, gTo],
  );

  // KPIs
  const kpis = useMemo(
    () => ({
      totalClientes: filtered.length,
      activos: filtered.filter((c) => c.status === "activo").length,
      desarrollo: filtered.filter((c) => c.status === "desarrollo").length,
      inactivos: filtered.filter((c) => c.status === "inactivo").length,
      alquilerActivo: filtered.filter(
        (c) => c.plan === "alquiler" && c.status === "activo",
      ).length,
      alquilerDesarrollo: filtered.filter(
        (c) => c.plan === "alquiler" && c.status === "desarrollo",
      ).length,
      alquilerInactivo: filtered.filter(
        (c) => c.plan === "alquiler" && c.status === "inactivo",
      ).length,
      ventaActivo: filtered.filter(
        (c) => c.plan === "venta" && c.status === "activo",
      ).length,
      ventaDesarrollo: filtered.filter(
        (c) => c.plan === "venta" && c.status === "desarrollo",
      ).length,
      ventaInactivo: filtered.filter(
        (c) => c.plan === "venta" && c.status === "inactivo",
      ).length,
      nuevosMes: filtered.filter((c) => {
        if (!c.registration_date) return false;
        const d = new Date(c.registration_date);
        return (
          d.getMonth() === now.getMonth() &&
          d.getFullYear() === now.getFullYear()
        );
      }).length,
      nuevosAnio: filtered.filter(
        (c) =>
          c.registration_date &&
          new Date(c.registration_date).getFullYear() === currentYear,
      ).length,
      colaboradoresActivos: collaborators.filter((c) => c.is_active).length,
      colaboradoresInactivos: collaborators.filter((c) => !c.is_active).length,
      colaboradoresTotal: collaborators.length,
    }),
    [filtered, collaborators],
  );

  // Ingresos KPIs
  const kpiIngresos = useMemo(() => {
    const mes = filtered
      .filter((c) => {
        if (!c.registration_date) return false;
        const d = new Date(c.registration_date);
        return (
          d.getMonth() === now.getMonth() &&
          d.getFullYear() === now.getFullYear()
        );
      })
      .reduce((s, c) => s + (parseFloat(c.total_price) || 0), 0);
    const anio = filtered
      .filter(
        (c) =>
          c.registration_date &&
          new Date(c.registration_date).getFullYear() === currentYear,
      )
      .reduce((s, c) => s + (parseFloat(c.total_price) || 0), 0);
    const meses = now.getMonth() + 1;
    return {
      mes,
      anio,
      proyectado: anio + (anio / (meses || 1)) * (12 - meses),
    };
  }, [filtered]);

  // Tortas
  const pieAlquilerEstado = useMemo(
    () =>
      [
        { label: "Activo", value: kpis.alquilerActivo, color: "#00ff88" },
        {
          label: "Desarrollo",
          value: kpis.alquilerDesarrollo,
          color: "#ffb800",
        },
        { label: "Inactivo", value: kpis.alquilerInactivo, color: "#ff3366" },
      ].filter((d) => d.value > 0),
    [kpis],
  );

  const pieVentaEstado = useMemo(
    () =>
      [
        { label: "Activo", value: kpis.ventaActivo, color: "#00ff88" },
        { label: "Desarrollo", value: kpis.ventaDesarrollo, color: "#ffb800" },
        { label: "Inactivo", value: kpis.ventaInactivo, color: "#ff3366" },
      ].filter((d) => d.value > 0),
    [kpis],
  );

  const pieVentasTipos = useMemo(() => {
    const count = {};
    filtered
      .filter((c) => c.plan === "venta")
      .forEach((c) => {
        const k = c.web_type_name || "Sin tipo";
        count[k] = (count[k] || 0) + 1;
      });
    return Object.entries(count)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([label, value], i) => ({
        label,
        value,
        color: PIE_COLORS[i % PIE_COLORS.length],
      }));
  }, [filtered]);

  const pieAlquilerTipos = useMemo(() => {
    const count = {};
    filtered
      .filter((c) => c.plan === "alquiler")
      .forEach((c) => {
        const k = c.web_type_name || "Sin tipo";
        count[k] = (count[k] || 0) + 1;
      });
    return Object.entries(count)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([label, value], i) => ({
        label,
        value,
        color: PIE_COLORS[i % PIE_COLORS.length],
      }));
  }, [filtered]);

  // Genera datos de línea con filtros de año y mes
  const buildMonthlyData = (yearFilter, fromMonth, toMonth, valueFn) => {
    const yearsToUse =
      yearFilter === "all" ? availableYears : [Number(yearFilter)];
    const result = [];
    yearsToUse.forEach((yr) => {
      for (let m = fromMonth; m <= toMonth; m++) {
        const label =
          availableYears.length > 1 || yearFilter === "all"
            ? `${MONTHS_SHORT[m]} ${String(yr).slice(2)}`
            : MONTHS_SHORT[m];
        const value = valueFn(yr, m);
        result.push({ label, value });
      }
    });
    return result;
  };

  const newClientsByMonth = useMemo(
    () =>
      buildMonthlyData(
        ncYear,
        ncFrom,
        ncTo,
        (yr, m) =>
          filtered.filter((c) => {
            if (!c.registration_date) return false;
            const d = new Date(c.registration_date);
            return d.getFullYear() === yr && d.getMonth() === m;
          }).length,
      ),
    [filtered, ncYear, ncFrom, ncTo, availableYears],
  );

  const incomeByMonth = useMemo(
    () =>
      buildMonthlyData(incYear, incFrom, incTo, (yr, m) =>
        filtered
          .filter((c) => {
            if (!c.registration_date) return false;
            const d = new Date(c.registration_date);
            return d.getFullYear() === yr && d.getMonth() === m;
          })
          .reduce((s, c) => s + (parseFloat(c.total_price) || 0), 0),
      ),
    [filtered, incYear, incFrom, incTo, availableYears],
  );

  // Top 10
  const top10Ventas = useMemo(() => {
    const count = {};
    filtered
      .filter((c) => c.plan === "venta")
      .forEach((c) => {
        const k = c.web_type_name || "Sin tipo";
        count[k] = (count[k] || 0) + 1;
      });
    return Object.entries(count).map(([label, value]) => ({
      label,
      value,
      valueLabel: `${value} ventas`,
    }));
  }, [filtered]);

  const top10Alquiler = useMemo(() => {
    const count = {};
    filtered
      .filter((c) => c.plan === "alquiler")
      .forEach((c) => {
        const k = c.web_type_name || "Sin tipo";
        count[k] = (count[k] || 0) + 1;
      });
    return Object.entries(count).map(([label, value]) => ({
      label,
      value,
      valueLabel: `${value} alquileres`,
    }));
  }, [filtered]);

  const retencion = useMemo(
    () =>
      filtered.length > 0
        ? Math.round((kpis.activos / filtered.length) * 100)
        : 0,
    [filtered, kpis],
  );

  const venc = useMemo(() => {
    const en5 = new Date(now);
    en5.setDate(en5.getDate() + 5);
    const en30 = new Date(now);
    en30.setDate(en30.getDate() + 30);
    return {
      v5: clients.filter(
        (c) =>
          c.next_payment_date &&
          new Date(c.next_payment_date) <= en5 &&
          new Date(c.next_payment_date) >= now,
      ),
      v30: clients.filter(
        (c) =>
          c.next_payment_date &&
          new Date(c.next_payment_date) <= en30 &&
          new Date(c.next_payment_date) >= now,
      ),
    };
  }, [clients]);

  const handleChartFilter = (which, field, val) => {
    if (which === "nc") {
      if (field === "year") setNcYear(val);
      else if (field === "from") setNcFrom(val);
      else if (field === "to") setNcTo(val);
      else {
        setNcYear("all");
        setNcFrom(0);
        setNcTo(11);
      }
    } else {
      if (field === "year") setIncYear(val);
      else if (field === "from") setIncFrom(val);
      else if (field === "to") setIncTo(val);
      else {
        setIncYear("all");
        setIncFrom(0);
        setIncTo(11);
      }
    }
  };

  const card = {
    backgroundColor: "#111427",
    border: "1px solid rgba(63,229,229,0.12)",
    borderRadius: "0.75rem",
    padding: "1.5rem",
  };

  if (isLoading)
    return <LoadingSpinner fullPage label="Cargando dashboard..." />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <h2
            style={{
              fontFamily: "'Rajdhani', sans-serif",
              fontSize: "1.25rem",
              fontWeight: 700,
              color: "white",
              letterSpacing: "0.05em",
              margin: 0,
            }}
          >
            Dashboard
          </h2>
          <p
            style={{
              color: "#8892a4",
              fontSize: "14px",
              margin: "0.25rem 0 0 0",
            }}
          >
            Resumen general · {filtered.length} registros en el período
          </p>
        </div>
        <p
          style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: "11px",
            color: "#3fe5e5",
            margin: 0,
          }}
        >
          {now.toLocaleDateString("es-PE", {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
          })}
        </p>
      </div>

      {/* Filtros globales */}
      <div style={{ ...card, padding: "1.25rem" }}>
        <p
          style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: "9px",
            color: "#3fe5e5",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            margin: "0 0 0.875rem 0",
          }}
        >
          Filtros globales — afectan todos los datos
        </p>

        {/* Indicador de modo activo */}
        {(gFrom || gTo) && (
          <div
            style={{
              marginBottom: "0.75rem",
              padding: "0.5rem 0.875rem",
              borderRadius: "0.375rem",
              backgroundColor: "rgba(255,184,0,0.06)",
              border: "1px solid rgba(255,184,0,0.25)",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
            }}
          >
            <span
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "9px",
                color: "#ffb800",
                letterSpacing: "0.1em",
              }}
            >
              ⚡ MODO RANGO DE FECHAS ACTIVO — filtro por mes bloqueado
            </span>
          </div>
        )}
        {gMonth > 0 && !gFrom && !gTo && (
          <div
            style={{
              marginBottom: "0.75rem",
              padding: "0.5rem 0.875rem",
              borderRadius: "0.375rem",
              backgroundColor: "rgba(63,229,229,0.06)",
              border: "1px solid rgba(63,229,229,0.25)",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
            }}
          >
            <span
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "9px",
                color: "#3fe5e5",
                letterSpacing: "0.1em",
              }}
            >
              ⚡ MODO MES ACTIVO — filtros de rango de fecha bloqueados
            </span>
          </div>
        )}

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "0.75rem",
            alignItems: "flex-end",
          }}
        >
          {/* Año — siempre activo */}
          <div
            style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}
          >
            <label
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "9px",
                color: "#8892a4",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              Año
            </label>
            <select
              value={gYear}
              onChange={(e) => setGYear(Number(e.target.value))}
              style={{
                padding: "0.5rem 0.875rem",
                borderRadius: "0.375rem",
                fontSize: "13px",
                color: "white",
                backgroundColor: "#1a1d30",
                border: "1px solid rgba(63,229,229,0.2)",
                outline: "none",
                fontFamily: "'Rajdhani', sans-serif",
                cursor: "pointer",
              }}
            >
              <option value={0}>Todos los años</option>
              {availableYears.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>

          {/* Mes — se bloquea si hay rango de fechas activo */}
          <div
            style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}
          >
            <label
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "9px",
                color: gFrom || gTo ? "rgba(136,146,164,0.35)" : "#8892a4",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              Mes {(gFrom || gTo) && "(bloqueado)"}
            </label>
            <select
              value={gMonth}
              onChange={(e) => {
                if (!gFrom && !gTo) setGMonth(Number(e.target.value));
              }}
              disabled={!!(gFrom || gTo)}
              style={{
                padding: "0.5rem 0.875rem",
                borderRadius: "0.375rem",
                fontSize: "13px",
                color:
                  gFrom || gTo
                    ? "rgba(136,146,164,0.35)"
                    : gMonth
                      ? "white"
                      : "#8892a4",
                backgroundColor:
                  gFrom || gTo ? "rgba(26,29,48,0.4)" : "#1a1d30",
                border: `1px solid ${gFrom || gTo ? "rgba(63,229,229,0.06)" : "rgba(63,229,229,0.2)"}`,
                outline: "none",
                fontFamily: "'Rajdhani', sans-serif",
                cursor: gFrom || gTo ? "not-allowed" : "pointer",
                minWidth: "130px",
                opacity: gFrom || gTo ? 0.4 : 1,
              }}
            >
              <option value={0}>Todos los meses</option>
              {MONTHS_FULL.map((m, i) => (
                <option key={i} value={i + 1}>
                  {m}
                </option>
              ))}
            </select>
          </div>

          {/* Separador */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              paddingBottom: "0.25rem",
            }}
          >
            <span
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "9px",
                color: "rgba(136,146,164,0.4)",
                letterSpacing: "0.1em",
              }}
            >
              — O —
            </span>
          </div>

          {/* Desde — se bloquea si hay mes activo */}
          <div
            style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}
          >
            <label
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "9px",
                color: gMonth > 0 ? "rgba(136,146,164,0.35)" : "#8892a4",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              Desde {gMonth > 0 && "(bloqueado)"}
            </label>
            <input
              type="date"
              value={gFrom}
              onChange={(e) => {
                if (!gMonth) {
                  setGFrom(e.target.value);
                }
              }}
              disabled={gMonth > 0}
              style={{
                padding: "0.5rem 0.875rem",
                borderRadius: "0.375rem",
                fontSize: "13px",
                color: gMonth > 0 ? "rgba(136,146,164,0.35)" : "white",
                backgroundColor: gMonth > 0 ? "rgba(26,29,48,0.4)" : "#1a1d30",
                border: `1px solid ${gMonth > 0 ? "rgba(63,229,229,0.06)" : "rgba(63,229,229,0.2)"}`,
                outline: "none",
                fontFamily: "'Rajdhani', sans-serif",
                cursor: gMonth > 0 ? "not-allowed" : "pointer",
                opacity: gMonth > 0 ? 0.4 : 1,
              }}
            />
          </div>

          {/* Hasta — se bloquea si hay mes activo */}
          <div
            style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}
          >
            <label
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "9px",
                color: gMonth > 0 ? "rgba(136,146,164,0.35)" : "#8892a4",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              Hasta {gMonth > 0 && "(bloqueado)"}
            </label>
            <input
              type="date"
              value={gTo}
              onChange={(e) => {
                if (!gMonth) {
                  setGTo(e.target.value);
                }
              }}
              disabled={gMonth > 0}
              style={{
                padding: "0.5rem 0.875rem",
                borderRadius: "0.375rem",
                fontSize: "13px",
                color: gMonth > 0 ? "rgba(136,146,164,0.35)" : "white",
                backgroundColor: gMonth > 0 ? "rgba(26,29,48,0.4)" : "#1a1d30",
                border: `1px solid ${gMonth > 0 ? "rgba(63,229,229,0.06)" : "rgba(63,229,229,0.2)"}`,
                outline: "none",
                fontFamily: "'Rajdhani', sans-serif",
                cursor: gMonth > 0 ? "not-allowed" : "pointer",
                opacity: gMonth > 0 ? 0.4 : 1,
              }}
            />
          </div>

          {/* Botón limpiar */}
          {(gMonth || gFrom || gTo || gYear !== 0) && (
            <button
              onClick={() => {
                setGYear(0);
                setGMonth(0);
                setGFrom("");
                setGTo("");
              }}
              style={{
                padding: "0.5rem 1rem",
                borderRadius: "0.375rem",
                fontSize: "13px",
                fontFamily: "'Rajdhani', sans-serif",
                fontWeight: 600,
                backgroundColor: "transparent",
                border: "1px solid rgba(255,51,102,0.3)",
                color: "#ff3366",
                cursor: "pointer",
              }}
            >
              Limpiar todo
            </button>
          )}
        </div>
      </div>

      {/* KPIs Clientes */}
      <div>
        <SectionTitle>Clientes</SectionTitle>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(6,1fr)",
            gap: "1rem",
          }}
        >
          <KpiCard
            label="Total clientes"
            value={kpis.totalClientes}
            color="#3fe5e5"
          />
          <KpiCard
            label="Clientes activos"
            value={kpis.activos}
            color="#00ff88"
            sub="Con servicio activo"
          />
          <KpiCard
            label="En desarrollo"
            value={kpis.desarrollo}
            color="#ffb800"
            sub="Web en proceso"
          />
          <KpiCard
            label="Clientes inactivos"
            value={kpis.inactivos}
            color="#ff3366"
            sub="Dados de baja"
          />
          <KpiCard
            label="Nuevos este mes"
            value={kpis.nuevosMes}
            color="#00c8ff"
            sub={MONTHS_FULL[currentMonth]}
          />
          <KpiCard
            label="Nuevos este año"
            value={kpis.nuevosAnio}
            color="#3fe5e5"
            sub={String(currentYear)}
          />
        </div>
      </div>

      {/* KPIs Webs */}
      <div>
        <SectionTitle>Webs</SectionTitle>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(6,1fr)",
            gap: "1rem",
          }}
        >
          <KpiCard
            label="Alquiler activo"
            value={kpis.alquilerActivo}
            color="#00ff88"
          />
          <KpiCard
            label="Alquiler desarrollo"
            value={kpis.alquilerDesarrollo}
            color="#ffb800"
          />
          <KpiCard
            label="Alquiler inactivo"
            value={kpis.alquilerInactivo}
            color="#ff3366"
          />
          <KpiCard
            label="Venta activa"
            value={kpis.ventaActivo}
            color="#4540d9"
          />
          <KpiCard
            label="Venta desarrollo"
            value={kpis.ventaDesarrollo}
            color="#8235f2"
          />
          <KpiCard
            label="Venta inactiva"
            value={kpis.ventaInactivo}
            color="#ff3366"
          />
        </div>
      </div>

      {/* KPIs Equipo */}
      <div>
        <SectionTitle>Equipo</SectionTitle>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3,1fr)",
            gap: "1rem",
          }}
        >
          <KpiCard
            label="Total colaboradores"
            value={kpis.colaboradoresTotal}
            color="#3fe5e5"
          />
          <KpiCard
            label="Colaboradores activos"
            value={kpis.colaboradoresActivos}
            color="#00ff88"
            sub="Con acceso al sistema"
          />
          <KpiCard
            label="Colaboradores inactivos"
            value={kpis.colaboradoresInactivos}
            color="#ff3366"
            sub="Sin acceso al sistema"
          />
        </div>
      </div>

      {/* KPIs Ingresos */}
      <div>
        <SectionTitle>Ingresos</SectionTitle>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3,1fr)",
            gap: "1rem",
          }}
        >
          <KpiCard
            label="Ingresos este mes"
            value={formatPrice(kpiIngresos.mes)}
            color="#00ff88"
            sub={MONTHS_FULL[currentMonth]}
          />
          <KpiCard
            label="Ingresos este año"
            value={formatPrice(kpiIngresos.anio)}
            color="#3fe5e5"
            sub={String(currentYear)}
          />
          <KpiCard
            label="Proyectado fin de año"
            value={formatPrice(kpiIngresos.proyectado)}
            color="#ffb800"
            sub="Basado en promedio mensual"
          />
        </div>
      </div>

      {/* Tortas estado alquiler + venta */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "1.5rem",
        }}
      >
        <div style={card}>
          <p
            style={{
              fontFamily: "'Orbitron', monospace",
              fontSize: "12px",
              fontWeight: 700,
              color: "white",
              letterSpacing: "1px",
              margin: "0 0 0.375rem 0",
            }}
          >
            ALQUILERES POR ESTADO
          </p>
          <p
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: "9px",
              color: "#8892a4",
              margin: "0 0 1.25rem 0",
            }}
          >
            Activo / Desarrollo / Inactivo
          </p>
          <PieChart data={pieAlquilerEstado} size={160} />
        </div>
        <div style={card}>
          <p
            style={{
              fontFamily: "'Orbitron', monospace",
              fontSize: "12px",
              fontWeight: 700,
              color: "white",
              letterSpacing: "1px",
              margin: "0 0 0.375rem 0",
            }}
          >
            VENTAS POR ESTADO
          </p>
          <p
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: "9px",
              color: "#8892a4",
              margin: "0 0 1.25rem 0",
            }}
          >
            Activo / Desarrollo / Inactivo
          </p>
          <PieChart data={pieVentaEstado} size={160} />
        </div>
      </div>

      {/* Tortas tipos de web */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "1.5rem",
        }}
      >
        <div style={card}>
          <p
            style={{
              fontFamily: "'Orbitron', monospace",
              fontSize: "12px",
              fontWeight: 700,
              color: "white",
              letterSpacing: "1px",
              margin: "0 0 0.375rem 0",
            }}
          >
            TIPOS DE WEB MÁS VENDIDOS
          </p>
          <p
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: "9px",
              color: "#8892a4",
              margin: "0 0 1.25rem 0",
            }}
          >
            Distribución por tipo — plan venta
          </p>
          <PieChart data={pieVentasTipos} size={160} />
        </div>
        <div style={card}>
          <p
            style={{
              fontFamily: "'Orbitron', monospace",
              fontSize: "12px",
              fontWeight: 700,
              color: "white",
              letterSpacing: "1px",
              margin: "0 0 0.375rem 0",
            }}
          >
            TIPOS DE WEB MÁS ALQUILADOS
          </p>
          <p
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: "9px",
              color: "#8892a4",
              margin: "0 0 1.25rem 0",
            }}
          >
            Distribución por tipo — plan alquiler
          </p>
          <PieChart data={pieAlquilerTipos} size={160} />
        </div>
      </div>

      {/* Línea: clientes nuevos */}
      <div style={card}>
        <p
          style={{
            fontFamily: "'Orbitron', monospace",
            fontSize: "13px",
            fontWeight: 700,
            color: "white",
            letterSpacing: "1px",
            margin: "0 0 0.375rem 0",
          }}
        >
          CLIENTES NUEVOS POR MES
        </p>
        <p
          style={{
            fontFamily: "'Share Tech Mono', monospace",
            fontSize: "9px",
            color: "#8892a4",
            margin: "0 0 0.875rem 0",
          }}
        >
          Cantidad de clientes registrados por período
        </p>
        <ChartFilter
          years={availableYears}
          selectedYear={ncYear}
          selectedMonthFrom={ncFrom}
          selectedMonthTo={ncTo}
          onChange={(f, v) => handleChartFilter("nc", f, v)}
        />
        <LineChart
          data={newClientsByMonth}
          color="#00c8ff"
          height={180}
          chartId="nc"
        />
      </div>

      {/* Línea: ingresos */}
      <div style={card}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: "0.375rem",
          }}
        >
          <div>
            <p
              style={{
                fontFamily: "'Orbitron', monospace",
                fontSize: "13px",
                fontWeight: 700,
                color: "white",
                letterSpacing: "1px",
                margin: 0,
              }}
            >
              INGRESOS A LO LARGO DEL TIEMPO
            </p>
            <p
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "9px",
                color: "#8892a4",
                margin: "4px 0 0 0",
              }}
            >
              Ingresos por período de registro
            </p>
          </div>
          <div style={{ display: "flex", gap: "1.5rem" }}>
            {[
              {
                label: "Mínimo",
                value: formatPrice(
                  Math.min(...incomeByMonth.map((d) => d.value)),
                ),
                color: "#ff3366",
              },
              {
                label: "Promedio",
                value: formatPrice(
                  incomeByMonth.reduce((s, d) => s + d.value, 0) /
                    (incomeByMonth.length || 1),
                ),
                color: "#ffb800",
              },
              {
                label: "Máximo",
                value: formatPrice(
                  Math.max(...incomeByMonth.map((d) => d.value)),
                ),
                color: "#00ff88",
              },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ textAlign: "center" }}>
                <p
                  style={{
                    fontFamily: "'Share Tech Mono', monospace",
                    fontSize: "8px",
                    color: "#8892a4",
                    margin: 0,
                    textTransform: "uppercase",
                  }}
                >
                  {label}
                </p>
                <p
                  style={{
                    fontFamily: "'Orbitron', monospace",
                    fontSize: "13px",
                    color,
                    margin: "2px 0 0 0",
                  }}
                >
                  {value}
                </p>
              </div>
            ))}
          </div>
        </div>
        <ChartFilter
          years={availableYears}
          selectedYear={incYear}
          selectedMonthFrom={incFrom}
          selectedMonthTo={incTo}
          onChange={(f, v) => handleChartFilter("inc", f, v)}
        />
        <LineChart
          data={incomeByMonth}
          color="#3fe5e5"
          height={180}
          isPrice={true}
          chartId="inc"
        />
      </div>

      {/* Top 10 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "1.5rem",
        }}
      >
        <div style={card}>
          <p
            style={{
              fontFamily: "'Orbitron', monospace",
              fontSize: "12px",
              fontWeight: 700,
              color: "white",
              letterSpacing: "1px",
              margin: "0 0 0.375rem 0",
            }}
          >
            TOP 10 MÁS VENDIDOS
          </p>
          <p
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: "9px",
              color: "#8892a4",
              margin: "0 0 0.5rem 0",
            }}
          >
            Tipos de web — plan venta
          </p>
          <BarList data={top10Ventas} color="#8235f2" />
        </div>
        <div style={card}>
          <p
            style={{
              fontFamily: "'Orbitron', monospace",
              fontSize: "12px",
              fontWeight: 700,
              color: "white",
              letterSpacing: "1px",
              margin: "0 0 0.375rem 0",
            }}
          >
            TOP 10 MÁS ALQUILADOS
          </p>
          <p
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: "9px",
              color: "#8892a4",
              margin: "0 0 0.5rem 0",
            }}
          >
            Tipos de web — plan alquiler
          </p>
          <BarList data={top10Alquiler} color="#3fe5e5" />
        </div>
      </div>

      {/* Retención */}
      <div
        style={{ ...card, display: "flex", alignItems: "center", gap: "2rem" }}
      >
        <div>
          <p
            style={{
              fontFamily: "'Share Tech Mono', monospace",
              fontSize: "10px",
              color: "#8892a4",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              margin: "0 0 0.5rem 0",
            }}
          >
            Tasa de retención
          </p>
          <p
            style={{
              fontFamily: "'Orbitron', monospace",
              fontSize: "40px",
              fontWeight: 700,
              color:
                retencion >= 70
                  ? "#00ff88"
                  : retencion >= 40
                    ? "#ffb800"
                    : "#ff3366",
              margin: 0,
              lineHeight: 1,
            }}
          >
            {retencion}%
          </p>
          <p
            style={{
              fontFamily: "'Rajdhani', sans-serif",
              fontSize: "13px",
              color: "#8892a4",
              margin: "0.5rem 0 0 0",
            }}
          >
            {kpis.activos} activos de {filtered.length} totales
          </p>
        </div>
        <div style={{ flex: 1 }}>
          <div
            style={{
              height: "8px",
              borderRadius: "4px",
              backgroundColor: "rgba(255,255,255,0.06)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${retencion}%`,
                backgroundColor:
                  retencion >= 70
                    ? "#00ff88"
                    : retencion >= 40
                      ? "#ffb800"
                      : "#ff3366",
                borderRadius: "4px",
                transition: "width 0.8s ease",
              }}
            />
          </div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginTop: "0.5rem",
            }}
          >
            <span
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "9px",
                color: "#8892a4",
              }}
            >
              0%
            </span>
            <span
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "9px",
                color: retencion >= 70 ? "#00ff88" : "#ffb800",
              }}
            >
              {retencion >= 70
                ? "✓ Buena retención"
                : retencion >= 40
                  ? "⚠ Retención media"
                  : "✕ Retención baja"}
            </span>
            <span
              style={{
                fontFamily: "'Share Tech Mono', monospace",
                fontSize: "9px",
                color: "#8892a4",
              }}
            >
              100%
            </span>
          </div>
        </div>
      </div>

      {/* Vencimientos */}
      <div>
        <SectionTitle>Próximos vencimientos</SectionTitle>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "1.5rem",
          }}
        >
          {[
            {
              title: "VENCEN EN 5 DÍAS",
              list: venc.v5,
              color: "#ff3366",
              bg: "rgba(255,51,102,",
            },
            {
              title: "VENCEN EN 30 DÍAS",
              list: venc.v30,
              color: "#ffb800",
              bg: "rgba(255,184,0,",
            },
          ].map(({ title, list, color, bg }) => (
            <div key={title} style={{ ...card, border: `1px solid ${bg}0.2)` }}>
              {/* Header */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "1rem",
                  paddingBottom: "0.75rem",
                  borderBottom: `1px solid ${bg}0.15)`,
                }}
              >
                <p
                  style={{
                    fontFamily: "'Orbitron', monospace",
                    fontSize: "11px",
                    fontWeight: 700,
                    color,
                    letterSpacing: "1px",
                    margin: 0,
                  }}
                >
                  {title}
                </p>
                <span
                  style={{
                    fontFamily: "'Orbitron', monospace",
                    fontSize: "22px",
                    fontWeight: 700,
                    color,
                    textShadow: `0 0 12px ${color}`,
                  }}
                >
                  {list.length}
                </span>
              </div>

              {list.length === 0 ? (
                <p
                  style={{
                    color: "#8892a4",
                    fontSize: "13px",
                    fontFamily: "'Rajdhani', sans-serif",
                    textAlign: "center",
                    padding: "1rem 0",
                  }}
                >
                  ✓ Sin vencimientos próximos
                </p>
              ) : (
                /* Scroll visible con barra estilizada */
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.5rem",
                    maxHeight: "280px",
                    overflowY: "scroll",
                    paddingRight: "6px",
                    /* Scrollbar visible */
                    scrollbarWidth: "thin",
                    scrollbarColor: `${color} rgba(255,255,255,0.05)`,
                  }}
                >
                  {list.map((c, i) => {
                    const daysLeft = Math.ceil(
                      (new Date(c.next_payment_date) - new Date()) /
                        (1000 * 60 * 60 * 24),
                    );
                    const urgente = daysLeft <= 2;
                    return (
                      <div
                        key={i}
                        onClick={() => navigate(`/clientes/${c.id}`)}
                        style={{
                          padding: "0.625rem 0.875rem",
                          borderRadius: "0.375rem",
                          backgroundColor: `${bg}0.05)`,
                          border: `1px solid ${bg}${urgente ? "0.35)" : "0.15)"}`,
                          cursor: "pointer",
                          transition: "all 0.15s",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = `${bg}0.12)`;
                          e.currentTarget.style.transform = "translateX(2px)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = `${bg}0.05)`;
                          e.currentTarget.style.transform = "translateX(0)";
                        }}
                      >
                        {/* Nombre + fecha + días restantes */}
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "flex-start",
                            gap: "0.5rem",
                          }}
                        >
                          <p
                            style={{
                              fontFamily: "'Rajdhani', sans-serif",
                              fontSize: "13px",
                              fontWeight: 700,
                              color: "white",
                              margin: 0,
                              flex: 1,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {c.name}
                          </p>
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              alignItems: "flex-end",
                              flexShrink: 0,
                            }}
                          >
                            <span
                              style={{
                                fontFamily: "'Share Tech Mono', monospace",
                                fontSize: "11px",
                                color,
                              }}
                            >
                              {formatDate(c.next_payment_date)}
                            </span>
                            <span
                              style={{
                                fontFamily: "'Orbitron', monospace",
                                fontSize: "10px",
                                fontWeight: 700,
                                color: urgente
                                  ? "#ff3366"
                                  : daysLeft <= 5
                                    ? "#ffb800"
                                    : "#00c8ff",
                                marginTop: "2px",
                              }}
                            >
                              {daysLeft === 0
                                ? "¡HOY!"
                                : daysLeft === 1
                                  ? "MAÑANA"
                                  : `${daysLeft} días`}
                            </span>
                          </div>
                        </div>

                        {/* CUPE + badges */}
                        <div
                          style={{
                            display: "flex",
                            gap: "0.5rem",
                            marginTop: "5px",
                            alignItems: "center",
                            flexWrap: "wrap",
                          }}
                        >
                          <span
                            style={{
                              fontFamily: "'Share Tech Mono', monospace",
                              fontSize: "10px",
                              color: `${bg}0.9)`,
                            }}
                          >
                            {c.cupe}
                          </span>
                          <Badge status={c.plan} />
                          <Badge status={c.status} />
                        </div>
                      </div>
                    );
                  })}
                  {/* Indicador de scroll si hay más de 4 */}
                  {list.length > 4 && (
                    <div
                      style={{
                        textAlign: "center",
                        padding: "0.25rem",
                        fontFamily: "'Share Tech Mono', monospace",
                        fontSize: "9px",
                        color: `${bg}0.6)`,
                        letterSpacing: "0.1em",
                      }}
                    >
                      ↑↓ SCROLL — {list.length} registros
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Lista de clientes */}
      <div>
        <SectionTitle>Todos los clientes</SectionTitle>
        <div style={card}>
          <ClientList clients={filtered} navigate={navigate} />
        </div>
      </div>
    </div>
  );
}
