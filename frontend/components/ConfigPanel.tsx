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
  sprite: string;
  api_key: string;
  api_key_id: number | null;
};

const DEFAULT_PERSONALITIES = [
  'Cooperative negotiator who builds trust and prefers long-term alliances.',
  'High-risk strategist and aggressive optimizer who exploits opportunities.',
  'Unpredictable wildcard who switches strategies turn-to-turn.',
  'Data-driven survivalist who hoards information and acts patiently.',
  'Efficiency-focused minimalist who works steadily and avoids risk.',
  'Charismatic leader who forms coalitions and leverages social bonds.',
  'Ruthless competitor who steals, sabotages, and dominates through force.',
  'Philanthropic idealist who donates and lends to help the weakest.',
];

function emptyAgent(index: number): AgentConfig {
  return {
    agent_id: `agent_${index + 1}`,
    display_name: `AGENT ${index + 1}`,
    provider: 'stub',
    model: '',
    personality: DEFAULT_PERSONALITIES[index % DEFAULT_PERSONALITIES.length],
    sprite: 'robot',
    api_key: '',
    api_key_id: null,
  };
}

export default function ConfigPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const httpBase = process.env.NEXT_PUBLIC_ORACLE_HTTP || 'http://localhost:8000';

  const [agents, setAgents] = useState<AgentConfig[]>([emptyAgent(0), emptyAgent(1), emptyAgent(2)]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [sprites, setSprites] = useState<string[]>([]);
  const [storedKeys, setStoredKeys] = useState<StoredKey[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    fetch(`${httpBase}/providers`).then(r => r.json()).then(d => {
      setProviders(d.providers || []);
      setSprites(d.sprites || []);
    }).catch(() => {});
    fetch(`${httpBase}/api-keys`).then(r => r.json()).then(d => {
      setStoredKeys(d.keys || []);
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

  async function saveKey(i: number) {
    const a = agents[i];
    if (!a.api_key) return;
    const res = await fetch(`${httpBase}/api-keys`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: a.provider, label: `${a.display_name} key`, key: a.api_key }),
    });
    const data = await res.json();
    if (data.id) {
      setStoredKeys(prev => [...prev, { id: data.id, provider: a.provider, label: data.label }]);
      updateAgent(i, { api_key_id: data.id, api_key: '' });
    }
  }

  async function submit() {
    setError('');
    setSubmitting(true);
    try {
      const payload = agents.map(a => ({
        agent_id: a.agent_id,
        display_name: a.display_name,
        provider: a.provider,
        model: a.model,
        personality: a.personality,
        sprite: a.sprite,
        ...(a.api_key_id ? { api_key_id: a.api_key_id } : {}),
        ...(a.api_key ? { api_key: a.api_key } : {}),
      }));
      const res = await fetch(`${httpBase}/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agents: payload }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
      } else {
        onClose();
      }
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) return null;

  const providerNeedsKey = (name: string) => providers.find(p => p.name === name)?.requires_key ?? false;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-start justify-center z-50 overflow-y-auto py-8">
      <div className="bg-arena-panel border border-arena-accent/30 rounded-lg p-6 max-w-3xl w-full mx-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-arena-accent text-sm tracking-widest">CONFIGURE SIMULATION</h2>
          <button onClick={onClose} className="text-white/40 hover:text-white text-lg">&times;</button>
        </div>

        <p className="text-white/60 text-xs mb-4">Set up 3-10 agents. Each agent can use any provider and model.</p>

        <div className="space-y-4 mb-4">
          {agents.map((a, i) => (
            <div key={i} className="border border-white/10 rounded p-3 bg-black/30">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-arena-accent text-xs font-bold w-6">{i + 1}</span>
                <input
                  value={a.display_name}
                  onChange={e => updateAgent(i, { display_name: e.target.value, agent_id: e.target.value.toLowerCase().replace(/\s+/g, '_') })}
                  className="bg-black/50 border border-white/20 text-white text-xs px-2 py-1 rounded w-32"
                  placeholder="Name"
                />
                <select
                  value={a.provider}
                  onChange={e => onProviderChange(i, e.target.value)}
                  className="bg-black/50 border border-white/20 text-white text-xs px-2 py-1 rounded"
                >
                  {providers.map(p => (
                    <option key={p.name} value={p.name}>{p.name}</option>
                  ))}
                </select>
                <input
                  value={a.model}
                  onChange={e => updateAgent(i, { model: e.target.value })}
                  className="bg-black/50 border border-white/20 text-white text-xs px-2 py-1 rounded flex-1"
                  placeholder="Model ID"
                />
                <select
                  value={a.sprite}
                  onChange={e => updateAgent(i, { sprite: e.target.value })}
                  className="bg-black/50 border border-white/20 text-white text-xs px-2 py-1 rounded"
                >
                  {sprites.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                {agents.length > 3 && (
                  <button onClick={() => removeAgent(i)} className="text-red-400 hover:text-red-300 text-xs px-1">&times;</button>
                )}
              </div>

              {providerNeedsKey(a.provider) && (
                <div className="flex items-center gap-2 mb-2">
                  {a.api_key_id ? (
                    <span className="text-green-400 text-xs">Key stored (ID: {a.api_key_id})</span>
                  ) : (
                    <>
                      <input
                        type="password"
                        value={a.api_key}
                        onChange={e => updateAgent(i, { api_key: e.target.value })}
                        className="bg-black/50 border border-white/20 text-white text-xs px-2 py-1 rounded flex-1"
                        placeholder="API Key"
                      />
                      {a.api_key && (
                        <button onClick={() => saveKey(i)} className="text-arena-accent text-xs hover:underline">
                          SAVE KEY
                        </button>
                      )}
                      {storedKeys.filter(k => k.provider === a.provider).length > 0 && (
                        <select
                          onChange={e => updateAgent(i, { api_key_id: Number(e.target.value), api_key: '' })}
                          className="bg-black/50 border border-white/20 text-white text-xs px-2 py-1 rounded"
                          defaultValue=""
                        >
                          <option value="" disabled>Use saved...</option>
                          {storedKeys.filter(k => k.provider === a.provider).map(k => (
                            <option key={k.id} value={k.id}>{k.label}</option>
                          ))}
                        </select>
                      )}
                    </>
                  )}
                </div>
              )}

              <textarea
                value={a.personality}
                onChange={e => updateAgent(i, { personality: e.target.value })}
                className="bg-black/50 border border-white/20 text-white text-xs px-2 py-1 rounded w-full h-12 resize-none"
                placeholder="Personality description..."
              />
            </div>
          ))}
        </div>

        {error && <p className="text-red-400 text-xs mb-3">{error}</p>}

        <div className="flex items-center gap-3">
          {agents.length < 10 && (
            <button onClick={addAgent} className="text-arena-accent text-xs border border-arena-accent/30 px-3 py-1 rounded hover:bg-arena-accent/10">
              + ADD AGENT
            </button>
          )}
          <div className="flex-1" />
          <span className="text-white/40 text-xs">{agents.length} agents</span>
          <button onClick={onClose} className="text-white/60 text-xs px-3 py-1">CANCEL</button>
          <button
            onClick={submit}
            disabled={submitting}
            className="bg-arena-accent text-black px-4 py-1 text-xs rounded disabled:opacity-50"
          >
            {submitting ? 'STARTING...' : 'START SIMULATION'}
          </button>
        </div>
      </div>
    </div>
  );
}
