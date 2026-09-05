import axiosInstance from "./axios";
import clientsMock from "../mocks/clients.json";
import {
  applyTextSearch,
  createApiError,
  nextId,
  normalizeList,
  shouldUseMock,
} from "./helpers";

let mockClients = normalizeList(clientsMock, "clients");

export async function getClients(filters = {}) {
  if (shouldUseMock()) {
    let clients = [...mockClients];
    clients = applyTextSearch(clients, filters.search, ["name", "cupe", "email", "document_number"]);
    if (filters.status) clients = clients.filter((client) => client.status === filters.status);
    if (filters.plan) clients = clients.filter((client) => client.plan === filters.plan);
    return clients;
  }

  const response = await axiosInstance.get("/api/clients/", { params: filters });
  return normalizeList(response.data, "clients");
}

export async function getClientById(id) {
  if (shouldUseMock()) {
    const client = mockClients.find((item) => String(item.id) === String(id));
    if (!client) throw createApiError("Cliente no encontrado.");
    return client;
  }

  const response = await axiosInstance.get(`/api/clients/${id}`);
  return response.data;
}

export async function createClient(payload) {
  if (shouldUseMock()) {
    const client = {
      ...payload,
      id: nextId(mockClients),
      cupe: `CLI-${String(1000000 + nextId(mockClients) * 7919).padStart(8, "0")}`,
      is_active: payload.is_active ?? true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    mockClients = [client, ...mockClients];
    return client;
  }

  const response = await axiosInstance.post("/api/clients/", payload);
  return response.data;
}

export async function updateClient(id, payload) {
  if (shouldUseMock()) {
    const index = mockClients.findIndex((item) => String(item.id) === String(id));
    if (index === -1) throw createApiError("Cliente no encontrado.");
    mockClients[index] = {
      ...mockClients[index],
      ...payload,
      updated_at: new Date().toISOString(),
    };
    return mockClients[index];
  }

  const response = await axiosInstance.put(`/api/clients/${id}`, payload);
  return response.data;
}

export async function deactivateClient(id) {
  if (shouldUseMock()) {
    return updateClient(id, { status: "inactivo", is_active: false });
  }

  const response = await axiosInstance.delete(`/api/clients/${id}`);
  return response.data;
}
