const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";

export function shouldUseMock() {
  return USE_MOCK;
}

export function normalizeList(payload, key) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload[key])) return payload[key];
  return [];
}

export function applyTextSearch(items, search, fields) {
  if (!search) return items;
  const query = String(search).trim().toLowerCase();
  if (!query) return items;
  return items.filter((item) =>
    fields.some((field) => String(item[field] ?? "").toLowerCase().includes(query)),
  );
}

export function nextId(items) {
  return Math.max(0, ...items.map((item) => Number(item.id) || 0)) + 1;
}

export function createApiError(message) {
  const error = new Error(message);
  error.userMessage = message;
  return error;
}
