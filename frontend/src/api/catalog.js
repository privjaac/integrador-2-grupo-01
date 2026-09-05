import axiosInstance from "./axios";
import catalogMock from "../mocks/catalog.json";
import { createApiError, nextId, normalizeList, shouldUseMock } from "./helpers";

let mockWebTypes = normalizeList(catalogMock, "web_types");
let mockWebFeatures = normalizeList(catalogMock, "web_features");

export async function getWebTypes(activeOnly = false) {
  if (shouldUseMock()) {
    return activeOnly
      ? mockWebTypes.filter((item) => item.is_active !== false)
      : [...mockWebTypes];
  }

  const response = await axiosInstance.get("/api/web-types/", {
    params: activeOnly ? { is_active: true } : {},
  });
  return normalizeList(response.data, "web_types");
}

export async function createWebType(payload) {
  if (shouldUseMock()) {
    const item = { ...payload, id: nextId(mockWebTypes), is_active: true };
    mockWebTypes = [...mockWebTypes, item];
    return item;
  }

  const response = await axiosInstance.post("/api/web-types/", payload);
  return response.data;
}

export async function getWebFeatures(webTypeId = null, activeOnly = false) {
  if (shouldUseMock()) {
    let features = [...mockWebFeatures];
    if (webTypeId) {
      features = features.filter(
        (item) => !item.web_type_id || String(item.web_type_id) === String(webTypeId),
      );
    }
    return activeOnly
      ? features.filter((item) => item.is_active !== false)
      : features;
  }

  const response = await axiosInstance.get("/api/web-features/", {
    params: {
      ...(webTypeId ? { web_type_id: webTypeId } : {}),
      ...(activeOnly ? { is_active: true } : {}),
    },
  });
  return normalizeList(response.data, "web_features");
}

export async function createWebFeature(payload) {
  if (shouldUseMock()) {
    const item = { ...payload, id: nextId(mockWebFeatures), is_active: true };
    mockWebFeatures = [...mockWebFeatures, item];
    return item;
  }

  const response = await axiosInstance.post("/api/web-features/", payload);
  return response.data;
}

export async function updateWebType(id, payload) {
  if (shouldUseMock()) {
    const index = mockWebTypes.findIndex((item) => String(item.id) === String(id));
    if (index === -1) throw createApiError("Tipo de web no encontrado.");
    mockWebTypes[index] = { ...mockWebTypes[index], ...payload };
    return mockWebTypes[index];
  }

  const response = await axiosInstance.put(`/api/web-types/${id}`, payload);
  return response.data;
}

export async function updateWebFeature(id, payload) {
  if (shouldUseMock()) {
    const index = mockWebFeatures.findIndex((item) => String(item.id) === String(id));
    if (index === -1) throw createApiError("Funcionalidad no encontrada.");
    mockWebFeatures[index] = { ...mockWebFeatures[index], ...payload };
    return mockWebFeatures[index];
  }

  const response = await axiosInstance.put(`/api/web-features/${id}`, payload);
  return response.data;
}
