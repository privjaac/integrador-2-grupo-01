import axiosInstance from "./axios";

export async function getWebTypes(isActive) {
  const params = isActive === undefined ? {} : { is_active: isActive };
  const { data } = await axiosInstance.get("/api/web-types/", { params });
  return data;
}

export async function createWebType(payload) {
  const { data } = await axiosInstance.post("/api/web-types/", payload);
  return data;
}

export async function updateWebType(id, payload) {
  const { data } = await axiosInstance.put(`/api/web-types/${id}`, payload);
  return data;
}

export async function getWebFeatures(webTypeId, isActive) {
  const params = isActive === undefined ? {} : { is_active: isActive };
  const { data } = await axiosInstance.get("/api/web-features/", { params });
  return data;
}

export async function createWebFeature(payload) {
  const { data } = await axiosInstance.post("/api/web-features/", payload);
  return data;
}

export async function updateWebFeature(id, payload) {
  const { data } = await axiosInstance.put(`/api/web-features/${id}`, payload);
  return data;
}
