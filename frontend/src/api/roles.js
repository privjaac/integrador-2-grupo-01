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

  const response = await axiosInstance.put(`/api/roles/${id}`, payload);
  return normalizeRole(response.data);
}

export async function createRole(payload) {
  if (shouldUseMock()) {
    const role = normalizeRole({ id: Date.now(), ...payload });
    mockRoles = [...mockRoles, role];
    return role;
  }
  const response = await axiosInstance.post("/api/roles/", payload);
  return normalizeRole(response.data);
}

export async function deleteRole(id) {
  if (shouldUseMock()) {
    mockRoles = mockRoles.filter((item) => String(item.id) !== String(id));
    return { message: "Rol eliminado." };
  }
  const response = await axiosInstance.delete(`/api/roles/${id}`);
  return response.data;
}

export async function getPermissionCatalog() {
  if (shouldUseMock()) return [];
  const response = await axiosInstance.get("/api/roles/permission-catalog");
  return response.data;
}

export async function getRoleHistory() {
  if (shouldUseMock()) return [];
  const response = await axiosInstance.get("/api/roles/history");
  return response.data;
}
