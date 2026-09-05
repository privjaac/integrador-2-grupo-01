import axiosInstance from "./axios";
import { shouldUseMock } from "./helpers";

export async function getNextCupe(type) {
  if (shouldUseMock()) {
    const prefix = type === "client" ? "CLI" : "ELO";
    return `${prefix}-${String(Math.floor(Math.random() * 90000000) + 10000000)}`;
  }

  const response = await axiosInstance.get(`/api/cupe/next-${type}`);
  return response.data.next_cupe || response.data.cupe || response.data;
}

export async function changeCupe(type, id, newCupe, reason) {
  if (shouldUseMock()) {
    return {
      entity_type: type,
      entity_id: id,
      new_cupe: newCupe,
      reason,
      changed_at: new Date().toISOString(),
    };
  }

  const response = await axiosInstance.post(`/api/cupe/change-${type}/${id}`, {
    new_cupe: newCupe,
    reason,
  });
  return response.data;
}

export async function getCupeHistory(type, id) {
  if (shouldUseMock()) {
    return [];
  }

  const response = await axiosInstance.get(`/api/cupe/history/${type}/${id}`);
  return Array.isArray(response.data) ? response.data : response.data.history || [];
}
