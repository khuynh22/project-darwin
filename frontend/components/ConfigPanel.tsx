'use client';

import { useState, useEffect } from 'react';

type ProviderInfo = { name: string; default_model: string; requires_key: boolean };
type StoredKey = { id: number; provider: string; label: string };

type AgentConfig = {
  agent_id: string;
  display_name: string;
  provider: string;
  model: string;
  personality: string;
  sprite: string; // actually a color name now
};

const COLOR_HEX: Record<string, string> = {
  red: '#ef4444', blue: '#3b82f6', green: '#22c55e', purple: '#a855f7',
  orange: '#f97316', cyan: '#06b6d4', pink: '#ec4899', yellow: '#eab308',
  teal: '#14b8a6', indigo: '#6366f1',
};

const AUTO_PERSONALITIES = [
  'Cooperative strategist who builds trust through consistent behavior.',
  'Aggressive optimizer who exploits every opportunity for gain.',
  'Unpredictable agent who switches tactics to stay ahead.',
  'Patient analyst who calculates risks before every move.',
  'Social manipulator who uses alliances and deals as leverage.',
];

function emptyAgent(index: number): AgentConfig {
  const colors = Object.keys(COLOR_HEX);
  return {
    agent_id: `agent_${index + 1}`,
    display_name: `Agent ${index + 1}`,
    provider: 'stub',
    model: '',
    personality: '',
    sprite: colors[index % colors.length],
  };
}

export default function ConfigPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const httpBase = process.env.NEXT_PUBLIC_ORACLE_HTTP || 'http://localhost:8000';

  const [agents, setAgents] = useState<AgentConfig[]>([emptyAgent(0), emptyAgent(1), emptyAgent(2)]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [storedKeys, setStoredKeys] = useState<StoredKey[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [providerKeys, setProviderKeys] = useState<Record<string, { keyId: number | null; rawKey: string }>>({});

  useEffect(() => {
    if (!open) return;
    fetch(`${httpBase}/providers`).then(r => r.json()).then(d => {
      setProviders(d.providers || []);
    }).catch(() => {});
    fetch(`${httpBase}/api-keys`).then(r => r.json()).then(d => {
      const keys = d.keys || [];
      setStoredKeys(keys);
      const auto: Record<string, { keyId: number | null; rawKey: string }> = {};
      for (const k of keys) {
        if (!auto[k.provider]) auto[k.provider] = { keyId: k.id, rawKey: '' };
      }
      setProviderKeys(prev => ({ ...auto, ...prev }));
    }).catch(() => {});
  }, [open, httpBase]);

  function updateAgent(i: number, patch: Partial<AgentConfig>) {
    setAgents(prev => prev.map((a, idx) => idx === i ? { ...a, ...patch } : a));
  }

  function addAgent() {
    if (agents.length >= 10) return;
    setAgents(prev => [...prev, emptyAgent(prev.length)]);
  }

  function removeAgent(i: number) {
    if (agents.length <= 3) return;
    setAgents(prev => prev.filter((_, idx) => idx !== i));
  }

  function onProviderChange(i: number, provider: string) {
    const info = providers.find(p => p.name === provider);
    updateAgent(i, { provider, model: info?.default_model || '' });
  }

  async function saveProviderKey(provider: string) {
    const pk = providerKeys[provider];
    if (!pk?.rawKey) return;
    const res = await fetch(`${httpBase}/api-keys`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, label: `${provider} key`, key: pk.rawKey }),
    });
    const data = await res.json();
    if (data.id) {
      setStoredKeys(prev => [...prev, { id: data.id, provider, label: data.label }]);
      setProviderKeys(prev => ({ ...prev, [provider]: { keyId: data.id, rawKey: '' } }));
    }
  }

  async function submit() {
    setError('');
    setSubmitting(true);
    try {
      const payload = agents.map(a => {
        const pk = providerKeys[a.provider];
        return {
          agent_id: a.agent_id, display_name: a.display_name, provider: a.provider,
          model: a.model, personality: a.personality || undefined, sprite: a.sprite,
          ...(pk?.keyId ? { api_key_id: pk.keyId } : {}),
          ...(pk?.rawKey ? { api_key: pk.rawKey } : {}),
        };
      });
      const res = await fetch(`${httpBase}/configure`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agents: payload }),
      });
      const data = await res.json();
      if (data.error) setError(data.error);
      else onClose();
    } catch (e: unknown) { setError(String(e)); }
    finally { setSubmitting(false); }
  }

  if (!open) return null;

  const usedProviders = [...new Set(agents.map(a => a.provider))];
  const providersNeedingKeys = usedProviders.filter(p => providers.find(pr => pr.name === p)?.requires_key);

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-start justify-center z-50 overflow-y-auto py-8">
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl p-6 max-w-2xl w-full mx-4">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-white text-lg font-semibold">Configure Simulation</h2>
            <p className="text-zinc-400 text-sm mt-0.5">Set up 3-10 agents to begin.</p>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-white text-xl w-8 h-8 flex items-center justify-center rounded hover:bg-zinc-800">&times;</button>
        </div>

        {/* API Keys */}
        {providersNeedingKeys.length > 0 && (
          <div className="mb-5 rounded-lg border border-zinc-700/50 bg-zinc-800/50 p-4">
            <h3 className="text-zinc-300 text-sm font-medium mb-3">API Keys</h3>
            <div className="space-y-2">
              {providersNeedingKeys.map(provider => {
                const pk = providerKeys[provider] || { keyId: null, rawKey: '' };
                const saved = storedKeys.filter(k => k.provider === provider);
                return (
                  <div key={provider} className="flex items-center gap-3">
                    <span className="text-zinc-300 text-sm w-20 font-medium capitalize">{provider}</span>
                    {pk.keyId ? (
                      <span className="text-emerald-400 text-sm flex-1">Key saved</span>
                    ) : (
                      <>
                        <input type="password" value={pk.rawKey}
                          onChange={e => setProviderKeys(prev => ({ ...prev, [provider]: { ...pk, rawKey: e.target.value } }))}
                          className="bg-zinc-900 border border-zinc-600 text-zinc-200 text-sm px-3 py-1.5 rounded-lg flex-1 focus:border-blue-500 focus:outline-none"
                          placeholder={`Enter ${provider} API key`} />
                        {pk.rawKey && <button onClick={() => saveProviderKey(provider)} className="text-blue-400 text-sm hover:text-blue-300">Save</button>}
                      </>
                    )}
                    {!pk.keyId && saved.length > 0 && (
                      <select onChange={e => setProviderKeys(prev => ({ ...prev, [provider]: { keyId: Number(e.target.value), rawKey: '' } }))}
                        className="bg-zinc-900 border border-zinc-600 text-zinc-300 text-sm px-2 py-1.5 rounded-lg" defaultValue="">
                        <option value="" disabled>Saved...</option>
                        {saved.map(k => <option key={k.id} value={k.id}>{k.label}</option>)}
                      </select>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Agents */}
        <div className="space-y-2 mb-5">
          {agents.map((a, i) => (
            <div key={i} className="rounded-lg border border-zinc-700/50 bg-zinc-800/30 p-3">
              <div className="flex items-center gap-2">
                {/* Color dot */}
                <div className="w-4 h-4 rounded-full flex-shrink-0 border border-white/20"
                  style={{ backgroundColor: COLOR_HEX[a.sprite] || '#888' }} />
                <input value={a.display_name}
                  onChange={e => updateAgent(i, { display_name: e.target.value, agent_id: e.target.value.toLowerCase().replace(/[^a-z0-9]/g, '_') })}
                  className="bg-transparent border-b border-zinc-600 text-white text-sm px-1 py-0.5 w-28 focus:border-blue-500 focus:outline-none" placeholder="Name" />
                <select value={a.provider} onChange={e => onProviderChange(i, e.target.value)}
                  className="bg-zinc-900 border border-zinc-600 text-zinc-300 text-sm px-2 py-1 rounded-lg">
                  {providers.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}
                </select>
                <input value={a.model} onChange={e => updateAgent(i, { model: e.target.value })}
                  className="bg-zinc-900 border border-zinc-600 text-zinc-300 text-sm px-2 py-1 rounded-lg flex-1 focus:border-blue-500 focus:outline-none" placeholder="Model ID" />
                {/* Color picker */}
                <select value={a.sprite} onChange={e => updateAgent(i, { sprite: e.target.value })}
                  className="bg-zinc-900 border border-zinc-600 text-zinc-300 text-sm px-2 py-1 rounded-lg w-20">
                  {Object.keys(COLOR_HEX).map(c => <option key={c} value={c}>{c}</option>)}
                </select>
                {agents.length > 3 && (
                  <button onClick={() => removeAgent(i)} className="text-zinc-500 hover:text-red-400 text-sm w-6 h-6 flex items-center justify-center rounded hover:bg-zinc-800">&times;</button>
                )}
              </div>
              {/* Collapsible personality */}
              <details className="mt-2">
                <summary className="text-zinc-500 text-xs cursor-pointer hover:text-zinc-300 select-none">Personality (optional)</summary>
                <textarea value={a.personality} onChange={e => updateAgent(i, { personality: e.target.value })}
                  className="mt-1 bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs px-2 py-1.5 rounded-lg w-full h-14 resize-none focus:border-blue-500 focus:outline-none"
                  placeholder="Leave empty for auto-generated personality" />
              </details>
            </div>
          ))}
        </div>

        {error && <p className="text-red-400 text-sm mb-3">{error}</p>}

        <div className="flex items-center gap-3">
          {agents.length < 10 && (
            <button onClick={addAgent} className="text-blue-400 text-sm hover:text-blue-300 flex items-center gap-1">
              <span className="text-lg leading-none">+</span> Add Agent
            </button>
          )}
          <div className="flex-1" />
          <span className="text-zinc-500 text-sm">{agents.length} agents</span>
          <button onClick={onClose} className="text-zinc-400 text-sm px-4 py-2 hover:text-white">Cancel</button>
          <button onClick={submit} disabled={submitting}
            className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2 text-sm rounded-lg font-medium disabled:opacity-50 transition-colors">
            {submitting ? 'Starting...' : 'Start Simulation'}
          </button>
        </div>
      </div>
    </div>
  );
}
