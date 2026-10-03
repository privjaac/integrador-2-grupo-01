const GENERIC_ERROR = "No se pudo completar la operación.";
const SERVER_ERROR = "Ocurrió un error interno. Inténtalo nuevamente.";
const NETWORK_ERROR = "No se pudo conectar con el servidor.";
const MAX_MESSAGES = 4;
const MAX_LENGTH = 500;

function cleanText(value) {
  if (typeof value !== "string") return "";
  return value.trim().replace(/\s+/g, " ");
}

function validationMessage(item) {
  if (!item || typeof item !== "object" || Array.isArray(item)) return "";
  const message = cleanText(item.msg);
  if (!message) return "";

  const location = Array.isArray(item.loc)
    ? item.loc
        .filter((part) => !["body", "query", "path"].includes(String(part)))
        .map(String)
        .join(".")
    : "";
  return location ? `${location}: ${message}` : message;
}

export function normalizeApiError(error) {
  if (!error?.response) return NETWORK_ERROR;

  const status = Number(error.response.status);
  if (status >= 500) return SERVER_ERROR;

  const detail = error.response?.data?.detail;
  const detailText = cleanText(detail);
  if (detailText) return detailText.slice(0, MAX_LENGTH);

  if (Array.isArray(detail)) {
    const messages = [...new Set(detail.map(validationMessage).filter(Boolean))]
      .slice(0, MAX_MESSAGES)
      .join("; ");
    if (messages) return messages.slice(0, MAX_LENGTH);
  }

  return GENERIC_ERROR;
}

export default normalizeApiError;
