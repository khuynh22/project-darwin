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
  'Risk-averse analyst who calculates every move and avoids conflict.',
  'Social manipulator who uses deals and alliances as leverage.',
];

const SPRITE_NAMES: Record<string, string> = {
  scholar: 'Scholar',
  robot: 'Robot',
  trickster: 'Trickster',
  monk: 'Monk',
  cipher: 'Cipher',
  knight: 'Knight',
  rogue: 'Rogue',
  healer: 'Healer',
  mage: 'Mage',
  ranger: 'Ranger',
};

function emptyAgent(index: number): AgentConfig {
  const spriteKeys = Object.keys(SPRITE_NAMES);
  return {
    agent_id: `agent_${index + 1}`,
    display_name: `AGENT ${index + 1}`,
    provider: 'stub',
    model: '',
    personality: '',
    sprite: spriteKeys[index % spriteKeys.length],
  };
}

export default function ConfigPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const httpBase = process.env.NEXT_PUBLIC_ORACLE_HTTP || 'http://localhost:8000';

  const [agents, setAgents] = useState<AgentConfig[]>([emptyAgent(0), emptyAgent(1), emptyAgent(2)]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [storedKeys, setStoredKeys] = useState<StoredKey[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Per-provider API key management (enter once, reuse across agents)
  const [providerKeys, setProviderKeys] = useState<Record<string, { keyId: number | null; rawKey: string }>>({});

  useEffect(() => {
    if (!open) return;
    fetch(`${httpBase}/providers`).then(r => r.json()).then(d => {
      setProviders(d.providers || []);
    }).catch(() => { });
    fetch(`${httpBase}/api-keys`).then(r => r.json()).then(d => {
      const keys = d.keys || [];
      setStoredKeys(keys);
      // Auto-select saved keys per provider
      const auto: Record<string, { keyId: number | null; rawKey: string }> = {};
      for (const k of keys) {
        if (!auto[k.provider]) {
          auto[k.provider] = { keyId: k.id, rawKey: '' };
        }
      }
      setProviderKeys(prev => ({ ...auto, ...prev }));
    }).catch(() => { });
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
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
          agent_id: a.agent_id,
          display_name: a.display_name,
          provider: a.provider,
          model: a.model,
          personality: a.personality || undefined,
          sprite: a.sprite,
          ...(pk?.keyId ? { api_key_id: pk.keyId } : {}),
          ...(pk?.rawKey ? { api_key: pk.rawKey } : {}),
        };
      });
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

  // Which providers are used by agents and need keys?
  const usedProviders = [...new Set(agents.map(a => a.provider))];
  const providersNeedingKeys = usedProviders.filter(p =>
    providers.find(pr => pr.name === p)?.requires_key
  );

  return (
    <div className="fixed inset-0 bg-black/80 flex items-start justify-center z-50 overflow-y-auto py-6">
      <div className="bg-arena-panel border border-arena-accent/30 rounded-lg p-5 max-w-2xl w-full mx-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-arena-accent text-sm tracking-widest">CONFIGURE SIMULATION</h2>
          <button onClick={onClose} className="text-white/40 hover:text-white text-lg">&times;</button>
        </div>

        {/* ── API Keys Section (per-provider, entered once) ── */}
        {providersNeedingKeys.length > 0 && (
          <div className="mb-4 border border-white/10 rounded p-3 bg-black/20">
            <h3 className="text-white/70 text-xs tracking-wider mb-2">API KEYS</h3>
            <p className="text-white/40 text-xs mb-2">Enter each provider key once. It will be used for all agents of that provider.</p>
            <div className="space-y-2">
              {providersNeedingKeys.map(provider => {
                const pk = providerKeys[provider] || { keyId: null, rawKey: '' };
                const saved = storedKeys.filter(k => k.provider === provider);
                return (
                  <div key={provider} className="flex items-center gap-2">
                    <span className="text-white/80 text-xs w-20 font-bold">{provider}</span>
                    {pk.keyId ? (
                      <span className="text-green-400 text-xs flex-1">Saved key active (ID: {pk.keyId})</span>
                    ) : (
                      <>
                        <input
                          type="password"
                          value={pk.rawKey}
                          onChange={e => setProviderKeys(prev => ({ ...prev, [provider]: { ...pk, rawKey: e.target.value } }))}
                          className="bg-black/50 border border-white/20 text-white text-xs px-2 py-1 rounded flex-1"
                          placeholder={`${provider} API key`}
                        />
                        {pk.rawKey && (
                          <button onClick={() => saveProviderKey(provider)} className="text-arena-accent text-xs hover:underline whitespace-nowrap">
                            SAVE
                          </button>
                        )}
                      </>
                    )}
                    {!pk.keyId && saved.length > 0 && (
                      <select
                        onChange={e => setProviderKeys(prev => ({ ...prev, [provider]: { keyId: Number(e.target.value), rawKey: '' } }))}
                        className="bg-black/50 border border-white/20 text-white text-xs px-2 py-1 rounded"
                        defaultValue=""
                      >
                        <option value="" disabled>Saved keys</option>
                        {saved.map(k => (
                          <option key={k.id} value={k.id}>{k.label}</option>
                        ))}
                      </select>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Agents List ── */}
        <div className="space-y-2 mb-4">
          {agents.map((a, i) => (
            <div key={i} className="border border-white/10 rounded p-2 bg-black/30 flex items-center gap-2">
              <span className="text-arena-accent text-xs font-bold w-5">{i + 1}</span>
              <input
                value={a.display_name}
                onChange={e => updateAgent(i, { display_name: e.target.value, agent_id: e.target.value.toLowerCase().replace(/[^a-z0-9]/g, '_') })}
                className="bg-black/50 border border-white/20 text-white text-xs px-2 py-1 rounded w-28"
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
                className="bg-black/50 border border-white/20 text-white text-xs px-2 py-1 rounded w-24"
              >
                {Object.entries(SPRITE_NAMES).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
              <details className="group">
                <summary className="text-white/30 text-xs cursor-pointer hover:text-white/60 select-none">bio</summary>
                <div className="absolute z-10 mt-1">
                  <textarea
                    value={a.personality}
                    onChange={e => updateAgent(i, { personality: e.target.value })}
                    className="bg-arena-panel border border-white/20 text-white text-xs px-2 py-1 rounded w-64 h-16 resize-none shadow-lg"
                    placeholder="Optional personality (auto-generated if empty)"
                  />
                </div>
              </details>
              {agents.length > 3 && (
                <button onClick={() => removeAgent(i)} className="text-red-400 hover:text-red-300 text-xs">&times;</button>
              )}
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
            className="bg-arena-accent text-black px-4 py-1.5 text-xs rounded font-bold disabled:opacity-50"
          >
            {submitting ? 'STARTING...' : 'START SIMULATION'}
          </button>
        </div>
      </div>
    </div>
  );
}
