/**
 * app.js — Main application orchestrator
 * Initializes the app, manages views, providers, sessions.
 */

let providersData = [];

// ═══════════════════════════════════════════════════════════
// App Initialization
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    // Check auth state
    if (isAuthenticated()) {
        showApp();
    } else {
        showAuth();
    }

    // Input handlers
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        chatInput.addEventListener('input', autoResizeInput);
    }
});

// ═══════════════════════════════════════════════════════════
// View Management
// ═══════════════════════════════════════════════════════════
function showAuth() {
    document.getElementById('auth-screen').classList.remove('hidden');
    document.getElementById('app-root').classList.add('hidden');
}

function showApp() {
    document.getElementById('auth-screen').classList.add('hidden');
    document.getElementById('app-root').classList.remove('hidden');

    // Load user info
    const user = getStoredUser();
    if (user) {
        const email = user.email || '';
        document.getElementById('user-email').textContent = email;
        document.getElementById('user-avatar').textContent = email.charAt(0).toUpperCase();
    }

    // Load data
    loadProviders();
    loadSessions();
    loadKeys();
    loadAgents();
}

function switchView(view) {
    // Update nav
    document.querySelectorAll('.sidebar-nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.view === view);
    });

    // Update views
    document.querySelectorAll('.view-container').forEach(container => {
        container.classList.toggle('active', container.id === `${view}-view`);
    });
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('open');
}

// ═══════════════════════════════════════════════════════════
// Provider/Model Management
// ═══════════════════════════════════════════════════════════
async function loadProviders() {
    try {
        const resp = await authFetch('/api/providers');
        if (!resp.ok) return;

        providersData = await resp.json();
        const providerSelect = document.getElementById('provider-select');

        providerSelect.innerHTML = '<option value="">Select provider...</option>';
        for (const provider of providersData) {
            const opt = document.createElement('option');
            opt.value = provider.id;
            opt.textContent = provider.name + (provider.has_user_key ? ' ✓' : '');
            providerSelect.appendChild(opt);
        }

        // Also update agent provider models
        updateAgentModels();

    } catch (err) {
        console.error('Failed to load providers:', err);
    }
}

function onProviderChange() {
    const providerId = document.getElementById('provider-select').value;
    const modelSelect = document.getElementById('model-select');

    modelSelect.innerHTML = '<option value="">Select model...</option>';

    const provider = providersData.find(p => p.id === providerId);
    if (provider && provider.models) {
        for (const model of provider.models) {
            const opt = document.createElement('option');
            opt.value = model.id;
            opt.textContent = model.name + (model.context ? ` (${Math.round(model.context / 1000)}K)` : '');
            modelSelect.appendChild(opt);
        }
    }
}

function onModelChange() {
    // Could save preference, etc.
}

// ═══════════════════════════════════════════════════════════
// Session Management
// ═══════════════════════════════════════════════════════════
async function loadSessions() {
    try {
        const resp = await authFetch('/api/sessions?limit=30');
        if (!resp.ok) return;

        const sessions = await resp.json();
        const container = document.getElementById('session-list');

        if (sessions.length === 0) {
            container.innerHTML = `
                <div style="padding:12px 8px; color:var(--text-muted); font-size:11px; text-align:center;">
                    No conversations yet
                </div>
            `;
            return;
        }

        container.innerHTML = sessions.map(s => {
            const isActive = currentSessionId === s.id;
            const timeAgo = formatTimeAgo(new Date(s.updated_at));
            return `
                <div class="session-item ${isActive ? 'active' : ''}" data-id="${s.id}" onclick="loadSession('${s.id}')">
                    <span class="session-item-title">${escapeHtml(s.title)}</span>
                    <span class="session-item-meta">${s.message_count}msg</span>
                    <button class="session-item-delete" onclick="event.stopPropagation(); deleteSession('${s.id}')" title="Delete">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>
                </div>
            `;
        }).join('');

    } catch (err) {
        console.error('Failed to load sessions:', err);
    }
}

async function deleteSession(sessionId) {
    if (!confirm('Delete this conversation?')) return;

    try {
        await authFetch(`/api/sessions/${sessionId}`, {
            method: 'DELETE',
        });

        if (currentSessionId === sessionId) {
            clearChat();
        }
        loadSessions();
        showToast('Conversation deleted', 'success');
    } catch (err) {
        showToast('Failed to delete', 'error');
    }
}

// ═══════════════════════════════════════════════════════════
// Toast Notifications
// ═══════════════════════════════════════════════════════════
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ═══════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════
function formatTimeAgo(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'now';
    if (diffMins < 60) return `${diffMins}m`;
    if (diffHours < 24) return `${diffHours}h`;
    if (diffDays < 7) return `${diffDays}d`;
    return date.toLocaleDateString();
}
