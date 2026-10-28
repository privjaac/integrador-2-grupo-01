import test from "node:test";
import assert from "node:assert/strict";
import { buildServiceDistribution } from "./serviceDistribution.js";

test("PB-REP-007 counts distinct clients only through active contracted service rows", () => {
  const distribution = buildServiceDistribution([
    { client_id: 1, plan: "alquiler", web_type_name: "Web A" },
    { client_id: 1, plan: "alquiler", web_type_name: "Web A" },
    { client_id: 2, plan: "alquiler", web_type_name: "Web A" },
    { client_id: 1, plan: "venta", web_type_name: "Web B" },
    { client_id: 3, plan: "venta", web_type_name: null, service_name: "Servicio sin catálogo" },
    { client_id: 4, plan: "", web_type_name: "Web C" },
  ], new Set([1, 2, 3, 4]));

  assert.deepEqual(distribution, [
    { plan: "alquiler", label: "Web A", value: 2 },
    { plan: "venta", label: "Web B", value: 1 },
    { plan: "venta", label: "Servicio sin catálogo", value: 1 },
  ]);
});

test("PB-REP-007 respects the selected client date filter", () => {
  assert.deepEqual(buildServiceDistribution([
    { client_id: 1, plan: "alquiler", web_type_name: "Web A" },
    { client_id: 2, plan: "alquiler", web_type_name: "Web A" },
  ], new Set([2])), [
    { plan: "alquiler", label: "Web A", value: 1 },
  ]);
});
