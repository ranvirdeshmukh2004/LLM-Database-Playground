/**
 * agents.js — Agent builder UI
 */

let agentsList = [];

// ── Load agents ────────────────────────────────────────────
async function loadAgents() {
    try {
        const resp = await fetch('/api/agents', { headers: authHeaders() });
        if (!resp.ok) return;

        agentsList = await resp.json();
        const container = document.getElementById('agents-list');

        if (agentsList.length === 0) {
            container.innerHTML = `
                <div style="text-align:center; padding:20px; color:var(--text-muted); font-size:13px; grid-column:1/-1;">
                    No agents created yet. Build one below.
                </div>
            `;
            return;
        }

        container.innerHTML = agentsList.map(agent => `
            <div class="agent-card" onclick="chatWithAgent('${agent.id}')">
                <div class="agent-card-header">
                    <div class="agent-card-icon">🤖</div>
                    <div class="agent-card-name">${escapeHtml(agent.name)}</div>
                </div>
                ${agent.description ? `<div class="agent-card-desc">${escapeHtml(agent.description)}</div>` : ''}
                <div class="agent-card-meta">
                    <span class="agent-card-badge">${agent.provider}</span>
                    <span>${agent.model.split('/').pop()}</span>
                </div>
                <div class="agent-card-actions" onclick="event.stopPropagation()">
                    <button class="key-action-btn" onclick="chatWithAgent('${agent.id}')">Chat</button>
                    <button class="key-action-btn delete" onclick="deleteAgent('${agent.id}')">Delete</button>
                </div>
            </div>
        `).join('');

    } catch (err) {
        console.error('Failed to load agents:', err);
    }
}

// ── Create agent ───────────────────────────────────────────
async function handleAddAgent(e) {
    e.preventDefault();

    const name = document.getElementById('agent-name').value.trim();
    const provider = document.getElementById('agent-provider').value;
    const model = document.getElementById('agent-model').value;
    const description = document.getElementById('agent-description').value.trim();
    const systemPrompt = document.getElementById('agent-prompt').value.trim();

    if (!name || !systemPrompt || !model) {
        showToast('Please fill in all required fields', 'error');
        return false;
    }

    try {
        const resp = await fetch('/api/agents', {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({
                name,
                description,
                system_prompt: systemPrompt,
                provider,
                model,
                settings: { temperature: 0.7, max_tokens: 2048 },
            }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Failed to create agent');
        }

        showToast(`Agent "${name}" created!`, 'success');
        document.getElementById('add-agent-form').reset();
        loadAgents();

    } catch (err) {
        showToast(err.message, 'error');
    }

    return false;
}

// ── Chat with agent ────────────────────────────────────────
async function chatWithAgent(agentId) {
    const agent = agentsList.find(a => a.id === agentId);
    if (!agent) return;

    // Set provider/model
    document.getElementById('provider-select').value = agent.provider;
    onProviderChange();
    setTimeout(() => {
        document.getElementById('model-select').value = agent.model;
    }, 100);

    // Start new chat with agent context
    clearChat();
    switchView('chat');

    showToast(`Chatting with agent: ${agent.name}`, 'success');
}

// ── Delete agent ───────────────────────────────────────────
async function deleteAgent(agentId) {
    if (!confirm('Delete this agent?')) return;

    try {
        const resp = await fetch(`/api/agents/${agentId}`, {
            method: 'DELETE',
            headers: authHeaders(),
        });

        if (!resp.ok) throw new Error('Failed to delete agent');

        showToast('Agent deleted', 'success');
        loadAgents();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ── Update agent model dropdown ────────────────────────────
function updateAgentModels() {
    const provider = document.getElementById('agent-provider').value;
    const modelSelect = document.getElementById('agent-model');
    const providerData = providersData.find(p => p.id === provider);

    modelSelect.innerHTML = '';
    if (providerData && providerData.models) {
        for (const model of providerData.models) {
            const opt = document.createElement('option');
            opt.value = model.id;
            opt.textContent = model.name;
            modelSelect.appendChild(opt);
        }
    }
}
