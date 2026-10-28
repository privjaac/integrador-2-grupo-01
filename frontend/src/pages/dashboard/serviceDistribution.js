export function buildServiceDistribution(services, filteredClientIds) {
  const includedIds = filteredClientIds instanceof Set
    ? filteredClientIds
    : new Set(filteredClientIds || []);
  const groups = new Map();

  for (const service of services || []) {
    const serviceType = service.web_type_name || service.service_name;
    if (!includedIds.has(service.client_id) || !serviceType || !service.plan) continue;
    const key = `${service.plan}\u0000${serviceType}`;
    if (!groups.has(key)) {
      groups.set(key, { plan: service.plan, label: serviceType, clientIds: new Set() });
    }
    groups.get(key).clientIds.add(service.client_id);
  }

  return [...groups.values()]
    .map(({ plan, label, clientIds }) => ({ plan, label, value: clientIds.size }));
}
