import axiosInstance from "./axios";

export async function getCollaborators(params = {}) {
  const { data } = await axiosInstance.get("/api/users/", { params });
  return data;
}

export async function getCollaboratorById(id) {
  const { data } = await axiosInstance.get(`/api/users/${id}`);
  return data;
}

export async function createCollaborator(payload) {
  const { data } = await axiosInstance.post("/api/users/", payload);
  return data;
}

export async function updateCollaborator(id, payload) {
  const { data } = await axiosInstance.put(`/api/users/${id}`, payload);
  return data;
}

export async function toggleCollaboratorStatus(id, newStatus) {
  const { data } = await axiosInstance.put(`/api/users/${id}`, {
    is_active: newStatus,
  });
  return data;
}
