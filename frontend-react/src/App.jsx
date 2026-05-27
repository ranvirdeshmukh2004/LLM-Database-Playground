import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from './context/AuthContext';
import { authFetch } from './api/client';
import AuthPage from './pages/AuthPage';
import ChatPage from './pages/ChatPage';
import KeysPage from './pages/KeysPage';
import AgentsPage from './pages/AgentsPage';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import Toast from './components/Toast';

export default function App() {
  const { isAuthenticated } = useAuth();
  const [view, setView] = useState('chat');
  const [providers, setProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [timerDisplay, setTimerDisplay] = useState('0.00s');

  // Timer ref for ChatPage
  const timerRef = useRef({
    intervalId: null,
    start() {
      const t0 = performance.now();
      this.intervalId = setInterval(() => {
        setTimerDisplay(((performance.now() - t0) / 1000).toFixed(2) + 's');
      }, 50);
    },
    stop() {
      if (this.intervalId) clearInterval(this.intervalId);
    },
  });

  // ── Load providers ──────────────────────────────────────
  const loadProviders = useCallback(async () => {
    try {
      const resp = await authFetch('/api/providers');
      if (resp.ok) setProviders(await resp.json());
    } catch { /* ignore */ }
  }, []);

  // ── Load sessions ───────────────────────────────────────
  const loadSessions = useCallback(async () => {
    try {
      const resp = await authFetch('/api/sessions?limit=30');
      if (resp.ok) {
        const data = await resp.json();
        setSessions(data.sessions || data || []);
      }
    } catch { /* ignore */ }
  }, []);

  // Load on auth
  useEffect(() => {
    if (isAuthenticated) {
      loadProviders();
      loadSessions();
    }
  }, [isAuthenticated, loadProviders, loadSessions]);

  // ── Handlers ────────────────────────────────────────────
  const handleNewChat = () => {
    setActiveSession(null);
    setView('chat');
  };

  const handleSelectSession = (id) => {
    setActiveSession(id);
    setView('chat');
  };

  const handleDeleteSession = async (id) => {
    try {
      await authFetch(`/api/sessions/${id}`, { method: 'DELETE' });
      setSessions(prev => prev.filter(s => s.id !== id));
      if (activeSession === id) setActiveSession(null);
    } catch { /* ignore */ }
  };

  const handleSessionCreated = (id) => {
    setActiveSession(id);
    loadSessions();
  };

  const handleProviderChange = (providerId) => {
    setSelectedProvider(providerId);
    setSelectedModel('');
  };

  if (!isAuthenticated) return <AuthPage />;

  return (
    <>
      <div className={`app-root ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
        <Sidebar
          sessions={sessions}
          activeSession={activeSession}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
          onNewChat={handleNewChat}
          activeView={view}
          onSwitchView={setView}
        />

        <div className="main-area">
          <TopBar
            providers={providers}
            selectedProvider={selectedProvider}
            selectedModel={selectedModel}
            onProviderChange={handleProviderChange}
            onModelChange={setSelectedModel}
            timerDisplay={timerDisplay}
            onToggleSidebar={() => setSidebarOpen(prev => !prev)}
          />

          {view === 'chat' && (
            <ChatPage
              provider={selectedProvider}
              model={selectedModel}
              sessionId={activeSession}
              onSessionCreated={handleSessionCreated}
              onSwitchView={setView}
              timerRef={timerRef}
            />
          )}
          {view === 'keys' && <KeysPage />}
          {view === 'agents' && <AgentsPage providers={providers} />}
        </div>
      </div>
      <Toast />
    </>
  );
}
