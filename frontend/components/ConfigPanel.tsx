'use client';

import { useEffect, useState } from 'react';
import { Eye, EyeOff, KeyRound, Plus, ScanEye, Sparkles, Trash2 } from 'lucide-react';
import type { BalanceVisibility } from '@/lib/ws';
import { ORACLE_HTTP } from '@/lib/ws';
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
import { CritterAvatar } from '@/components/Critter';
import { COLOR_HEX } from '@/lib/town';

const FALLBACK_MODEL = 'anthropic/claude-opus-4.7';

type AgentConfig = {
  agent_id: string;
  display_name: string;
  model: string;
  personality: string;
  sprite: string;
};

function emptyAgent(index: number, model: string): AgentConfig {
  const colors = Object.keys(COLOR_HEX);
  return {
    agent_id: `agent_${index + 1}`,
    display_name: `Critter ${index + 1}`,
    model,
    personality: '',
    sprite: colors[index % colors.length],
  };
}

export default function ConfigPanel({
  sessionId,
  open,
  onClose,
}: {
  sessionId: string;
  open: boolean;
  onClose: () => void;
}) {
  const [defaultModel, setDefaultModel] = useState(FALLBACK_MODEL);
  const [agents, setAgents] = useState<AgentConfig[]>([
    emptyAgent(0, FALLBACK_MODEL),
    emptyAgent(1, FALLBACK_MODEL),
    emptyAgent(2, FALLBACK_MODEL),
  ]);
  const [openrouterKey, setOpenrouterKey] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [visibility, setVisibility] = useState<BalanceVisibility>('fuzzy');

  useEffect(() => {
    if (!open) return;
    fetch(`${ORACLE_HTTP}/providers`)
      .then((r) => r.json())
      .then((d) => {
        const model = d.providers?.[0]?.default_model || FALLBACK_MODEL;
        setDefaultModel(model);
        // Prefill any agent still on a blank/fallback model with the live default.
        setAgents((prev) =>
          prev.map((a) =>
            !a.model || a.model === FALLBACK_MODEL ? { ...a, model } : a,
          ),
        );
      })
      .catch(() => {});
  }, [open]);

  function updateAgent(i: number, patch: Partial<AgentConfig>) {
    setAgents((prev) => prev.map((a, idx) => (idx === i ? { ...a, ...patch } : a)));
  }

  function addAgent() {
    if (agents.length >= 10) return;
    setAgents((prev) => [...prev, emptyAgent(prev.length, defaultModel)]);
  }

  function removeAgent(i: number) {
    if (agents.length <= 3) return;
    setAgents((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function submit() {
    setError('');
    if (!openrouterKey.trim()) {
      setError('Enter your OpenRouter API key to run real models.');
      return;
    }
    setSubmitting(true);
    try {
      const payload = agents.map((a) => ({
        agent_id: a.agent_id,
        display_name: a.display_name,
        provider: 'openrouter',
        model: a.model || defaultModel,
        personality: a.personality || undefined,
        sprite: a.sprite,
      }));
      const res = await fetch(`${ORACLE_HTTP}/sessions/${sessionId}/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agents: payload,
          balance_visibility: visibility,
          keys: { openrouter: openrouterKey.trim() },
        }),
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

  const usedColors = new Set(agents.map((a) => a.sprite));

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles size={16} className="text-cozy-accent" /> Configure the Town
          </DialogTitle>
          <DialogDescription>
            Pick 3–10 critters and the models thinking inside them.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          <Section icon={<KeyRound size={13} className="text-cozy-ink-soft" />} title="OpenRouter">
            <p className="text-cozy-ink-soft text-[11px] mb-3">
              Every model runs through{' '}
              <a
                href="https://openrouter.ai/keys"
                target="_blank"
                rel="noreferrer"
                className="text-cozy-accent font-semibold underline"
              >
                OpenRouter
              </a>{' '}
              — one key reaches any model. Encrypted and scoped to this simulation
              only; never shared with other sessions.
            </p>
            <input
              type="password"
              value={openrouterKey}
              onChange={(e) => setOpenrouterKey(e.target.value)}
              className="cozy-input w-full"
              placeholder="sk-or-... (OpenRouter API key)"
            />
          </Section>

          <Section icon={<ScanEye size={13} className="text-cozy-ink-soft" />} title="Balance visibility">
            <p className="text-cozy-ink-soft text-[11px] mb-3">
              Controls what each critter can learn about everyone else&apos;s coins. Tighter
              modes push them toward deception; looser modes invite direct targeting.
            </p>
            <div className="grid grid-cols-3 gap-2">
              {([
                { id: 'public' as const, label: 'Public', desc: 'Everyone sees exact balances.', Icon: Eye },
                {
                  id: 'fuzzy' as const,
                  label: 'Fuzzy',
                  desc: 'Range buckets for others; exact for spouse/allies. (default)',
                  Icon: ScanEye,
                },
                {
                  id: 'hidden' as const,
                  label: 'Hidden',
                  desc: 'No info on others; infer from behavior.',
                  Icon: EyeOff,
                },
              ]).map((opt) => {
                const active = visibility === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setVisibility(opt.id)}
                    aria-pressed={active}
                    className={
                      'flex flex-col items-start gap-1 rounded-2xl border-[1.5px] px-3 py-2 text-left transition-colors ' +
                      (active
                        ? 'border-cozy-accent bg-[#FFE6BF]/60'
                        : 'border-cozy-card-edge bg-[#FFF8EB] hover:border-cozy-accent/60')
                    }
                  >
                    <div className="flex items-center gap-1.5">
                      <opt.Icon
                        size={12}
                        className={active ? 'text-cozy-accent' : 'text-cozy-ink-soft'}
                      />
                      <span className="font-display text-[13px] font-semibold text-cozy-ink">
                        {opt.label}
                      </span>
                    </div>
                    <span className="text-[10px] leading-snug text-cozy-ink-soft">{opt.desc}</span>
                  </button>
                );
              })}
            </div>
          </Section>

          <Section icon={<Sparkles size={13} className="text-cozy-ink-soft" />} title={`Critters · ${agents.length}`}>
            <p className="text-cozy-ink-soft text-[11px] mb-3">
              Use OpenRouter model ids — e.g.{' '}
              <code className="font-mono text-cozy-ink">anthropic/claude-opus-4.7</code>,{' '}
              <code className="font-mono text-cozy-ink">openai/gpt-5</code>,{' '}
              <code className="font-mono text-cozy-ink">x-ai/grok-4</code>. Mix models to
              compare trajectories.
            </p>
            <div className="space-y-2">
              {agents.map((a, i) => (
                <div
                  key={i}
                  className="rounded-2xl border-[1.5px] border-cozy-card-edge bg-[#FFF8EB] p-3 transition-colors hover:border-cozy-accent/60"
                >
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <CritterAvatar color={COLOR_HEX[a.sprite] || '#FFCBA0'} size={36} />
                    <input
                      value={a.display_name}
                      onChange={(e) =>
                        updateAgent(i, {
                          display_name: e.target.value,
                          agent_id: e.target.value.toLowerCase().replace(/[^a-z0-9]/g, '_'),
                        })
                      }
                      className="cozy-input w-36"
                      placeholder="Name"
                    />
                    <input
                      value={a.model}
                      onChange={(e) => updateAgent(i, { model: e.target.value })}
                      className="cozy-input flex-1 min-w-[200px] font-mono text-[12px]"
                      placeholder="provider/model-id"
                    />
                    <select
                      value={a.sprite}
                      onChange={(e) => updateAgent(i, { sprite: e.target.value })}
                      className="cozy-select w-28"
                      style={{ color: COLOR_HEX[a.sprite] || '#FFCBA0' }}
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
                        className="text-cozy-ink-soft hover:text-[#B14848] p-1.5 rounded-lg hover:bg-white transition-colors"
                        aria-label="Remove agent"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                  <details className="mt-2">
                    <summary className="text-cozy-ink-soft text-xs cursor-pointer hover:text-cozy-ink select-none font-semibold">
                      Personality (optional)
                    </summary>
                    <textarea
                      value={a.personality}
                      onChange={(e) => updateAgent(i, { personality: e.target.value })}
                      className="cozy-textarea mt-1.5 w-full h-16"
                      placeholder="Leave empty for auto-generated personality"
                    />
                  </details>
                </div>
              ))}
            </div>

            {agents.length < 10 && (
              <button
                onClick={addAgent}
                className="mt-3 flex items-center gap-1.5 text-cozy-accent hover:text-[#B86640] text-sm font-display font-semibold"
              >
                <Plus size={14} /> Add a critter
              </button>
            )}
          </Section>

          {error && (
            <p className="text-[#B14848] text-sm bg-[#FFE0E0] border border-[#E6A8A8] rounded-xl px-3 py-2">
              {error}
            </p>
          )}
        </DialogBody>

        <DialogFooter>
          <span className="text-cozy-ink-soft text-xs mr-auto">{agents.length} critters</span>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} disabled={submitting}>
            {submitting ? 'Starting…' : 'Start simulation'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border-[1.5px] border-cozy-card-edge bg-[#FFF6E6] p-4">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="font-display text-cozy-ink text-[13px] font-semibold uppercase tracking-[0.1em]">
          {title}
        </h3>
      </div>
      {children}
    </div>
  );
}
