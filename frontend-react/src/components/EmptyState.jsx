export default function EmptyState({ onAddKeys, onCreateAgent }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">✦</div>
      <h2>Welcome to AI Agent Platform</h2>
      <p>Select a provider and model, add your API key, and start chatting with any LLM provider.</p>
      <div className="quick-actions">
        <button onClick={onAddKeys} className="quick-action-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
          </svg>
          Add API Keys
        </button>
        <button onClick={onCreateAgent} className="quick-action-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
          </svg>
          Create Agents
        </button>
      </div>
    </div>
  );
}
