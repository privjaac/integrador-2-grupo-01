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

export async function returnProjectToExecution(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/return-to-execution`, payload);
  return data;
}

export async function getDeliveryContext(projectId) {
  const { data } = await axiosInstance.get(`/api/projects/${projectId}/delivery-context`);
  return data;
}

export async function classifyProjectTask(projectId, taskId, payload) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/tasks/${taskId}/delivery-classification`, payload,
  );
  return data;
}

export async function recordTechnicalEvaluation(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/technical-evaluations`, payload);
  return data;
}

export async function getDeliveryAuthorizations(projectId) {
  const { data } = await axiosInstance.get(`/api/projects/${projectId}/delivery-authorizations`);
  return data;
}

export async function createDeliveryAuthorization(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/delivery-authorizations`, payload);
  return data;
}

export async function withdrawDeliveryAuthorization(projectId, authorizationId, reason) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/delivery-authorizations/${authorizationId}/withdrawal`, { reason },
  );
  return data;
}

export async function markProjectReadyForDelivery(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/ready-for-delivery`, payload);
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
