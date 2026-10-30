import {accessToken, clearSession, refreshToken, saveSession} from "./session.js";

const API_ROOT = "/api";

async function refreshAccessToken() {
  const response = await fetch(`${API_ROOT}/auth/refresh`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({refresh_token: refreshToken()}),
  });
  if (!response.ok) {
    clearSession();
    throw new Error("Your session has expired");
  }
  const session = await response.json();
  saveSession(session);
  return session.access_token;
}

export async function api(path, options = {}, retry = true) {
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (accessToken()) headers.set("Authorization", `Bearer ${accessToken()}`);
  const response = await fetch(`${API_ROOT}${path}`, {...options, headers});
  if (response.status === 401 && retry && refreshToken()) {
    await refreshAccessToken();
    return api(path, options, false);
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({detail: "Request failed"}));
    throw new Error(error.detail);
  }
  if (response.status === 204) return null;
  return response.json();
}
