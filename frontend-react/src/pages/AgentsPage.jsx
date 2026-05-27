import { useState, useEffect, useCallback } from 'react';
import { authFetch } from '../api/client';
import { showToast } from '../components/Toast';

export default function AgentsPage({ providers }) {
  const [agents, setAgents] = useState([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [agentProvider, setAgentProvider] = useState('openrouter');
  const [agentModel, setAgentModel] = useState('');
  const [prompt, setPrompt] = useState('');

  const loadAgents = useCallback(async () => {
    try {
      const resp = await authFetch('/api/agents');
      if (resp.ok) setAgents(await resp.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadAgents(); }, [loadAgents]);

  // Get models for selected provider
  const providerData = providers.find(p => p.id === agentProvider);
  const models = providerData?.models || [];

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      const resp = await authFetch('/api/agents', {
        method: 'POST',
        body: JSON.stringify({
          name,
          description,
          provider: agentProvider,
          model: agentModel,
          system_prompt: prompt,
          temperature: 0.7,
          max_tokens: 2048,
        }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || 'Failed to create agent');
      }
      showToast('Agent created!', 'success');
      setName(''); setDescription(''); setPrompt('');
      loadAgents();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const handleDelete = async (agentId) => {
    try {
      const resp = await authFetch(`/api/agents/${agentId}`, { method: 'DELETE' });
      if (resp.ok) {
        showToast('Agent deleted', 'success');
        loadAgents();
      }
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  return (
    <div className="view-container active">
      <div className="view-content">
        <div className="view-header">
          <h2>AI Agents</h2>
          <p>Create custom agents with specific system prompts, models, and configurations.</p>
        </div>

        <div className="agents-grid">
          {agents.map(a => (
            <div key={a.id} className="agent-card">
              <div className="agent-card-header">
                <h4>{a.name}</h4>
                <button className="btn-icon-sm btn-danger" onClick={() => handleDelete(a.id)}>✕</button>
              </div>
              {a.description && <p className="agent-description">{a.description}</p>}
              <div className="agent-meta">
                <span>{a.provider} / {a.model}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="add-key-card">
          <h3>Create New Agent</h3>
          <form onSubmit={handleCreate}>
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="agent-name">Agent Name</label>
                <input type="text" id="agent-name" value={name} onChange={e => setName(e.target.value)} required placeholder="Code Reviewer" />
              </div>
              <div className="form-group">
                <label htmlFor="agent-provider">Provider</label>
                <select id="agent-provider" value={agentProvider} onChange={e => { setAgentProvider(e.target.value); setAgentModel(''); }}>
                  <option value="openrouter">OpenRouter</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="xai">xAI (Grok)</option>
                  <option value="openai">OpenAI</option>
                </select>
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="agent-model">Model</label>
              <select id="agent-model" value={agentModel} onChange={e => setAgentModel(e.target.value)}>
                <option value="">Select model...</option>
                {models.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label htmlFor="agent-description">Description</label>
              <input type="text" id="agent-description" value={description} onChange={e => setDescription(e.target.value)} placeholder="A specialized agent for..." />
            </div>
            <div className="form-group">
              <label htmlFor="agent-prompt">System Prompt</label>
              <textarea id="agent-prompt" rows={4} value={prompt} onChange={e => setPrompt(e.target.value)} required placeholder="You are an expert code reviewer..." />
            </div>
            <div className="form-actions">
              <button type="submit" className="btn-send">Create Agent</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
