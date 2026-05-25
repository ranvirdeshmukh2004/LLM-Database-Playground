/**
 * keys.js — API key management UI
 */

const PROVIDER_NAMES = {
    openrouter: 'OpenRouter',
    anthropic: 'Anthropic (Claude)',
    xai: 'xAI (Grok)',
    openai: 'OpenAI',
    custom: 'Self-Hosted',
};

const PROVIDER_INITIALS = {
    openrouter: 'OR',
    anthropic: 'AN',
    xai: 'xA',
    openai: 'OA',
    custom: 'SH',
};

// ── Load keys ──────────────────────────────────────────────
async function loadKeys() {
    try {
        const resp = await fetch('/api/keys', { headers: authHeaders() });
        if (!resp.ok) return;

        const keys = await resp.json();
        const container = document.getElementById('keys-list');

        if (keys.length === 0) {
            container.innerHTML = `
                <div style="text-align:center; padding:20px; color:var(--text-muted); font-size:13px;">
                    No API keys configured yet. Add one below to get started.
                </div>
            `;
            return;
        }

        container.innerHTML = keys.map(key => `
            <div class="key-card">
                <div class="key-card-info">
                    <div class="key-card-icon ${key.provider}">
                        ${PROVIDER_INITIALS[key.provider] || '??'}
                    </div>
                    <div class="key-card-details">
                        <h4>${PROVIDER_NAMES[key.provider] || key.provider}</h4>
                        <p>${key.key_preview}</p>
                    </div>
                </div>
                <div class="key-card-actions">
                    <span class="key-status ${key.is_active ? 'active' : 'inactive'}">
                        <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:currentColor;"></span>
                        ${key.is_active ? 'Active' : 'Inactive'}
                    </span>
                    <button class="key-action-btn" onclick="testKey('${key.id}')">Test</button>
                    <button class="key-action-btn delete" onclick="deleteKey('${key.id}')">Delete</button>
                </div>
            </div>
        `).join('');

    } catch (err) {
        console.error('Failed to load keys:', err);
    }
}

// ── Add key ────────────────────────────────────────────────
async function handleAddKey(e) {
    e.preventDefault();

    const provider = document.getElementById('key-provider').value;
    const keyName = document.getElementById('key-name').value.trim() || 'default';
    const apiKey = document.getElementById('key-value').value.trim();

    if (!apiKey) {
        showToast('Please enter an API key', 'error');
        return false;
    }

    try {
        const resp = await fetch('/api/keys', {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({
                provider,
                api_key: apiKey,
                key_name: keyName,
            }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Failed to save key');
        }

        showToast(`${PROVIDER_NAMES[provider]} key saved (encrypted)`, 'success');
        document.getElementById('key-value').value = '';
        loadKeys();
        loadProviders(); // Refresh provider list to update has_user_key

    } catch (err) {
        showToast(err.message, 'error');
    }

    return false;
}

// ── Test key ───────────────────────────────────────────────
async function testKey(keyId) {
    try {
        showToast('Testing API key...', 'info');
        const resp = await fetch(`/api/keys/${keyId}/test`, {
            method: 'POST',
            headers: authHeaders(),
        });

        const result = await resp.json();

        if (result.status === 'valid') {
            showToast(`API key is valid (${result.latency_ms}ms)`, 'success');
        } else if (result.status === 'invalid') {
            showToast(`Invalid API key: ${result.detail}`, 'error');
        } else {
            showToast(`Test error: ${result.detail}`, 'error');
        }
    } catch (err) {
        showToast(`Test failed: ${err.message}`, 'error');
    }
}

// ── Delete key ─────────────────────────────────────────────
async function deleteKey(keyId) {
    if (!confirm('Delete this API key?')) return;

    try {
        const resp = await fetch(`/api/keys/${keyId}`, {
            method: 'DELETE',
            headers: authHeaders(),
        });

        if (!resp.ok) throw new Error('Failed to delete key');

        showToast('API key deleted', 'success');
        loadKeys();
        loadProviders();
    } catch (err) {
        showToast(err.message, 'error');
    }
}
