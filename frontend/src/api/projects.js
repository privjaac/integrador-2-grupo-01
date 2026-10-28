import axiosInstance from "./axios";

export async function getProjects() {
  const { data } = await axiosInstance.get("/api/projects/");
  return data;
}

export async function createProject(payload) {
  const { data } = await axiosInstance.post("/api/projects/", payload);
  return data;
}

export async function enterTechnicalValidation(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/technical-validation`, payload);
  return data;
}

export async function returnProjectToExecution(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/return-to-execution`, payload);
  return data;
}

export async function getDeliveryContext(projectId) {
  const { data } = await axiosInstance.get(`/api/projects/${projectId}/delivery-context`);
  return data;
}

export async function classifyProjectTask(projectId, taskId, payload) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/tasks/${taskId}/delivery-classification`, payload,
  );
  return data;
}

export async function recordTechnicalEvaluation(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/technical-evaluations`, payload);
  return data;
}

export async function getDeliveryAuthorizations(projectId) {
  const { data } = await axiosInstance.get(`/api/projects/${projectId}/delivery-authorizations`);
  return data;
}

export async function createDeliveryAuthorization(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/delivery-authorizations`, payload);
  return data;
}

export async function withdrawDeliveryAuthorization(projectId, authorizationId, reason) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/delivery-authorizations/${authorizationId}/withdrawal`, { reason },
  );
  return data;
}

export async function markProjectReadyForDelivery(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/ready-for-delivery`, payload);
  return data;
}

export async function getProjectDeliveries(projectId) {
  const { data } = await axiosInstance.get(`/api/projects/${projectId}/deliveries`);
  return data;
}

export async function recordProjectDelivery(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/deliveries`, payload);
  return data;
}

export async function reviewProjectDeliveryVersion(projectId, payload) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/delivery-version-reviews`, payload,
  );
  return data;
}

export async function formalizeProjectDelivery(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/deliveries/formalize`, payload);
  return data;
}

export async function getCommercialAuthorizations(projectId) {
  const { data } = await axiosInstance.get(`/api/projects/${projectId}/commercial-authorizations`);
  return data;
}

export async function createCommercialAuthorization(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/commercial-authorizations`, payload);
  return data;
}

export async function withdrawCommercialAuthorization(projectId, authorizationId, reason) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/commercial-authorizations/${authorizationId}/withdrawal`, { reason },
  );
  return data;
}

export async function startProject(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/start`, payload);
  return data;
}

export async function getProjectContractedServices(projectId) {
  const { data } = await axiosInstance.get(`/api/projects/${projectId}/contracted-services`);
  return data;
}

export async function linkContractedService(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/contracted-services`, payload);
  return data;
}

export async function unlinkContractedService(projectId, linkId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/contracted-services/${linkId}/withdrawal`, payload);
  return data;
}

export async function getProjectCancellations(projectId) {
  const { data } = await axiosInstance.get(`/api/projects/${projectId}/cancellations`);
  return data;
}

export async function getL1ExceptionalCancellations() {
  const { data } = await axiosInstance.get("/api/projects/exceptional-cancellations");
  return data;
}

export async function getL1ExceptionalResumptions() {
  const { data } = await axiosInstance.get("/api/projects/exceptional-resumptions");
  return data;
}

export async function getL1SubstitutionContext() {
  const { data } = await axiosInstance.get("/api/projects/substitutions/context");
  return data;
}

export async function getProjectSubstitutions(projectId) {
  const { data } = await axiosInstance.get(`/api/projects/${projectId}/substitutions`);
  return data;
}

export async function createProjectSubstitution(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/substitutions`, payload);
  return data;
}

export async function endProjectSubstitution(projectId, substitutionId) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/substitutions/${substitutionId}/end`,
  );
  return data;
}

export async function openProjectCancellation(projectId, payload) {
  const { data } = await axiosInstance.post(`/api/projects/${projectId}/cancellations`, payload);
  return data;
}

export async function evaluateProjectCancellation(projectId, cancellationId, payload) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/cancellations/${cancellationId}/technical-evaluation`, payload,
  );
  return data;
}

export async function evaluateProjectCancellationCommercially(projectId, cancellationId, payload) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/cancellations/${cancellationId}/commercial-evaluation`, payload,
  );
  return data;
}

export async function decideProjectCancellationExceptionally(projectId, cancellationId, payload) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/cancellations/${cancellationId}/exceptional-decision`, payload,
  );
  return data;
}

export async function decideProjectCancellation(projectId, cancellationId, payload) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/cancellations/${cancellationId}/decision`, payload,
  );
  return data;
}

export async function recordProjectCancellationEffectivity(projectId, cancellationId, payload) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/cancellations/${cancellationId}/effectivity`, payload,
  );
  return data;
}

export async function getProjectResumptions(projectId) {
  const { data } = await axiosInstance.get(`/api/projects/${projectId}/resumptions`);
  return data;
}

export async function evaluateProjectResumption(projectId, cancellationId, payload) {
  const { data } = await axiosInstance.post(
    `/api/projects/${projectId}/cancellations/${cancellationId}/resumption/technical-evaluation`, payload,
  );
  return data;
}

export async function decideProjectResumptionCommercially(resumptionId, payload) {
  const { data } = await axiosInstance.post(
    `/api/projects/resumptions/${resumptionId}/commercial-decision`, payload,
  );
  return data;
}

export async function decideProjectResumptionExceptionally(resumptionId, payload) {
  const { data } = await axiosInstance.post(
    `/api/projects/resumptions/${resumptionId}/exceptional-decision`, payload,
  );
  return data;
}
