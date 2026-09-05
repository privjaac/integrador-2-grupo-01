// ==============================================================================
// VITE.CONFIG.JS — Configuración del entorno de desarrollo y build
//
// Responsabilidad: configura Vite como bundler del proyecto React.
//   Define cómo se procesa el CSS, qué plugins se usan, y cómo
//   se levanta el servidor de desarrollo local.
//
// Tecnologías configuradas aquí:
//   - React       → plugin oficial de Vite para JSX y Fast Refresh
//   - Tailwind v4 → procesado vía PostCSS (sin tailwind.config.js,
//                   porque v4 lo configura todo desde index.css)
//   - Autoprefixer → agrega prefijos CSS para compatibilidad cross-browser
//
// Patrón: Configuration as Code — toda la config del entorno en un solo lugar.
//
// NOTA PARA EL EQUIPO:
//   No modificar este archivo sin aprobación del Tech Lead.
//   Cualquier cambio afecta el build de producción.
// ==============================================================================

// ------------------------------------------------------------------------------
// SECCIÓN 1 — Imports
// Importamos las herramientas necesarias para configurar el entorno.
// ------------------------------------------------------------------------------

// defineConfig: función helper de Vite que da autocompletado en el IDE
import { defineConfig } from "vite";

// plugin-react: habilita JSX, Fast Refresh (hot reload sin perder estado)
// y el runtime automático de React (no necesitamos importar React en cada archivo)
import react from "@vitejs/plugin-react";

// tailwindcss: framework de utilidades CSS — v4 se integra como plugin PostCSS
import tailwindcss from "@tailwindcss/postcss";

// autoprefixer: agrega automáticamente prefijos CSS (-webkit-, -moz-, etc.)
// para que los estilos funcionen en todos los navegadores modernos
import autoprefixer from "autoprefixer";

// ------------------------------------------------------------------------------
// SECCIÓN 2 — Configuración principal
// defineConfig recibe un objeto con todas las opciones de Vite.
// El export default es lo que Vite lee al arrancar.
// ------------------------------------------------------------------------------

export default defineConfig({
  // ----------------------------------------------------------------------------
  // plugins: lista de plugins que extienden las capacidades de Vite.
  // react() habilita el soporte completo para React en este proyecto.
  // ----------------------------------------------------------------------------
  plugins: [react()],

  // ----------------------------------------------------------------------------
  // css.postcss: configura el procesador de CSS.
  // PostCSS es la herramienta que transforma el CSS antes de entregarlo
  // al navegador. Tailwind v4 y autoprefixer corren como plugins de PostCSS.
  //
  // Flujo: archivo .css → PostCSS → Tailwind expande clases → Autoprefixer
  // agrega prefijos → CSS final listo para el navegador.
  // ----------------------------------------------------------------------------
  css: {
    postcss: {
      plugins: [
        tailwindcss(), // procesa las clases de Tailwind y genera el CSS
        autoprefixer(), // agrega prefijos para compatibilidad cross-browser
      ],
    },
  },

  // ----------------------------------------------------------------------------
  // server: opciones del servidor de desarrollo local.
  // Puerto 5173 es el default de Vite — el dev frontend accede en localhost:5173
  // ----------------------------------------------------------------------------
  server: {
    port: 5173,
    // strictPort: true significa que si el puerto ya está ocupado,
    // Vite falla en lugar de usar otro puerto aleatorio.
    // Esto evita confusión cuando hay varios proyectos corriendo.
    strictPort: true,
  },
});
