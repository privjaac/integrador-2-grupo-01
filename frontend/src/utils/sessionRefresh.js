let refreshInFlight = null;

export function isDefinitiveSessionFailure(error) {
  return error?.response?.status === 401;
}

export function withCoordinatedRefresh(readRefreshToken, operation) {
  if (refreshInFlight) return refreshInFlight;

  const run = async () => {
    let refreshToken = readRefreshToken();
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        return await operation(refreshToken);
      } catch (error) {
        const latestToken = readRefreshToken();
        if (
          attempt === 0
          && isDefinitiveSessionFailure(error)
          && latestToken
          && latestToken !== refreshToken
        ) {
          refreshToken = latestToken;
          continue;
        }
        throw error;
      }
    }
    return null;
  };

  const coordinate = () => {
    if (typeof navigator !== "undefined" && navigator.locks?.request) {
      return navigator.locks.request("elisa-refresh-token-rotation", run);
    }
    return run();
  };

  refreshInFlight = Promise.resolve().then(coordinate).finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}
