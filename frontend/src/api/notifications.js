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

export async function getCommercialNoticeConfig() {
  const { data } = await axiosInstance.get("/api/notifications/commercial-notice-config");
  return data;
}

export async function updateCommercialNoticeConfig(channel, payload) {
  const { data } = await axiosInstance.put(`/api/notifications/commercial-notice-config/${channel}`, payload);
  return data;
}

export async function getUpcomingCommercialNotices(params = {}) {
  const { data } = await axiosInstance.get("/api/notifications/upcoming", { params });
  return data;
}

export async function getCommercialNoticeLogs(params = {}) {
  const { data } = await axiosInstance.get("/api/notifications/logs", { params });
  return data;
}

export async function getCommercialNoticeDetail(id) {
  const { data } = await axiosInstance.get(`/api/notifications/logs/${id}`);
  return data;
}

export async function resendCommercialNotice(id) {
  const { data } = await axiosInstance.post(`/api/notifications/logs/${id}/resend`);
  return data;
}
