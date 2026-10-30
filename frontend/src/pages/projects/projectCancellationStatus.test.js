import assert from "node:assert/strict";
import test from "node:test";
import { projectCancellationStatus } from "./projectCancellationStatus.js";

const effective = { id: 4, event_type: "efectiva", effective_at: "2026-10-27T20:00:00-05:00", occurred_at: "2026-10-27T20:01:00-05:00" };

test("a cancellation followed by a recorded resumption is historical, not currently effective", () => {
  const result = projectCancellationStatus(
    [{ id: 1, events: [effective] }],
    [{ cancellation_id: 1, events: [{ event_type: "reanudacion_registrada", occurred_at: "2026-10-28T20:00:00-05:00" }] }],
    Date.parse("2026-10-30T12:00:00-05:00"),
  );
  assert.equal(result.current, null);
  assert.equal(result.resumed.cancellation.id, 1);
});

test("an effective cancellation without a later resumption remains current", () => {
  const result = projectCancellationStatus([{ id: 1, events: [effective] }], [], Date.parse("2026-10-30T12:00:00-05:00"));
  assert.equal(result.current.cancellation.id, 1);
  assert.equal(result.resumed, null);
});

test("future effectivity is not presented as a current restriction", () => {
  const future = { ...effective, effective_at: "2026-11-01T20:00:00-05:00" };
  const result = projectCancellationStatus([{ id: 1, events: [future] }], [], Date.parse("2026-10-30T12:00:00-05:00"));
  assert.equal(result.current, null);
  assert.equal(result.resumed, null);
});
