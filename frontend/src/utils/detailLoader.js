export async function loadRecordWithOptionalHistories(loadRecord, historyLoaders) {
  const record = await loadRecord();
  const settledHistories = await Promise.allSettled(historyLoaders.map((loadHistory) => loadHistory()));

  return {
    record,
    histories: settledHistories.map((result) => result.status === "fulfilled" ? result.value : []),
    hasHistoryError: settledHistories.some((result) => result.status === "rejected"),
  };
}
