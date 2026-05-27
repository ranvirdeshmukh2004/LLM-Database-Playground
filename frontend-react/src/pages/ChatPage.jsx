import { useState, useEffect, useRef, useCallback } from 'react';
import { authFetch, getUserId } from '../api/client';
import ChatMessage from '../components/ChatMessage';
import ChatInput from '../components/ChatInput';
import EmptyState from '../components/EmptyState';
import { marked } from 'marked';
import hljs from 'highlight.js';

export default function ChatPage({ provider, model, sessionId, onSessionCreated, onSwitchView, timerRef }) {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [streamingMeta, setStreamingMeta] = useState({});
  const messagesEndRef = useRef(null);
  const abortRef = useRef(null);

  // Load session messages when sessionId changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }
    (async () => {
      try {
        const resp = await authFetch(`/api/sessions/${sessionId}`);
        if (resp.ok) {
          const data = await resp.json();
          setMessages((data.messages || []).map(m => ({
            role: m.role,
            content: m.content,
            meta: { latency: m.latency_ms, model: m.model },
          })));
        }
      } catch { /* ignore */ }
    })();
  }, [sessionId]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  const sendMessage = useCallback(async (text) => {
    if (!provider || !model) return;

    const userMsg = { role: 'user', content: text, meta: {} };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setIsStreaming(true);
    setStreamingContent('');
    setStreamingMeta({});

    // Timer
    const t0 = performance.now();
    if (timerRef?.current) timerRef.current.start();

    const abortController = new AbortController();
    abortRef.current = abortController;

    const messagesDicts = newMessages.map(m => ({ role: m.role, content: m.content }));

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': getUserId(),
        },
        body: JSON.stringify({
          session_id: sessionId,
          provider,
          model,
          messages: messagesDicts,
          system_prompt: 'You are a helpful AI assistant.',
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

      // Get session ID from header
      const newSessionId = resp.headers.get('X-Session-ID');
      if (newSessionId && !sessionId) {
        onSessionCreated(newSessionId);
      }

      // Read SSE stream
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let fullText = '';
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const dataStr = line.slice(6).trim();
          if (dataStr === '[DONE]') continue;

          try {
            const data = JSON.parse(dataStr);
            if (data.error) {
              fullText += `\n\n**Error:** ${data.error}`;
              setStreamingContent(fullText);
              continue;
            }
            const delta = data.choices?.[0]?.delta;
            if (delta?.content) {
              fullText += delta.content;
              setStreamingContent(fullText);
            }
            if (data.model) {
              setStreamingMeta(prev => ({ ...prev, model: data.model }));
            }
          } catch { /* skip parse errors */ }
        }
      }

      const latency = Math.round(performance.now() - t0);
      const assistantMsg = { role: 'assistant', content: fullText, meta: { latency, model } };
      setMessages(prev => [...prev, assistantMsg]);
      setStreamingContent('');
      setStreamingMeta({});

    } catch (err) {
      if (err.name !== 'AbortError') {
        const latency = Math.round(performance.now() - t0);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `**Error:** ${err.message}`,
          meta: { latency, model },
        }]);
        setStreamingContent('');
      }
    } finally {
      setIsStreaming(false);
      if (timerRef?.current) timerRef.current.stop();
    }
  }, [provider, model, sessionId, messages, onSessionCreated, timerRef]);

  const stopGeneration = () => {
    abortRef.current?.abort();
    setIsStreaming(false);
    if (streamingContent) {
      setMessages(prev => [...prev, { role: 'assistant', content: streamingContent, meta: streamingMeta }]);
      setStreamingContent('');
    }
  };

  const hasMessages = messages.length > 0 || streamingContent;

  return (
    <div className="view-container active" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="chat-messages" style={{ flex: 1, overflowY: 'auto' }}>
        {!hasMessages && (
          <EmptyState
            onAddKeys={() => onSwitchView('keys')}
            onCreateAgent={() => onSwitchView('agents')}
          />
        )}
        {messages.map((msg, i) => (
          <ChatMessage key={i} role={msg.role} content={msg.content} meta={msg.meta} />
        ))}
        {streamingContent && (
          <div className="message">
            <div className="msg-row assistant">
              <div className="msg-avatar assistant-avatar">✦</div>
              <div>
                <div className="msg-bubble streaming-bubble" dangerouslySetInnerHTML={{
                  __html: (() => { try { return marked.parse(streamingContent); } catch { return streamingContent; } })()
                }} />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <ChatInput onSend={sendMessage} onStop={stopGeneration} isStreaming={isStreaming} />
    </div>
  );
}
