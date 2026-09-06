import axiosInstance from "./axios";

export async function getRoles() {
  const { data } = await axiosInstance.get("/api/roles/");
  return data;
}

export async function createRole(payload) {
  const { data } = await axiosInstance.post("/api/roles/", payload);
  return data;
}

export async function updateRole(id, payload) {
  const { data } = await axiosInstance.put(`/api/roles/${id}`, payload);
  return data;
}
