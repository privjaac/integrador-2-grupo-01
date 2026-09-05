import axiosInstance from "./axios";
import usersMock from "../mocks/users.json";
import {
  applyTextSearch,
  createApiError,
  nextId,
  normalizeList,
  shouldUseMock,
} from "./helpers";

let mockUsers = normalizeList(usersMock, "collaborators");

export async function getCollaborators(filters = {}) {
  if (shouldUseMock()) {
    let users = [...mockUsers];
    users = applyTextSearch(users, filters.search, [
      "first_name",
      "last_name",
      "username",
      "email",
      "cupe",
      "document_number",
    ]);
    if (filters.role_id) {
      users = users.filter((user) => String(user.role_id) === String(filters.role_id));
    }
    if (filters.is_active !== undefined) {
      users = users.filter((user) => Boolean(user.is_active) === Boolean(filters.is_active));
    }
    return users;
  }

  const response = await axiosInstance.get("/api/users/", { params: filters });
  return normalizeList(response.data, "users");
}

export async function getCollaboratorById(id) {
  if (shouldUseMock()) {
    const user = mockUsers.find((item) => String(item.id) === String(id));
    if (!user) throw createApiError("Colaborador no encontrado.");
    return user;
  }

  const response = await axiosInstance.get(`/api/users/${id}`);
  return response.data;
}

export async function createCollaborator(payload) {
  if (shouldUseMock()) {
    const user = {
      ...payload,
      id: nextId(mockUsers),
      cupe: `ELO-${String(1000000 + nextId(mockUsers) * 7919).padStart(8, "0")}`,
      is_active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    mockUsers = [user, ...mockUsers];
    return user;
  }

  const response = await axiosInstance.post("/api/users/", payload);
  return response.data;
}

export async function updateCollaborator(id, payload) {
  if (shouldUseMock()) {
    const index = mockUsers.findIndex((item) => String(item.id) === String(id));
    if (index === -1) throw createApiError("Colaborador no encontrado.");
    mockUsers[index] = {
      ...mockUsers[index],
      ...payload,
      updated_at: new Date().toISOString(),
    };
    return mockUsers[index];
  }

  const response = await axiosInstance.put(`/api/users/${id}`, payload);
  return response.data;
}

export async function toggleCollaboratorStatus(id, isActive) {
  if (shouldUseMock()) {
    return updateCollaborator(id, { is_active: isActive });
  }

  if (isActive) {
    return updateCollaborator(id, { is_active: true });
  }

  const response = await axiosInstance.delete(`/api/users/${id}`);
  return response.data;
}
