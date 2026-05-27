/**
 * API client — Anonymous Sessions for Aurora Architecture.
 * Replaces complex JWT auth with a simple local UUID.
 */

export function getUserId() {
  let uid = localStorage.getItem('anon_user_id');
  if (!uid) {
    uid = crypto.randomUUID();
    localStorage.setItem('anon_user_id', uid);
  }
  return uid;
}

// ── Headers ────────────────────────────────────────────────
function getHeaders() {
  return {
    'Content-Type': 'application/json',
    'X-User-Id': getUserId(),
  };
}

// ── API fetch wrapper ──────────────────────────────────────
export async function authFetch(url, options = {}) {
  const headers = { ...getHeaders(), ...(options.headers || {}) };
  return fetch(url, { ...options, headers });
}
