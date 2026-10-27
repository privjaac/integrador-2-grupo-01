import axiosInstance from "./axios";

export async function getProjects() {
  const { data } = await axiosInstance.get("/api/projects/");
  return data;
}

export async function createProject(payload) {
  const { data } = await axiosInstance.post("/api/projects/", payload);
  return data;
}

export async function enterTechnicalValidation(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/technical-validation`, payload);
  return data;
}

export async function getCommercialAuthorizations(projectId) {
  const { data } = await axiosInstance.get(`/api/projects/${projectId}/commercial-authorizations`);
  return data;
}

export async function createCommercialAuthorization(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/commercial-authorizations`, payload);
  return data;
}

export async function withdrawCommercialAuthorization(projectId, authorizationId, reason) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/commercial-authorizations/${authorizationId}/withdrawal`, { reason },
  );
  return data;
}

export async function startProject(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/start`, payload);
  return data;
}
