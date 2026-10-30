import assert from "node:assert/strict";
import test from "node:test";
import { isNotificationInboxOutOfScope, notificationDestination } from "./notificationErrors.js";

test("recognizes the API response for an inbox outside the user's scope", () => {
  assert.equal(isNotificationInboxOutOfScope({
    response: { status: 403, data: { detail: "El rol no tiene un ámbito propio de notificaciones" } },
  }), true);
});

test("does not hide unrelated authorization or server errors", () => {
  assert.equal(isNotificationInboxOutOfScope({ response: { status: 403, data: { detail: "Cuenta inactiva" } } }), false);
  assert.equal(isNotificationInboxOutOfScope({ response: { status: 500, data: {} } }), false);
});

test("routes notification clicks to the corresponding view only when the user can access it", () => {
  assert.equal(notificationDestination({ task_id: 28 }, { role: "L5" }), "/tareas/detalle/28");
  assert.equal(notificationDestination({ event_type: "commercial_payment_reminder" }, { role: "L3" }), "/notificaciones-alertas");
  assert.equal(notificationDestination({ event_type: "commercial_payment_reminder" }, { role: "L4" }), null);
});
