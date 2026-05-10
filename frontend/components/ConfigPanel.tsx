'use client';

import { useState, useEffect } from 'react';
import { CheckCircle2, KeyRound, Plus, Sparkles, Trash2 } from 'lucide-react';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import AgentSigil from '@/components/AgentSigil';

type ProviderInfo = { name: string; default_model: string; requires_key: boolean };
type StoredKey = { id: number; provider: string; label: string };

type AgentConfig = {
  agent_id: string;
  display_name: string;
  provider: string;
  model: string;
  personality: string;
  sprite: string; // color name
};

const COLOR_HEX: Record<string, string> = {
  red: '#ef4444',
  blue: '#3b82f6',
  green: '#22c55e',
  purple: '#a855f7',
  orange: '#f97316',
  cyan: '#06b6d4',
  pink: '#ec4899',
  yellow: '#eab308',
  teal: '#14b8a6',
  indigo: '#6366f1',
};

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

  const [agents, setAgents] = useState<AgentConfig[]>([
    emptyAgent(0),
    emptyAgent(1),
    emptyAgent(2),
  ]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [storedKeys, setStoredKeys] = useState<StoredKey[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [providerKeys, setProviderKeys] = useState<
    Record<string, { keyId: number | null; rawKey: string }>
  >({});

  useEffect(() => {
    if (!open) return;
    fetch(`${httpBase}/providers`)
      .then((r) => r.json())
      .then((d) => setProviders(d.providers || []))
      .catch(() => {});
    fetch(`${httpBase}/api-keys`)
      .then((r) => r.json())
      .then((d) => {
        const keys = d.keys || [];
        setStoredKeys(keys);
        const auto: Record<string, { keyId: number | null; rawKey: string }> = {};
        for (const k of keys) {
          if (!auto[k.provider]) auto[k.provider] = { keyId: k.id, rawKey: '' };
        }
        setProviderKeys((prev) => ({ ...auto, ...prev }));
      })
      .catch(() => {});
  }, [open, httpBase]);

  function updateAgent(i: number, patch: Partial<AgentConfig>) {
    setAgents((prev) => prev.map((a, idx) => (idx === i ? { ...a, ...patch } : a)));
  }

  function addAgent() {
    if (agents.length >= 10) return;
    setAgents((prev) => [...prev, emptyAgent(prev.length)]);
  }

  function removeAgent(i: number) {
    if (agents.length <= 3) return;
    setAgents((prev) => prev.filter((_, idx) => idx !== i));
  }

  function onProviderChange(i: number, provider: string) {
    const info = providers.find((p) => p.name === provider);
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
      setStoredKeys((prev) => [...prev, { id: data.id, provider, label: data.label }]);
      setProviderKeys((prev) => ({ ...prev, [provider]: { keyId: data.id, rawKey: '' } }));
    }
  }

  async function submit() {
    setError('');
    setSubmitting(true);
    try {
      const payload = agents.map((a) => {
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
      if (data.error) setError(data.error);
      else onClose();
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  const usedProviders = [...new Set(agents.map((a) => a.provider))];
  const providersNeedingKeys = usedProviders.filter(
    (p) => providers.find((pr) => pr.name === p)?.requires_key,
  );

  // Colors already chosen by other agents (so we can grey them out)
  const usedColors = new Set(agents.map((a) => a.sprite));

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles size={16} className="text-blue-400" /> Configure Simulation
          </DialogTitle>
          <DialogDescription>Set up 3–10 agents to begin a new run.</DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          {/* API Keys section */}
          {providersNeedingKeys.length > 0 && (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-4">
              <div className="flex items-center gap-2 mb-3">
                <KeyRound size={13} className="text-zinc-400" />
                <h3 className="text-zinc-200 text-xs font-semibold uppercase tracking-wider">
                  API Keys
                </h3>
              </div>
              <div className="space-y-2">
                {providersNeedingKeys.map((provider) => {
                  const pk = providerKeys[provider] || { keyId: null, rawKey: '' };
                  const saved = storedKeys.filter((k) => k.provider === provider);
                  return (
                    <div key={provider} className="flex items-center gap-3">
                      <span className="text-zinc-300 text-sm w-20 font-medium capitalize">
                        {provider}
                      </span>
                      {pk.keyId ? (
                        <span className="text-emerald-400 text-xs flex items-center gap-1.5 flex-1">
                          <CheckCircle2 size={12} /> Key saved
                        </span>
                      ) : (
                        <>
                          <input
                            type="password"
                            value={pk.rawKey}
                            onChange={(e) =>
                              setProviderKeys((prev) => ({
                                ...prev,
                                [provider]: { ...pk, rawKey: e.target.value },
                              }))
                            }
                            className="bg-zinc-900 border border-zinc-700 text-zinc-200 text-sm px-3 py-1.5 rounded-md flex-1 focus:border-blue-500 focus:outline-none"
                            placeholder={`Enter ${provider} API key`}
                          />
                          {pk.rawKey && (
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={() => saveProviderKey(provider)}
                            >
                              Save
                            </Button>
                          )}
                        </>
                      )}
                      {!pk.keyId && saved.length > 0 && (
                        <select
                          onChange={(e) =>
                            setProviderKeys((prev) => ({
                              ...prev,
                              [provider]: { keyId: Number(e.target.value), rawKey: '' },
                            }))
                          }
                          className="bg-zinc-900 border border-zinc-700 text-zinc-300 text-sm px-2 py-1.5 rounded-md"
                          defaultValue=""
                        >
                          <option value="" disabled>
                            Saved…
                          </option>
                          {saved.map((k) => (
                            <option key={k.id} value={k.id}>
                              {k.label}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Agents */}
          <div className="space-y-2">
            {agents.map((a, i) => (
              <div
                key={i}
                className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3 hover:border-zinc-700 transition-colors"
              >
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 flex-shrink-0 flex items-center justify-center">
                    <AgentSigil color={COLOR_HEX[a.sprite] || '#888'} size={36} state="idle" />
                  </div>
                  <input
                    value={a.display_name}
                    onChange={(e) =>
                      updateAgent(i, {
                        display_name: e.target.value,
                        agent_id: e.target.value.toLowerCase().replace(/[^a-z0-9]/g, '_'),
                      })
                    }
                    className="bg-zinc-900 border border-zinc-700 text-zinc-100 text-sm px-2 py-1 rounded w-32 focus:border-blue-500 focus:outline-none"
                    placeholder="Name"
                  />
                  <select
                    value={a.provider}
                    onChange={(e) => onProviderChange(i, e.target.value)}
                    className="bg-zinc-900 border border-zinc-700 text-zinc-200 text-sm px-2 py-1 rounded"
                  >
                    {providers.map((p) => (
                      <option key={p.name} value={p.name}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                  <input
                    value={a.model}
                    onChange={(e) => updateAgent(i, { model: e.target.value })}
                    className="bg-zinc-900 border border-zinc-700 text-zinc-200 text-sm px-2 py-1 rounded flex-1 focus:border-blue-500 focus:outline-none"
                    placeholder="Model ID (optional)"
                  />
                  <select
                    value={a.sprite}
                    onChange={(e) => updateAgent(i, { sprite: e.target.value })}
                    className="bg-zinc-900 border border-zinc-700 text-zinc-200 text-sm px-2 py-1 rounded w-24"
                    style={{ color: COLOR_HEX[a.sprite] }}
                  >
                    {Object.keys(COLOR_HEX).map((c) => (
                      <option
                        key={c}
                        value={c}
                        disabled={usedColors.has(c) && c !== a.sprite}
                      >
                        {c}
                      </option>
                    ))}
                  </select>
                  {agents.length > 3 && (
                    <button
                      onClick={() => removeAgent(i)}
                      className="text-zinc-500 hover:text-red-400 p-1.5 rounded hover:bg-zinc-800 transition-colors"
                      aria-label="Remove agent"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
                <details className="mt-2">
                  <summary className="text-zinc-500 text-xs cursor-pointer hover:text-zinc-300 select-none">
                    Personality (optional)
                  </summary>
                  <textarea
                    value={a.personality}
                    onChange={(e) => updateAgent(i, { personality: e.target.value })}
                    className="mt-1.5 bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs px-2 py-1.5 rounded w-full h-16 resize-none focus:border-blue-500 focus:outline-none"
                    placeholder="Leave empty for auto-generated personality"
                  />
                </details>
              </div>
            ))}
          </div>

          {agents.length < 10 && (
            <Button variant="ghost" size="sm" onClick={addAgent} className="text-blue-400 hover:text-blue-300">
              <Plus size={13} /> Add agent
            </Button>
          )}

          {error && (
            <p className="text-red-400 text-sm bg-red-950/40 border border-red-900/60 rounded px-3 py-2">
              {error}
            </p>
          )}
        </DialogBody>

        <DialogFooter>
          <span className="text-zinc-500 text-xs mr-auto">{agents.length} agents</span>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" onClick={submit} disabled={submitting}>
            {submitting ? 'Starting…' : 'Start simulation'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
