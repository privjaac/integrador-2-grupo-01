import axiosInstance from "./axios";
import rolesMock from "../mocks/roles.json";
import { createApiError, normalizeList, shouldUseMock } from "./helpers";

let mockRoles = normalizeList(rolesMock, "roles");

function normalizeRole(role) {
  return {
    ...role,
    hierarchy: role.hierarchy ?? Number(String(role.level || "").replace("L", "")),
  };
}

export async function getRoles() {
  if (shouldUseMock()) {
    return mockRoles.map(normalizeRole);
  }

  const response = await axiosInstance.get("/api/roles/");
  return normalizeList(response.data, "roles").map(normalizeRole);
}

export async function updateRole(id, payload) {
  if (shouldUseMock()) {
    const index = mockRoles.findIndex((item) => String(item.id) === String(id));
    if (index === -1) throw createApiError("Rol no encontrado.");
    mockRoles[index] = normalizeRole({ ...mockRoles[index], ...payload });
    return mockRoles[index];
  }

  const response = await axiosInstance.put(`/api/roles/${id}`, {
    name: payload.name,
    description: payload.description,
  });
  return normalizeRole(response.data);
}
