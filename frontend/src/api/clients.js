import axiosInstance from "./axios";

export async function getClients(params = {}) {
  const { data } = await axiosInstance.get("/api/clients/", { params });
  return data;
}

export async function getClientById(id) {
  const { data } = await axiosInstance.get(`/api/clients/${id}`);
  return data;
}

export async function createClient(payload) {
  const { data } = await axiosInstance.post("/api/clients/", payload);
  return data;
}

export async function updateClient(id, payload) {
  const { data } = await axiosInstance.put(`/api/clients/${id}`, payload);
  return data;
}

export async function deactivateClient(id) {
  const { data } = await axiosInstance.delete(`/api/clients/${id}`);
  return data;
}
