import { getDbMode } from '../api/client';

export default function TopBar({ providers, selectedProvider, selectedModel, onProviderChange, onModelChange, timerDisplay, onToggleSidebar }) {
  const dbMode = getDbMode();
  const provider = providers.find(p => p.id === selectedProvider);
  const models = provider?.models || [];

  return (
    <div className="top-bar">
      <div className="top-bar-left">
        <button className="btn-icon" onClick={onToggleSidebar}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
      </div>
      <div className="top-bar-center">
        <select className="provider-select" value={selectedProvider} onChange={e => onProviderChange(e.target.value)}>
          <option value="">Select provider...</option>
          {providers.map(p => (
            <option key={p.id} value={p.id}>
              {p.name}{p.has_user_key ? ' ✓' : ''}
            </option>
          ))}
        </select>
        <select className="model-select" value={selectedModel} onChange={e => onModelChange(e.target.value)}>
          <option value="">Select model...</option>
          {models.map(m => (
            <option key={m.id} value={m.id}>
              {m.name}{m.context ? ` (${Math.round(m.context / 1000)}K)` : ''}
            </option>
          ))}
        </select>
      </div>
      <div className="top-bar-right">
        <span className={`db-mode-badge ${dbMode}`} title={`Database: ${dbMode === 'plain' ? 'Plain PostgreSQL' : 'Supabase PostgreSQL'}`}>
          {dbMode === 'plain' ? '🔵 Plain PG' : '🟢 Supabase'}
        </span>
        <div className="timer-badge">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
          </svg>
          <span>{timerDisplay}</span>
        </div>
      </div>
    </div>
  );
}
