const ACCESS_TOKEN_KEY = "shopfast_access_token";
const REFRESH_TOKEN_KEY = "shopfast_refresh_token";

export function saveSession(session) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, session.access_token);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, session.refresh_token);
}

export function accessToken() {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function refreshToken() {
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function clearSession() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}
