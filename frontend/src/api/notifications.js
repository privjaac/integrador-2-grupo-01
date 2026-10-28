import axiosInstance from "./axios";

export async function getInternalNotifications() {
  const { data } = await axiosInstance.get("/api/notifications/internal/");
  return data;
}

export async function markInternalNotificationRead(id) {
  const { data } = await axiosInstance.patch(`/api/notifications/internal/${id}/read`);
  return data;
}
