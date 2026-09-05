// ==============================================================================
// TABLE.JSX v3 — Filas alternas con gris moderado + paginación
// ==============================================================================

import LoadingSpinner from "./LoadingSpinner";

export default function Table({
  children,
  isLoading = false,
  className = "",
  ...props
}) {
  if (isLoading) {
    return (
      <div
        style={{ display: "flex", justifyContent: "center", padding: "4rem 0" }}
      >
        <LoadingSpinner size="md" />
      </div>
    );
  }
  return (
    <div
      style={{
        overflowX: "auto",
        borderRadius: "0.5rem",
        border: "1px solid rgba(63,229,229,0.15)",
      }}
      className={className}
    >
      <table
        style={{
          width: "100%",
          minWidth: "600px",
          fontSize: "14px",
          borderCollapse: "collapse",
        }}
        role="table"
        {...props}
      >
        {children}
      </table>
    </div>
  );
}

Table.Head = function TableHead({ children }) {
  return (
    <thead role="rowgroup" style={{ backgroundColor: "#0b0d1a" }}>
      {children}
    </thead>
  );
};

Table.Body = function TableBody({ children }) {
  return <tbody role="rowgroup">{children}</tbody>;
};

Table.Row = function TableRow({
  children,
  onClick,
  isSelected = false,
  index,
  className = "",
}) {
  // Moderado — gris claramente distinguible en filas impares
  const bgColor = isSelected
    ? "rgba(63,229,229,0.10)"
    : index !== undefined && index % 2 === 1
      ? "rgba(255,255,255,0.06)" // moderado — se ve claramente
      : "#111427"; // par — fondo base de cards

  return (
    <tr
      role="row"
      className={className}
      onClick={onClick}
      style={{
        backgroundColor: bgColor,
        cursor: onClick ? "pointer" : "default",
        borderBottom: "1px solid rgba(63,229,229,0.07)",
        transition: "background-color 0.15s",
      }}
      onMouseEnter={(e) => {
        if (!isSelected)
          e.currentTarget.style.backgroundColor = "rgba(63,229,229,0.06)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = bgColor;
      }}
    >
      {children}
    </tr>
  );
};

Table.HeadCell = function TableHeadCell({ children, className = "" }) {
  return (
    <th
      role="columnheader"
      scope="col"
      className={className}
      style={{
        padding: "1rem 1.25rem",
        textAlign: "left",
        fontSize: "11px",
        fontWeight: 700,
        letterSpacing: "0.1em",
        textTransform: "uppercase",
        color: "#8892a4",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </th>
  );
};

Table.Cell = function TableCell({ children, className = "", ...props }) {
  return (
    <td
      role="cell"
      className={className}
      style={{
        padding: "1rem 1.25rem",
        color: "rgba(255,255,255,0.85)",
        verticalAlign: "middle",
      }}
      {...props}
    >
      {children}
    </td>
  );
};

Table.Empty = function TableEmpty({
  colSpan = 5,
  message = "No hay datos para mostrar",
  icon,
}) {
  return (
    <tr role="row">
      <td
        role="cell"
        colSpan={colSpan}
        style={{ padding: "4rem 1rem", textAlign: "center" }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "0.75rem",
          }}
        >
          {icon || (
            <svg
              width="40"
              height="40"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              style={{ color: "#374151" }}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          )}
          <p style={{ color: "#8892a4", fontSize: "14px" }}>{message}</p>
        </div>
      </td>
    </tr>
  );
};

Table.Pagination = function TablePagination({
  currentPage = 1,
  totalPages = 1,
  totalItems = 0,
  itemsPerPage = 10,
  onPageChange,
}) {
  if (totalPages <= 1) return null;

  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalItems);

  const getPageNumbers = () => {
    const pages = [];
    let start = Math.max(1, currentPage - 2);
    let end = Math.min(totalPages, start + 4);
    if (end - start < 4) start = Math.max(1, end - 4);
    for (let i = start; i <= end; i++) pages.push(i);
    return pages;
  };

  const btnStyle = (isActive, isDisabled = false) => ({
    padding: "0.375rem 0.75rem",
    borderRadius: "0.375rem",
    fontSize: "13px",
    fontWeight: isActive ? 600 : 400,
    fontFamily: "'Rajdhani', sans-serif",
    cursor: isDisabled ? "not-allowed" : "pointer",
    border: isActive
      ? "1px solid rgba(63,229,229,0.4)"
      : "1px solid rgba(63,229,229,0.15)",
    backgroundColor: isActive ? "rgba(63,229,229,0.12)" : "transparent",
    color: isActive ? "#3fe5e5" : isDisabled ? "#374151" : "#8892a4",
    transition: "all 0.15s",
    minWidth: "36px",
    textAlign: "center",
  });

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "1rem 0",
        flexWrap: "wrap",
        gap: "0.75rem",
      }}
    >
      <p
        style={{
          color: "#8892a4",
          fontSize: "13px",
          fontFamily: "'Rajdhani', sans-serif",
          margin: 0,
        }}
      >
        Mostrando{" "}
        <span style={{ color: "white", fontWeight: 600 }}>
          {startItem}–{endItem}
        </span>{" "}
        de <span style={{ color: "white", fontWeight: 600 }}>{totalItems}</span>{" "}
        registros
      </p>
      <div style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          style={btnStyle(false, currentPage === 1)}
        >
          ‹
        </button>
        {getPageNumbers().map((n) => (
          <button
            key={n}
            onClick={() => onPageChange(n)}
            style={btnStyle(n === currentPage)}
          >
            {n}
          </button>
        ))}
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          style={btnStyle(false, currentPage === totalPages)}
        >
          ›
        </button>
      </div>
    </div>
  );
};
