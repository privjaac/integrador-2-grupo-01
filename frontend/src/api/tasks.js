import axiosInstance from "./axios";

export async function getTaskContext() {
  const { data } = await axiosInstance.get("/api/tasks/context");
  return data;
}

export async function createTask(payload) {
  const { data } = await axiosInstance.post("/api/tasks/", payload);
  return data;
}

export async function assignTask(id, assignee_id) {
  const { data } = await axiosInstance.post(`/api/tasks/${id}/assignment`, { assignee_id });
  return data;
}

export async function startTask(id) {
  const { data } = await axiosInstance.post(`/api/tasks/${id}/start`);
  return data;
}

export async function submitTaskReview(id, result_text) {
  const { data } = await axiosInstance.post(`/api/tasks/${id}/submit-review`, { result_text });
  return data;
}

export async function reviewTask(id, resolution, reason = null) {
  const { data } = await axiosInstance.post(`/api/tasks/${id}/review`, { resolution, reason });
  return data;
}

export async function reassignTask(id, { assignee_id, responsible_id, reason }) {
  const { data } = await axiosInstance.post(`/api/tasks/${id}/reassignment`, {
    assignee_id, responsible_id, reason,
  });
  return data;
}

export async function removeTaskExecutor(id, reason) {
  const { data } = await axiosInstance.post(`/api/tasks/${id}/remove-executor`, { reason });
  return data;
}

export async function blockTask(id, reason, evidence = "") {
  const { data } = await axiosInstance.post(`/api/tasks/${id}/block`, { reason, evidence });
  return data;
}

export async function unblockTask(id, reason, evidence = "") {
  const { data } = await axiosInstance.post(`/api/tasks/${id}/unblock`, { reason, evidence });
  return data;
}

export async function reportTaskIncident(id, reason, evidence = "") {
  const { data } = await axiosInstance.post(`/api/tasks/${id}/incident`, { reason, evidence });
  return data;
}

export async function designateLeader(projectId, collaborator_id) {
  const { data } = await axiosInstance.post(`/api/tasks/projects/${projectId}/leadership`, { collaborator_id });
  return data;
}

export async function addTeamMember(projectId, collaborator_id) {
  const { data } = await axiosInstance.post(`/api/tasks/projects/${projectId}/team`, { collaborator_id });
  return data;
}

export async function designateCoordinator(projectId, collaborator_id) {
  const { data } = await axiosInstance.post(`/api/tasks/projects/${projectId}/coordination`, { collaborator_id });
  return data;
}

export async function removeCoordinator(projectId, collaboratorId) {
  const { data } = await axiosInstance.delete(`/api/tasks/projects/${projectId}/coordination/${collaboratorId}`);
  return data;
}

export async function removeLeader(projectId, collaboratorId) {
  const { data } = await axiosInstance.delete(`/api/tasks/projects/${projectId}/leadership/${collaboratorId}`);
  return data;
}

export async function removeTeamMember(projectId, collaboratorId) {
  const { data } = await axiosInstance.delete(`/api/tasks/projects/${projectId}/team/${collaboratorId}`);
  return data;
}
