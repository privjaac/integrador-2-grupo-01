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
let mockClientRequests = [];
let mockClientHistory = [];

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

export async function requestClientChange(id, changes, reason) {
  if (shouldUseMock()) {
    const client = mockClients.find((item) => String(item.id) === String(id));
    if (!client) throw createApiError("Cliente no encontrado.");
    const request = { id: nextId(mockClientRequests), client_id: client.id, client_name: client.name, request_type: "modificacion", changes, reason, status: "pendiente" };
    mockClientRequests.unshift(request);
    mockClientHistory.unshift({ id: nextId(mockClientHistory), client_id: client.id, event_type: "modificacion_solicitada", occurred_at: new Date().toISOString(), actor_id: null, reason });
    return request;
  }
  const response = await axiosInstance.post(`/api/clients/${id}/change-requests`, { changes, reason });
  return response.data;
}

export async function requestClientDeactivation(id, reason) {
  if (shouldUseMock()) {
    const client = mockClients.find((item) => String(item.id) === String(id));
    if (!client) throw createApiError("Cliente no encontrado.");
    const request = { id: nextId(mockClientRequests), client_id: client.id, client_name: client.name, request_type: "baja", changes: { status: "inactivo" }, reason, status: "pendiente" };
    mockClientRequests.unshift(request);
    mockClientHistory.unshift({ id: nextId(mockClientHistory), client_id: client.id, event_type: "baja_solicitada", occurred_at: new Date().toISOString(), actor_id: null, reason });
    return request;
  }
  const response = await axiosInstance.post(`/api/clients/${id}/deactivation-requests`, { reason });
  return response.data;
}

export async function getClientChangeRequests() {
  if (shouldUseMock()) return mockClientRequests.filter((item) => item.status === "pendiente");
  const response = await axiosInstance.get('/api/clients/requests/pending');
  return response.data;
}

export async function resolveClientChangeRequest(id, decision, reason) {
  if (shouldUseMock()) {
    const request = mockClientRequests.find((item) => String(item.id) === String(id));
    if (!request || request.status !== "pendiente") throw createApiError("Solicitud no encontrada o ya resuelta.");
    request.status = decision;
    const client = mockClients.find((item) => String(item.id) === String(request.client_id));
    if (decision === "aprobado" && client) Object.assign(client, request.changes, { updated_at: new Date().toISOString() });
    mockClientHistory.unshift({ id: nextId(mockClientHistory), client_id: request.client_id, event_type: `${request.request_type}_${decision}`, occurred_at: new Date().toISOString(), actor_id: null, reason });
    return request;
  }
  const response = await axiosInstance.post(`/api/clients/requests/${id}/resolve`, { decision, reason });
  return response.data;
}

export async function getClientHistory(id) {
  if (shouldUseMock()) return mockClientHistory.filter((item) => String(item.client_id) === String(id));
  const response = await axiosInstance.get(`/api/clients/${id}/history`);
  return response.data;
}

export async function getContractedServices(clientId) {
  const response = await axiosInstance.get(`/api/clients/${clientId}/contracted-services`);
  return response.data;
}

export async function recordContractedService(clientId, payload) {
  const response = await axiosInstance.post(`/api/clients/${clientId}/contracted-services`, payload);
  return response.data;
}

export async function amendContractedService(clientId, serviceId, payload) {
  const response = await axiosInstance.put(`/api/clients/${clientId}/contracted-services/${serviceId}`, payload);
  return response.data;
}
