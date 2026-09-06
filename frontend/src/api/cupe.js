import axiosInstance from "./axios";

export async function getCupeHistory(entityType, entityId) {
  const { data } = await axiosInstance.get("/api/cupe-log/", {
    params: { entity_type: entityType },
  });
  return data.filter((log) => String(log.entity_id) === String(entityId));
}

export async function getNextCupe(entityType) {
  const { data } = await axiosInstance.get("/api/cupe-log/next", {
    params: { entity_type: entityType },
  });
  return data;
}

export async function changeCupe(entityType, entityId, newCupe, reason, observations) {
  const { data } = await axiosInstance.post("/api/cupe-log/", {
    entity_type: entityType,
    entity_id: Number(entityId),
    new_cupe: newCupe,
    reason,
    observations,
  });
  return data;
}
