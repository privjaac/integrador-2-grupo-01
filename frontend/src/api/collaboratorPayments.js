import axiosInstance from "./axios";

export async function getCollaboratorPayments(filters = {}) {
  const response = await axiosInstance.get("/api/collaborators/payments/", { params: filters });
  return response.data;
}

export async function recordCollaboratorPayment(payload, requestKey) {
  const response = await axiosInstance.post("/api/collaborators/payments/", payload, {
    headers: { "Idempotency-Key": requestKey },
  });
  return response.data;
}
