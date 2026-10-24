import axiosInstance from "./axios";

export async function getProjects() {
  const { data } = await axiosInstance.get("/api/projects/");
  return data;
}

export async function createProject(payload) {
  const { data } = await axiosInstance.post("/api/projects/", payload);
  return data;
}
