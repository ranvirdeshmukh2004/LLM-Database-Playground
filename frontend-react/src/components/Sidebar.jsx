import { useAuth } from '../context/AuthContext';

export default function Sidebar({ sessions, activeSession, onSelectSession, onDeleteSession, onNewChat, activeView, onSwitchView }) {
  const { user, logout } = useAuth();
  const email = user?.email || '';

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <div className="sidebar-logo-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
              <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <div>
            <h1 className="sidebar-title">AI Platform</h1>
            <p className="sidebar-subtitle">Multi-Provider</p>
          </div>
        </div>
        <button className="btn-new-chat" onClick={onNewChat} title="New Chat">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
      </div>

      <div className="sidebar-nav">
        {['chat', 'agents', 'keys'].map(view => (
          <button
            key={view}
            className={`sidebar-nav-item ${activeView === view ? 'active' : ''}`}
            onClick={() => onSwitchView(view)}
          >
            {view === 'chat' && <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>}
            {view === 'agents' && <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>}
            {view === 'keys' && <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" /></svg>}
            {view === 'chat' ? 'Chat' : view === 'agents' ? 'Agents' : 'API Keys'}
          </button>
        ))}
      </div>

      <div className="sidebar-section">
        <div className="sidebar-section-header">
          <span>Recent Chats</span>
        </div>
        <div className="session-list">
          {sessions.map(s => (
            <div
              key={s.id}
              className={`session-item ${activeSession === s.id ? 'active' : ''}`}
              onClick={() => onSelectSession(s.id)}
            >
              <span className="session-item-title">{s.title || 'New Chat'}</span>
              <button
                className="session-item-delete"
                onClick={e => { e.stopPropagation(); onDeleteSession(s.id); }}
              >✕</button>
            </div>
          ))}
        </div>
      </div>

      <div className="sidebar-footer">
        <div className="user-info">
          <div className="user-avatar">{email.charAt(0).toUpperCase()}</div>
          <span className="user-email">{email}</span>
        </div>
        <button onClick={logout} className="btn-icon-sm" title="Logout">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </div>
    </aside>
  );
}
