/**
 * auth.js — Supabase authentication client
 * Handles sign up, login, logout, session management.
 */

// ── Supabase client setup ──────────────────────────────────
// These will be populated from the app config
let SUPABASE_URL = '';
let SUPABASE_ANON_KEY = '';
let supabaseClient = null;

function initSupabaseAuth(url, anonKey) {
    SUPABASE_URL = url;
    SUPABASE_ANON_KEY = anonKey;
    if (window.supabase) {
        supabaseClient = window.supabase.createClient(url, anonKey);
    }
}

// ── Token management ───────────────────────────────────────
function getAccessToken() {
    return localStorage.getItem('access_token') || '';
}

function getRefreshToken() {
    return localStorage.getItem('refresh_token') || '';
}

function setTokens(access, refresh) {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
}

function clearTokens() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
}

function getStoredUser() {
    try {
        return JSON.parse(localStorage.getItem('user') || 'null');
    } catch {
        return null;
    }
}

function setStoredUser(user) {
    localStorage.setItem('user', JSON.stringify(user));
}

// ── Auth header helper ─────────────────────────────────────
function authHeaders() {
    const token = getAccessToken();
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
    };
}

// ── Auth API calls ─────────────────────────────────────────
async function signUp(email, password, displayName) {
    const resp = await fetch('/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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

async function signIn(email, password) {
    const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
    });

    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || 'Login failed');

    setTokens(data.access_token, data.refresh_token);
    setStoredUser(data.user);
    return data;
}

async function signOut() {
    try {
        await fetch('/api/auth/logout', {
            method: 'POST',
            headers: authHeaders(),
        });
    } catch { /* ignore */ }
    clearTokens();
}

async function getMe() {
    const resp = await fetch('/api/auth/me', { headers: authHeaders() });
    if (!resp.ok) throw new Error('Not authenticated');
    return await resp.json();
}

// ── Session check ──────────────────────────────────────────
function isAuthenticated() {
    return !!getAccessToken();
}

// ── Auth UI handlers ───────────────────────────────────────
let authMode = 'login'; // 'login' or 'signup'

function switchAuthTab(mode) {
    authMode = mode;
    document.getElementById('tab-login').classList.toggle('active', mode === 'login');
    document.getElementById('tab-signup').classList.toggle('active', mode === 'signup');
    document.getElementById('signup-name-field').classList.toggle('hidden', mode === 'login');
    document.getElementById('auth-submit-text').textContent = mode === 'login' ? 'Sign In' : 'Create Account';
    document.getElementById('auth-error').classList.add('hidden');
}

async function handleAuth(e) {
    e.preventDefault();

    const email = document.getElementById('auth-email').value.trim();
    const password = document.getElementById('auth-password').value;
    const name = document.getElementById('auth-name')?.value?.trim() || '';
    const errorEl = document.getElementById('auth-error');
    const submitBtn = document.getElementById('auth-submit');
    const submitText = document.getElementById('auth-submit-text');
    const spinner = document.getElementById('auth-spinner');

    errorEl.classList.add('hidden');
    submitBtn.disabled = true;
    submitText.textContent = authMode === 'login' ? 'Signing in...' : 'Creating account...';
    spinner.classList.remove('hidden');

    try {
        if (authMode === 'signup') {
            await signUp(email, password, name);
        } else {
            await signIn(email, password);
        }
        // Success — switch to app
        showApp();
    } catch (err) {
        errorEl.textContent = err.message;
        errorEl.classList.remove('hidden');
    } finally {
        submitBtn.disabled = false;
        submitText.textContent = authMode === 'login' ? 'Sign In' : 'Create Account';
        spinner.classList.add('hidden');
    }

    return false;
}

async function handleLogout() {
    await signOut();
    showAuth();
}
