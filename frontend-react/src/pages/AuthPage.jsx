import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import DbToggle from '../components/DbToggle';

export default function AuthPage() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'signup') {
        await signup(email, password, name);
      } else {
        await login(email, password);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-container">
        <div className="auth-header">
          <div className="auth-logo">
            <div className="auth-logo-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <div>
              <h1 className="auth-title">AI Agent Platform</h1>
              <p className="auth-subtitle">Multi-Provider LLM Console</p>
            </div>
          </div>
        </div>

        <div className="auth-card">
          <div className="auth-tabs">
            <button className={`auth-tab ${mode === 'login' ? 'active' : ''}`} onClick={() => setMode('login')}>Sign In</button>
            <button className={`auth-tab ${mode === 'signup' ? 'active' : ''}`} onClick={() => setMode('signup')}>Sign Up</button>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            {error && <div className="auth-error">{error}</div>}

            {mode === 'signup' && (
              <div className="form-group">
                <label htmlFor="auth-name">Display Name</label>
                <input type="text" id="auth-name" value={name} onChange={e => setName(e.target.value)} placeholder="Your name" autoComplete="name" />
              </div>
            )}

            <div className="form-group">
              <label htmlFor="auth-email">Email</label>
              <input type="email" id="auth-email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required autoComplete="email" />
            </div>

            <div className="form-group">
              <label htmlFor="auth-password">Password</label>
              <input type="password" id="auth-password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" required minLength={8} autoComplete="current-password" />
            </div>

            <button type="submit" className="auth-submit-btn" disabled={loading}>
              <span>{loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}</span>
              {loading && <div className="spinner" />}
            </button>
          </form>

          <DbToggle />

          <div className="auth-providers-section">
            <div className="auth-divider"><span>Supported Providers</span></div>
            <div className="provider-badges">
              <span className="provider-badge">OpenRouter</span>
              <span className="provider-badge">Claude</span>
              <span className="provider-badge">Grok</span>
              <span className="provider-badge">OpenAI</span>
              <span className="provider-badge">Self-Hosted</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
