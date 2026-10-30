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
    user: await getCurrentUser(response.data.access_token),
  };
}

export async function getCurrentUser(accessToken) {
  const response = await axiosInstance.get("/api/users/me", {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    skipAuthRefresh: true,
  });
  return response.data;
}

export async function requestPasswordRecovery(email) {
  return axiosInstance.post("/api/auth/forgot-password", { email: email.trim().toLowerCase() });
}

export async function resetPassword(token, newPassword, confirmPassword) {
  return axiosInstance.put("/api/auth/reset-password", {
    token, new_password: newPassword, confirm_password: confirmPassword,
  });
}
