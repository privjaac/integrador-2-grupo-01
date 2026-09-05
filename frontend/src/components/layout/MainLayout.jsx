// ==============================================================================
// MAINLAYOUT.JSX — Estructura visual principal del sistema ELISA (v5)
//
// Layout:
//   ┌──────────────┬──────────────────────────┐
//   │              │ TOPBAR (sticky)           │
//   │   SIDEBAR    ├──────────────────────────┤
//   │   (256px)    │                          │
//   │              │   CONTENIDO              │
//   │              │                          │
//   └──────────────┴──────────────────────────┘
//
// El sidebar ocupa 256px a la izquierda.
// El área derecha (flex:1) contiene el topbar sticky arriba y el contenido abajo.
// ==============================================================================

import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function MainLayout() {
  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        backgroundColor: "#05060f",
      }}
    >
      {/* Sidebar — columna izquierda */}
      <div style={{ width: "256px", flexShrink: 0 }}>
        <Sidebar />
      </div>

      {/* Área derecha — topbar arriba + contenido abajo */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
          minHeight: "100vh",
        }}
      >
        {/* Topbar sticky — se queda arriba al hacer scroll */}
        <div style={{ position: "sticky", top: 0, zIndex: 30, flexShrink: 0 }}>
          <Topbar />
        </div>

        {/* Contenido de la página */}
        <main style={{ flex: 1, padding: "2rem" }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
