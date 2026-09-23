import axiosInstance from "./axios";
import { shouldUseMock } from "./helpers";

export async function getNextCupe(type) {
  if (shouldUseMock()) {
    const prefix = type === "client" ? "CLI" : "ELO";
    return `${prefix}-${String(Math.floor(Math.random() * 90000000) + 10000000)}`;
  }

  const response = await axiosInstance.get(`/api/cupe-log/next-${type}`);
  return response.data.next_cupe || response.data.cupe || response.data;
}

export async function changeCupe(type, id, newCupe, reason, observations) {
  if (shouldUseMock()) {
    return {
      entity_type: type,
      entity_id: id,
      new_cupe: newCupe,
      reason,
      changed_at: new Date().toISOString(),
    };
  }

  const response = await axiosInstance.post('/api/cupe-log/', {
    entity_type: type,
    entity_id: Number(id),
    new_cupe: newCupe,
    reason,
    observations: observations || null,
  });
  return response.data;
}

export async function getCupeHistory(type, id) {
  if (shouldUseMock()) {
    return [];
  }

  const response = await axiosInstance.get('/api/cupe-log/', {
    params: { entity_type: type, entity_id: id },
  });
  const history = Array.isArray(response.data) ? response.data : response.data.history || [];
  return history.map((entry) => ({
    ...entry,
    motivo: entry.reason,
    observaciones: entry.observations,
    authorized_by: entry.authorized_by_name,
    created_at: entry.changed_at,
  }));
}
