import axiosInstance from "./axios";
import authMock from "../mocks/auth.json";
import { createApiError, shouldUseMock } from "./helpers";

export async function loginApi(username, password) {
  if (shouldUseMock()) {
    const validUsername = authMock.login_success?.username || "elomux";
    const validPassword = authMock.login_success?.password || "elomux123";

    if (username !== validUsername || password !== validPassword) {
      throw createApiError("Usuario o contraseña incorrectos.");
    }

    return {
      access_token: authMock.login_success?.access_token || "mock_access_token",
      refresh_token: authMock.login_success?.refresh_token || "mock_refresh_token",
      user: authMock.user,
    };
  }

  const response = await axiosInstance.post("/api/auth/login", {
    username,
    password,
  });

  if (response.data.user) return response.data;

  return {
    ...response.data,
    user: await getCurrentUser(),
  };
}

export async function getCurrentUser() {
  const response = await axiosInstance.get("/api/users/me");
  return response.data;
}
