import axiosInstance from "./axios";

export async function getInternalNotifications() {
  const { data } = await axiosInstance.get("/api/notifications/internal/");
  return data;
}

export async function markInternalNotificationRead(id) {
  const { data } = await axiosInstance.patch(`/api/notifications/internal/${id}/read`);
  return data;
}

export async function getTaskDeadlineSettings() {
  const { data } = await axiosInstance.get("/api/notifications/internal/task-deadline-settings");
  return data;
}

export async function updateTaskDeadlineSettings(payload) {
  const { data } = await axiosInstance.put("/api/notifications/internal/task-deadline-settings", payload);
  return data;
}
