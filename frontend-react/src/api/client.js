/**
 * API client — token management, authFetch, DB mode.
 * Drop-in replacement for the vanilla auth.js utility layer.
 */

// ── Token helpers ──────────────────────────────────────────
export function getAccessToken() {
  return localStorage.getItem('access_token') || '';
}
export function getRefreshToken() {
  return localStorage.getItem('refresh_token') || '';
}
export function setTokens(access, refresh) {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
  localStorage.setItem('token_expires_at', (Date.now() + 3600 * 1000).toString());
}
export function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('token_expires_at');
  localStorage.removeItem('user');
}
export function getStoredUser() {
  try { return JSON.parse(localStorage.getItem('user') || 'null'); } catch { return null; }
}
export function setStoredUser(user) {
  localStorage.setItem('user', JSON.stringify(user));
}
function isTokenExpired() {
  const exp = parseInt(localStorage.getItem('token_expires_at') || '0');
  return Date.now() > exp - 720_000;
}

// ── DB Mode ────────────────────────────────────────────────
export function getDbMode() {
  return localStorage.getItem('db_mode') || 'supabase';
}
export function setDbMode(mode) {
  localStorage.setItem('db_mode', mode);
}

// ── Headers ────────────────────────────────────────────────
function authHeaders() {
  return {
    Authorization: `Bearer ${getAccessToken()}`,
    'Content-Type': 'application/json',
    'X-DB-Mode': getDbMode(),
  };
}

// ── Token refresh ──────────────────────────────────────────
let refreshPromise = null;
async function ensureValidToken() {
  if (!getAccessToken() || !getRefreshToken()) return;
  if (!isTokenExpired()) return;
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const resp = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-DB-Mode': getDbMode() },
        body: JSON.stringify({ refresh_token: getRefreshToken() }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setTokens(data.access_token, data.refresh_token);
      } else {
        clearTokens();
      }
    } catch { /* ignore */ }
    finally { refreshPromise = null; }
  })();
  return refreshPromise;
}

// ── Authenticated fetch ────────────────────────────────────
export async function authFetch(url, options = {}) {
  await ensureValidToken();
  const headers = { ...authHeaders(), ...(options.headers || {}) };
  const resp = await fetch(url, { ...options, headers });
  if (resp.status === 401 && getRefreshToken()) {
    localStorage.setItem('token_expires_at', '0');
    await ensureValidToken();
    const retryHeaders = { ...authHeaders(), ...(options.headers || {}) };
    return fetch(url, { ...options, headers: retryHeaders });
  }
  return resp;
}

// ── Auth API ───────────────────────────────────────────────
export async function apiSignUp(email, password, displayName) {
  const resp = await fetch('/api/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-DB-Mode': getDbMode() },
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || 'Sign up failed');
  if (data.access_token) {
    setTokens(data.access_token, data.refresh_token);
    setStoredUser(data.user);
  }
  return data;
}

export async function apiSignIn(email, password) {
  const resp = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-DB-Mode': getDbMode() },
    body: JSON.stringify({ email, password }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || 'Login failed');
  setTokens(data.access_token, data.refresh_token);
  setStoredUser(data.user);
  return data;
}

export async function apiSignOut() {
  try {
    await fetch('/api/auth/logout', { method: 'POST', headers: authHeaders() });
  } catch { /* ignore */ }
  clearTokens();
}
