// ==============================================================================
// USEAPI.JS — Hook personalizado para llamadas a la API con estado
//
// Responsabilidad: encapsula la lógica repetitiva de cualquier llamada
//   a la API — loading, error, datos — en un hook reutilizable.
//   Evita duplicar código de manejo de estado en cada componente.
//
// Patrón: Custom Hook Pattern + State Machine simplificada
//   Cada llamada a la API tiene exactamente 3 estados posibles:
//     1. idle    → no se ha llamado todavía
//     2. loading → la petición está en curso
//     3. success → la petición terminó con éxito (data disponible)
//     4. error   → la petición falló (error disponible)
//
// Seguridad:
//   - No expone detalles técnicos del error al usuario final.
//   - Loguea el error completo en consola solo en desarrollo.
//   - Maneja el caso de componente desmontado para evitar
//     actualizar estado en un componente que ya no existe
//     (memory leak y warning de React).
//
// Uso en cualquier componente:
//   import { useApi } from '../../hooks/useApi'
//   import { getClients } from '../../api/clients'
//
//   function ClientsPage() {
//     const { data, isLoading, error, execute } = useApi(getClients)
//
//     useEffect(() => { execute() }, [])
//
//     if (isLoading) return <Spinner />
//     if (error)     return <ErrorModal message={error} />
//     return <Table data={data} />
//   }
//
// NOTA PARA EL EQUIPO:
//   Este hook es para llamadas simples de lectura.
//   Para formularios (POST/PUT con validación), usar el estado
//   local del componente directamente.
// ==============================================================================

// ------------------------------------------------------------------------------
// SECCIÓN 1 — IMPORTS
// ------------------------------------------------------------------------------

import { useState, useCallback, useEffect, useRef } from "react";

// ==============================================================================
// HOOK — useApi
//
// Parámetros:
//   apiFunction (function) → la función del service layer a ejecutar
//                            Ej: getClients, getRoles, getWebTypes
//
// Retorna:
//   {
//     data      (any)      → los datos retornados por la API (null si no hay)
//     isLoading (boolean)  → true mientras la petición está en curso
//     error     (string)   → mensaje de error para mostrar al usuario (null si no hay)
//     execute   (function) → función para disparar la llamada a la API
//     reset     (function) → limpia el estado (data, error) a su valor inicial
//   }
// ==============================================================================

export function useApi(apiFunction) {
  // ----------------------------------------------------------------------------
  // SECCIÓN 2 — ESTADO INTERNO
  //
  // Tres estados para representar el ciclo completo de una petición HTTP:
  //   data      → lo que devuelve la API cuando tiene éxito
  //   isLoading → si la petición está en progreso
  //   error     → mensaje de error si la petición falla
  // ----------------------------------------------------------------------------

  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // ----------------------------------------------------------------------------
  // SECCIÓN 3 — REF PARA PREVENIR MEMORY LEAKS
  //
  // isMounted es una ref que trackea si el componente sigue montado.
  // Si el usuario navega a otra página mientras hay una petición en curso,
  // el componente se desmonta. Cuando la petición termina, no debemos
  // llamar a setData/setError porque el componente ya no existe.
  //
  // useRef en lugar de useState porque cambiar isMounted no debe
  // provocar un re-render del componente.
  // ----------------------------------------------------------------------------

  const isMounted = useRef(true);

  useEffect(() => {
    // Al montar el componente, isMounted es true
    isMounted.current = true;

    // Al desmontar el componente, isMounted pasa a false
    // Esto previene actualizaciones de estado en componentes desmontados
    return () => {
      isMounted.current = false;
    };
  }, []);

  // ----------------------------------------------------------------------------
  // SECCIÓN 4 — FUNCIÓN EXECUTE
  //
  // Ejecuta la apiFunction pasada al hook y maneja todos los estados.
  //
  // Parámetros:
  //   ...args → argumentos opcionales que se pasan a la apiFunction
  //             Ej: execute(clientId) para buscar un cliente específico
  //
  // Flujo:
  //   1. Activa isLoading y limpia errores anteriores
  //   2. Ejecuta la apiFunction
  //   3. Si tiene éxito → guarda los datos
  //   4. Si falla → extrae el mensaje de error y lo guarda
  //   5. Siempre desactiva isLoading al terminar
  //
  // useCallback evita recrear la función en cada render.
  // La dependencia es apiFunction — si cambia, execute se recrea.
  // ----------------------------------------------------------------------------

  const execute = useCallback(
    async (...args) => {
      // Paso 1 — Activa el estado de carga y limpia errores previos
      setIsLoading(true);
      setError(null);

      try {
        // Paso 2 — Ejecuta la función de API con los argumentos recibidos
        const result = await apiFunction(...args);

        // Paso 3 — Solo actualiza el estado si el componente sigue montado
        if (isMounted.current) {
          setData(result);
        }
      } catch (err) {
        // Paso 4 — Manejo de errores
        // Solo actualiza el estado si el componente sigue montado
        if (isMounted.current) {
          // Extrae el mensaje de error de la respuesta del backend si existe.
          // El backend FastAPI devuelve errores en el formato: { detail: "mensaje" }
          // Si no hay mensaje del backend, usa un mensaje genérico.
          const errorMessage =
            err?.response?.data?.detail ||
            err?.message ||
            "Ocurrió un error inesperado. Intentá nuevamente.";

          setError(errorMessage);

          // En desarrollo loguea el error completo para debugging.
          // En producción (VITE_MODE=production) no se loguea nada
          // para no exponer información interna del sistema.
          if (import.meta.env.DEV) {
            console.error("[useApi] Error en la petición:", err);
          }
        }
      } finally {
        // Paso 5 — Desactiva el loading solo si el componente sigue montado
        if (isMounted.current) {
          setIsLoading(false);
        }
      }
    },
    [apiFunction],
  );

  // ----------------------------------------------------------------------------
  // SECCIÓN 5 — FUNCIÓN RESET
  //
  // Limpia el estado del hook a sus valores iniciales.
  // Útil cuando el usuario cierra un modal de error y queremos
  // que la próxima ejecución empiece desde cero.
  //
  // useCallback para consistencia y optimización.
  // ----------------------------------------------------------------------------

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setIsLoading(false);
  }, []);

  // ----------------------------------------------------------------------------
  // SECCIÓN 6 — RETORNO
  //
  // El componente que usa este hook recibe todo lo necesario para
  // manejar cualquier llamada a la API de forma completa.
  // ----------------------------------------------------------------------------

  return {
    data,
    isLoading,
    error,
    execute,
    reset,
  };
}
