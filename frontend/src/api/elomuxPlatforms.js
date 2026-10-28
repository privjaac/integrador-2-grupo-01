import axiosInstance from "./axios";

export async function getElomuxPlatforms() {
  const response = await axiosInstance.get("/api/elomux-platforms/");
  return response.data;
}

export async function createElomuxPlatform(data) {
  const response = await axiosInstance.post("/api/elomux-platforms/", data);
  return response.data;
}

export async function updateElomuxPlatform(id, data) {
  const response = await axiosInstance.put(`/api/elomux-platforms/${id}`, data);
  return response.data;
}
