import assert from "node:assert/strict";
import test from "node:test";

import { normalizeApiError } from "./errorMessage.js";

test("returns a textual detail", () => {
  assert.equal(
    normalizeApiError({ response: { status: 400, data: { detail: "Duplicado" } } }),
    "Duplicado",
  );
});

test("normalizes one FastAPI validation error", () => {
  const message = normalizeApiError({
    response: {
      status: 422,
      data: { detail: [{ loc: ["body", "document_number"], msg: "Muy largo" }] },
    },
  });
  assert.equal(message, "document_number: Muy largo");
});

test("deduplicates and joins multiple validation errors", () => {
  const repeated = { loc: ["body", "name"], msg: "Requerido" };
  const message = normalizeApiError({
    response: {
      status: 422,
      data: { detail: [repeated, repeated, { loc: ["body", "plan"], msg: "Inválido" }] },
    },
  });
  assert.equal(message, "name: Requerido; plan: Inválido");
});

test("uses safe fallbacks for malformed, network and server errors", () => {
  assert.equal(
    normalizeApiError({ response: { status: 422, data: { detail: [{ input: {} }] } } }),
    "No se pudo completar la operación.",
  );
  assert.equal(normalizeApiError(new Error("Network Error")), "No se pudo conectar con el servidor.");
  assert.equal(
    normalizeApiError({ response: { status: 500, data: { detail: { secret: true } } } }),
    "Ocurrió un error interno. Inténtalo nuevamente.",
  );
});

test("always returns a string", () => {
  const cases = [null, {}, { response: { status: 400, data: {} } }];
  for (const value of cases) assert.equal(typeof normalizeApiError(value), "string");
});
