import { useEffect, useRef } from 'react';
import { marked } from 'marked';
import hljs from 'highlight.js';

function escapeHtml(str) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return str.replace(/[&<>"']/g, c => map[c]);
}

export default function ChatMessage({ role, content, meta = {} }) {
  const bubbleRef = useRef(null);
  const isUser = role === 'user';

  useEffect(() => {
    if (!isUser && bubbleRef.current) {
      bubbleRef.current.querySelectorAll('pre code').forEach(block => {
        if (!block.dataset.highlighted) {
          hljs.highlightElement(block);
          block.dataset.highlighted = 'true';
        }
      });
    }
  }, [content, isUser]);

  let rendered = content;
  if (!isUser) {
    try { rendered = marked.parse(content); } catch { rendered = content; }
  }

  const metaHtml = meta.latency
    ? `${meta.latency}ms · ${meta.model || ''}`
    : '';

  return (
    <div className="message">
      <div className={`msg-row ${role}`}>
        {!isUser && <div className="msg-avatar assistant-avatar">✦</div>}
        <div>
          <div
            className="msg-bubble"
            ref={bubbleRef}
            dangerouslySetInnerHTML={{ __html: isUser ? escapeHtml(content) : rendered }}
          />
          {metaHtml && <div className="msg-meta">{metaHtml}</div>}
        </div>
        {isUser && <div className="msg-avatar user-avatar">👤</div>}
      </div>
    </div>
  );
}
