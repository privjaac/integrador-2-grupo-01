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
