import { useDbMode } from '../context/DbModeContext';

export default function DbToggle() {
  const { dbMode, setDbMode, info } = useDbMode();

  return (
    <div className="db-toggle-section">
      <div className="db-toggle-label">Database Engine</div>
      <div className="db-toggle-switch">
        <button
          className={`db-toggle-btn ${dbMode === 'supabase' ? 'active' : ''}`}
          onClick={() => setDbMode('supabase')}
        >
          <span className="db-toggle-dot supabase-dot" />
          Supabase PG
        </button>
        <button
          className={`db-toggle-btn ${dbMode === 'plain' ? 'active' : ''}`}
          onClick={() => setDbMode('plain')}
        >
          <span className="db-toggle-dot plain-dot" />
          Plain PG
        </button>
      </div>
      <div className="db-toggle-info">{info}</div>
    </div>
  );
}
