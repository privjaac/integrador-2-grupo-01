import axiosInstance from "./axios";

export async function loginApi(username, password) {
  const { data } = await axiosInstance.post("/api/auth/login", {
    username,
    password,
  });
  return data;
}
