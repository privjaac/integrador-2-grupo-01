// ==============================================================================
// USEAUTH.JS — Hook personalizado para acceder al contexto de autenticación
//
// Responsabilidad: provee una interfaz limpia y segura para que cualquier
//   componente acceda al estado de autenticación sin necesidad de
//   importar AuthContext directamente.
//
// Patrón: Custom Hook Pattern
//   En lugar de que cada componente importe useContext + AuthContext,
//   este hook encapsula esa lógica y agrega validación.
//   Los componentes solo necesitan: import { useAuth } from '../hooks/useAuth'
//
// Seguridad:
//   Valida que el hook se use dentro del AuthProvider.
//   Si se usa fuera del provider (error de programación), lanza un error
//   claro en lugar de fallar silenciosamente con un null confuso.
//
// Uso en cualquier componente:
//   import { useAuth } from '../../hooks/useAuth'
//
//   function MiComponente() {
//     const { user, isAuthenticated, logout } = useAuth()
//     ...
//   }
//
// NOTA PARA EL EQUIPO:
//   Siempre usar este hook para acceder a la autenticación.
//   Nunca importar AuthContext directamente en los componentes.
// ==============================================================================

// ------------------------------------------------------------------------------
// SECCIÓN 1 — IMPORTS
//
// useContext: hook de React para consumir un contexto.
// AuthContext: el contexto creado en AuthContext.jsx.
// ------------------------------------------------------------------------------

import { useContext } from "react";
import { AuthContext } from "../context/AuthContext";

// ==============================================================================
// HOOK — useAuth
//
// Retorna el valor completo del AuthContext con validación incluida.
//
// Retorna:
//   {
//     token          (string|null)  → JWT de acceso para las peticiones API
//     user           (object|null)  → datos del usuario logueado
//     isAuthenticated(boolean)      → true si hay sesión activa
//     isLoading      (boolean)      → true mientras se verifica la sesión
//     login          (function)     → inicia sesión con token y datos de usuario
//     logout         (function)     → cierra sesión y limpia el estado
//   }
//
// Errores:
//   Lanza un Error si se usa fuera del AuthProvider.
//   Esto detecta errores de configuración en tiempo de desarrollo.
// ==============================================================================

export function useAuth() {
  // ----------------------------------------------------------------------------
  // SECCIÓN 2 — CONSUMO DEL CONTEXTO
  //
  // useContext(AuthContext) retorna el valor que AuthProvider pasa
  // como prop "value" a AuthContext.Provider.
  // Si el componente no está dentro del AuthProvider, retorna null
  // (el valor por defecto con el que se creó el contexto).
  // ----------------------------------------------------------------------------

  const context = useContext(AuthContext);

  // ----------------------------------------------------------------------------
  // SECCIÓN 3 — VALIDACIÓN DE USO CORRECTO
  //
  // Si context es null, significa que el hook se está usando fuera
  // del AuthProvider — esto es un error de programación.
  //
  // Lanzamos un Error descriptivo para que el dev sepa exactamente
  // qué está mal y cómo solucionarlo, en lugar de un crash genérico.
  //
  // Este error SOLO ocurre en tiempo de desarrollo. En producción
  // no debería pasar si la app está correctamente configurada.
  // ----------------------------------------------------------------------------

  if (context === null) {
    throw new Error(
      "[useAuth] Este hook debe usarse dentro de <AuthProvider>. " +
        "Verificá que el componente esté dentro del árbol de componentes " +
        "envuelto por AuthProvider en main.jsx.",
    );
  }

  // ----------------------------------------------------------------------------
  // SECCIÓN 4 — RETORNO DEL CONTEXTO
  //
  // Retorna el objeto completo del contexto.
  // Los componentes pueden desestructurar solo lo que necesitan:
  //   const { user, logout } = useAuth()
  // ----------------------------------------------------------------------------

  return context;
}
