/**
 * chat.js — Chat UI, SSE streaming, message rendering
 *
 * KEY FIX: Uses direct element references for streaming, not IDs.
 * The old code used getElementById('streaming-content') which returned
 * the FIRST element with that ID — if a previous message still had it,
 * new responses would overwrite old messages instead of their own bubble.
 */

let currentSessionId = null;
let chatMessages = [];
let isStreaming = false;
let abortController = null;
let timerInterval = null;
let timerStart = 0;

// Direct element references for the current streaming operation.
// These hold references to the ACTUAL DOM elements, not IDs.
let activeStreamingMsg = null;
let activeStreamingContent = null;

// ── Message rendering ──────────────────────────────────────
function renderMessage(role, content, meta = {}) {
    const container = document.getElementById('chat-messages');
    const emptyState = document.getElementById('empty-state');
    if (emptyState) emptyState.style.display = 'none';

    const msgDiv = document.createElement('div');
    msgDiv.className = 'message';

    const isUser = role === 'user';
    const avatarIcon = isUser ? '👤' : '✦';
    const avatarClass = isUser ? 'user-avatar' : 'assistant-avatar';

    let renderedContent = content;
    if (!isUser && window.marked) {
        try {
            renderedContent = marked.parse(content);
        } catch { renderedContent = content; }
    }

    const metaHtml = meta.latency ? `<div class="msg-meta">${meta.latency}ms · ${meta.model || ''}</div>` : '';

    msgDiv.innerHTML = `
        <div class="msg-row ${role}">
            ${!isUser ? `<div class="msg-avatar ${avatarClass}">${avatarIcon}</div>` : ''}
            <div>
                <div class="msg-bubble">${isUser ? escapeHtml(content) : renderedContent}</div>
                ${metaHtml}
            </div>
            ${isUser ? `<div class="msg-avatar ${avatarClass}">${avatarIcon}</div>` : ''}
        </div>
    `;

    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;

    // Highlight code blocks
    if (!isUser) {
        msgDiv.querySelectorAll('pre code').forEach(block => {
            if (window.hljs) hljs.highlightElement(block);
        });
    }

    return msgDiv;
}

function createStreamingBubble() {
    const container = document.getElementById('chat-messages');
    const emptyState = document.getElementById('empty-state');
    if (emptyState) emptyState.style.display = 'none';

    const msgDiv = document.createElement('div');
    msgDiv.className = 'message';

    // Build the bubble structure with a direct reference to the content div
    const contentDiv = document.createElement('div');
    contentDiv.className = 'msg-bubble';
    contentDiv.innerHTML = `
        <div class="typing-indicator">
            <span></span><span></span><span></span>
        </div>
    `;

    msgDiv.innerHTML = `
        <div class="msg-row assistant">
            <div class="msg-avatar assistant-avatar">✦</div>
            <div class="msg-content-wrapper"></div>
        </div>
    `;

    // Append contentDiv to the inner wrapper div
    const innerDiv = msgDiv.querySelector('.msg-content-wrapper');
    innerDiv.appendChild(contentDiv);

    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;

    // Store DIRECT references — no IDs used at all
    activeStreamingMsg = msgDiv;
    activeStreamingContent = contentDiv;

    return msgDiv;
}

function updateStreamingBubble(text) {
    // Uses direct element reference, NOT getElementById
    if (!activeStreamingContent) return;

    let rendered = text;
    if (window.marked) {
        try { rendered = marked.parse(text); } catch { rendered = text; }
    }

    activeStreamingContent.innerHTML = rendered;

    // Highlight code
    activeStreamingContent.querySelectorAll('pre code').forEach(block => {
        if (window.hljs) hljs.highlightElement(block);
    });

    const container = document.getElementById('chat-messages');
    container.scrollTop = container.scrollHeight;
}

function finalizeStreamingBubble(latencyMs, model) {
    if (!activeStreamingMsg) return;

    // Add metadata below the bubble
    const metaDiv = document.createElement('div');
    metaDiv.className = 'msg-meta';
    metaDiv.textContent = `${latencyMs}ms${model ? ' · ' + model : ''}`;

    const bubbleParent = activeStreamingMsg.querySelector('.msg-content-wrapper');
    if (bubbleParent) bubbleParent.appendChild(metaDiv);

    // Clear references — critical to prevent stale references
    activeStreamingMsg = null;
    activeStreamingContent = null;
}

// ── Send message ───────────────────────────────────────────
async function sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text || isStreaming) return;

    const provider = document.getElementById('provider-select').value;
    const model = document.getElementById('model-select').value;

    if (!provider || !model) {
        showToast('Please select a provider and model first', 'error');
        return;
    }

    // Lock UI immediately — prevent any double-sends
    isStreaming = true;
    setStreamingUI(true);

    // Add user message to conversation
    chatMessages.push({ role: 'user', content: text });
    renderMessage('user', text);
    input.value = '';
    autoResizeInput();

    // Create streaming placeholder bubble (uses direct references)
    createStreamingBubble();
    startTimer();

    abortController = new AbortController();
    let fullResponse = '';
    const t0 = performance.now();

    try {
        const systemPrompt = 'You are a helpful AI assistant.';
        await ensureValidToken(); // Refresh JWT if expired
        const resp = await fetch('/api/chat', {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({
                session_id: currentSessionId,
                provider,
                model,
                messages: chatMessages,
                system_prompt: systemPrompt,
                temperature: 0.7,
                max_tokens: 2048,
                top_p: 0.9,
                stream: true,
            }),
            signal: abortController.signal,
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: 'Chat request failed' }));
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }

        // Get session ID from response header
        const sessionId = resp.headers.get('X-Session-ID');
        if (sessionId) currentSessionId = sessionId;

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const data = line.slice(6).trim();

                if (data === '[DONE]') continue;

                try {
                    const parsed = JSON.parse(data);

                    // Check for error from provider
                    if (parsed.error) {
                        throw new Error(parsed.error);
                    }

                    const delta = parsed.choices?.[0]?.delta;
                    if (delta?.content) {
                        fullResponse += delta.content;
                        updateStreamingBubble(fullResponse);
                    }
                } catch (e) {
                    if (e.message && !e.message.includes('JSON')) {
                        throw e;
                    }
                }
            }
        }

    } catch (err) {
        if (err.name === 'AbortError') {
            fullResponse += '\n\n*[Generation stopped]*';
            updateStreamingBubble(fullResponse);
        } else {
            const errorContent = `**Error:** ${err.message}`;
            fullResponse = ''; // Don't save error as assistant message
            updateStreamingBubble(errorContent);
            showToast(err.message, 'error');
        }
    }

    const latencyMs = Math.round(performance.now() - t0);
    stopTimer();
    finalizeStreamingBubble(latencyMs, model);

    // Unlock UI
    isStreaming = false;
    setStreamingUI(false);

    // Save assistant response to conversation memory
    if (fullResponse) {
        chatMessages.push({ role: 'assistant', content: fullResponse });
    }

    // Refresh session list in sidebar
    loadSessions();
}

function stopGeneration() {
    if (abortController) {
        abortController.abort();
        abortController = null;
    }
}

// ── Timer ──────────────────────────────────────────────────
function startTimer() {
    timerStart = performance.now();
    const badge = document.getElementById('timer-badge');
    if (badge) badge.classList.add('active');

    timerInterval = setInterval(() => {
        const elapsed = ((performance.now() - timerStart) / 1000).toFixed(2);
        const display = document.getElementById('timer-display');
        if (display) display.textContent = `${elapsed}s`;
    }, 50);
}

function stopTimer() {
    clearInterval(timerInterval);
    const badge = document.getElementById('timer-badge');
    if (badge) badge.classList.remove('active');
}

// ── UI state ───────────────────────────────────────────────
function setStreamingUI(streaming) {
    const sendBtn = document.getElementById('send-btn');
    const chatInput = document.getElementById('chat-input');
    const stopBtn = document.getElementById('stop-btn');

    if (sendBtn) sendBtn.disabled = streaming;
    if (chatInput) chatInput.disabled = streaming;
    if (stopBtn) stopBtn.classList.toggle('hidden', !streaming);
}

function clearChat() {
    currentSessionId = null;
    chatMessages = [];
    activeStreamingMsg = null;
    activeStreamingContent = null;
    isStreaming = false;

    const container = document.getElementById('chat-messages');
    container.innerHTML = `
        <div id="empty-state" class="empty-state">
            <div class="empty-state-icon">✦</div>
            <h2>Welcome to AI Agent Platform</h2>
            <p>Select a provider and model, add your API key, and start chatting with any LLM provider.</p>
            <div class="quick-actions">
                <button onclick="switchView('keys')" class="quick-action-btn">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
                    Add API Keys
                </button>
                <button onclick="switchView('agents')" class="quick-action-btn">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
                    Create Agents
                </button>
            </div>
        </div>
    `;
}

function startNewChat() {
    clearChat();
    switchView('chat');
}

// ── Load session messages ──────────────────────────────────
async function loadSession(sessionId) {
    try {
        const resp = await authFetch(`/api/sessions/${sessionId}`);
        if (!resp.ok) throw new Error('Failed to load session');

        const session = await resp.json();
        currentSessionId = session.id;
        chatMessages = session.messages.map(m => ({ role: m.role, content: m.content }));

        // Set provider/model
        document.getElementById('provider-select').value = session.provider;
        onProviderChange();
        setTimeout(() => {
            document.getElementById('model-select').value = session.model;
        }, 100);

        // Clear and render all messages from history
        const container = document.getElementById('chat-messages');
        container.innerHTML = '';
        for (const msg of session.messages) {
            renderMessage(msg.role, msg.content, {
                latency: msg.latency_ms,
                model: msg.model,
            });
        }

        switchView('chat');
        highlightActiveSession(sessionId);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function highlightActiveSession(sessionId) {
    document.querySelectorAll('.session-item').forEach(el => {
        el.classList.toggle('active', el.dataset.id === sessionId);
    });
}

// ── Helpers ─────────────────────────────────────────────────
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function autoResizeInput() {
    const input = document.getElementById('chat-input');
    if (!input) return;
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
}
