import assert from "node:assert/strict";
import test from "node:test";
import { loadRecordWithOptionalHistories } from "./detailLoader.js";

test("keeps the requested record when an optional history request fails", async () => {
  const record = { id: 42, name: "DEMO · Café Aurora" };
  const result = await loadRecordWithOptionalHistories(
    async () => record,
    [async () => [{ id: 1 }], async () => { throw new Error("history unavailable"); }],
  );

  assert.equal(result.record, record);
  assert.deepEqual(result.histories, [[{ id: 1 }], []]);
  assert.equal(result.hasHistoryError, true);
});

test("rejects when the primary record cannot be loaded", async () => {
  await assert.rejects(
    () => loadRecordWithOptionalHistories(
      async () => { throw new Error("record unavailable"); },
      [async () => []],
    ),
    /record unavailable/,
  );
});
