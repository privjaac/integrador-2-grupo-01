// ==============================================================================
// MAIN.JSX — Punto de entrada de la aplicación ELISA
//
// Orden de providers (de afuera hacia adentro):
//   BrowserRouter  → maneja las rutas del navegador
//   AuthProvider   → maneja la sesión del usuario
//   ToastProvider  → maneja las notificaciones toast globales
//   App            → el árbol de rutas y componentes
// ==============================================================================

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { AuthProvider } from "./context/AuthContext";
import { ToastProvider } from "./components/ui/Toast";
import App from "./App";

import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
