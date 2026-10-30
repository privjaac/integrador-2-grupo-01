import assert from "node:assert/strict";
import test from "node:test";
import { isDefinitiveSessionFailure, withCoordinatedRefresh } from "./sessionRefresh.js";

test("only an explicit 401 is treated as a definitive invalid session", () => {
  assert.equal(isDefinitiveSessionFailure({ response: { status: 401 } }), true);
  assert.equal(isDefinitiveSessionFailure({ response: { status: 403 } }), false);
  assert.equal(isDefinitiveSessionFailure({ response: { status: 500 } }), false);
  assert.equal(isDefinitiveSessionFailure(new Error("network unavailable")), false);
});

test("coalesces overlapping refresh attempts in one browser context", async () => {
  let calls = 0;
  let resolveOperation;
  let resolveStarted;
  const started = new Promise((resolve) => { resolveStarted = resolve; });
  const operation = () => {
    calls += 1;
    resolveStarted();
    return new Promise((resolve) => { resolveOperation = resolve; });
  };
  const first = withCoordinatedRefresh(() => "refresh-a", operation);
  const second = withCoordinatedRefresh(() => "refresh-a", operation);

  await started;
  assert.equal(calls, 1);
  resolveOperation("rotated");
  assert.deepEqual(await Promise.all([first, second]), ["rotated", "rotated"]);
});

test("retries once with a token rotated by another tab after a stale-token 401", async () => {
  let currentToken = "refresh-old";
  const used = [];
  const result = await withCoordinatedRefresh(
    () => currentToken,
    async (token) => {
      used.push(token);
      if (token === "refresh-old") {
        currentToken = "refresh-new";
        throw { response: { status: 401 } };
      }
      return "access-restored";
    },
  );

  assert.equal(result, "access-restored");
  assert.deepEqual(used, ["refresh-old", "refresh-new"]);
});
