import axiosInstance from "./axios";
import { getClients } from "./clients";
import { getCollaborators } from "./users";
import { shouldUseMock } from "./helpers";

export async function getDashboardSummary() {
  if (shouldUseMock()) {
    const [clients, collaborators] = await Promise.all([getClients(), getCollaborators()]);
    return {
      clients: clients.map(({ id, cupe, name, plan, status, registration_date, web_type_name }) =>
        ({ id, cupe, name, plan, status, registration_date, web_type_name })),
      collaborators: {
        total: collaborators.length,
        active: collaborators.filter((item) => item.is_active).length,
        inactive: collaborators.filter((item) => !item.is_active).length,
      },
      services: {
        active: [], upcoming_expirations_30_days: [],
        upcoming_recurrences_30_days: [], expired: [],
      },
      monthly_revenue: [],
    };
  }
  const response = await axiosInstance.get("/api/dashboard/summary");
  return response.data;
}
