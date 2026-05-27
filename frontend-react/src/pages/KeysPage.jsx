import { useState, useEffect, useCallback } from 'react';
import { authFetch } from '../api/client';
import { showToast } from '../components/Toast';

export default function KeysPage() {
  const [keys, setKeys] = useState([]);
  const [provider, setProvider] = useState('openrouter');
  const [label, setLabel] = useState('default');
  const [keyValue, setKeyValue] = useState('');
  const [loading, setLoading] = useState(false);

  const loadKeys = useCallback(async () => {
    try {
      const resp = await authFetch('/api/keys');
      if (resp.ok) setKeys(await resp.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadKeys(); }, [loadKeys]);

  const handleAddKey = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const resp = await authFetch('/api/keys', {
        method: 'POST',
        body: JSON.stringify({ provider, name: label, api_key: keyValue }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || 'Failed to save key');
      }
      showToast('API key saved successfully!', 'success');
      setKeyValue('');
      loadKeys();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleTestKey = async (keyId) => {
    try {
      const resp = await authFetch(`/api/keys/${keyId}/test`, { method: 'POST' });
      const data = await resp.json();
      showToast(`Key test: ${data.status} ${data.latency_ms ? `(${data.latency_ms}ms)` : ''} ${data.detail || ''}`, data.status === 'valid' ? 'success' : 'error');
    } catch (err) {
      showToast(`Test failed: ${err.message}`, 'error');
    }
  };

  const handleDeleteKey = async (keyId) => {
    try {
      const resp = await authFetch(`/api/keys/${keyId}`, { method: 'DELETE' });
      if (resp.ok) {
        showToast('Key deleted', 'success');
        loadKeys();
      }
    } catch (err) {
      showToast(`Delete failed: ${err.message}`, 'error');
    }
  };

  return (
    <div className="view-container active">
      <div className="view-content">
        <div className="view-header">
          <h2>API Keys</h2>
          <p>Add your API keys to connect to LLM providers. Keys are encrypted before storage.</p>
        </div>

        <div className="keys-grid">
          {keys.map(k => (
            <div key={k.id} className="key-card">
              <div className="key-card-header">
                <span className="key-provider-name">{k.provider}</span>
                <span className="key-status">{k.is_active ? '● Active' : '○ Inactive'}</span>
              </div>
              <div className="key-card-body">
                <code className="key-masked">{k.masked_key}</code>
                <div className="key-meta">
                  {k.name && <span>{k.name}</span>}
                  {k.last_used_at && <span>Last used: {new Date(k.last_used_at).toLocaleDateString()}</span>}
                </div>
              </div>
              <div className="key-card-actions">
                <button className="btn-icon-sm" onClick={() => handleTestKey(k.id)}>Test</button>
                <button className="btn-icon-sm btn-danger" onClick={() => handleDeleteKey(k.id)}>Delete</button>
              </div>
            </div>
          ))}
        </div>

        <div className="add-key-card">
          <h3>Add New API Key</h3>
          <form onSubmit={handleAddKey}>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="key-provider">Provider</label>
                <select id="key-provider" value={provider} onChange={e => setProvider(e.target.value)}>
                  <option value="openrouter">OpenRouter</option>
                  <option value="anthropic">Anthropic (Claude)</option>
                  <option value="xai">xAI (Grok)</option>
                  <option value="openai">OpenAI</option>
                  <option value="custom">Self-Hosted</option>
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="key-name">Label</label>
                <input type="text" id="key-name" value={label} onChange={e => setLabel(e.target.value)} placeholder="default" />
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="key-value">API Key</label>
              <input type="password" id="key-value" value={keyValue} onChange={e => setKeyValue(e.target.value)} required placeholder="sk-or-v1-..." />
            </div>
            <div className="form-actions">
              <button type="submit" className="btn-send" disabled={loading}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
                {loading ? 'Saving...' : 'Save Key (Encrypted)'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
