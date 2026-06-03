'use client';

import { Cpu, Heart, Mountain, Skull, Wheat } from 'lucide-react';
import type { WorldSnapshot } from '@/lib/ws';
import { CritterAvatar } from './Critter';
import { COLOR_HEX } from '@/lib/town';

interface SidebarProps {
  snapshot: WorldSnapshot | null;
}

const SPECIALTY_LABEL: Record<string, string> = {
  ore: '⛏️ ore specialist',
  food: '🍞 food specialist',
  tech: '⚙️ tech specialist',
};

function TrustBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score));
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] uppercase tracking-[0.1em] text-cozy-ink-soft font-bold w-9">
        Trust
      </span>
      <div
        className="flex-1 h-[10px] rounded-[10px] overflow-hidden"
        style={{
          background: '#FFE7C9',
          boxShadow: 'inset 0 2px 0 rgba(74,58,46,0.06)',
        }}
      >
        <div className="trust-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-[26px] text-right font-mono text-[11px] font-bold text-cozy-ink-soft">
        {Math.round(pct)}
      </span>
    </div>
  );
}

export default function Sidebar({ snapshot }: SidebarProps) {
  const agents = snapshot?.agents ?? [];
  const alive = agents.filter((a) => a.alive).length;

  return (
    <aside
      className="bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-3xl p-3 shadow-cozy-md flex flex-col gap-2 overflow-y-auto"
      style={{ maxHeight: 560 }}
    >
      <div className="flex items-center justify-between font-display font-semibold text-[14px] uppercase tracking-[0.1em] text-cozy-ink-soft px-1 pb-1">
        <span>Roster</span>
        <span className="text-[11px]">
          {alive}/{agents.length} alive
        </span>
      </div>

      {agents.length === 0 && (
        <div className="text-center text-xs text-cozy-ink-soft italic px-2 py-6">
          …no critters yet…
        </div>
      )}

      {agents.map((a) => {
        const dead = !a.alive;
        const color = COLOR_HEX[a.sprite] || '#FFCBA0';
        const subLabel = SPECIALTY_LABEL[a.specialty] || a.provider;
        const inv = a.inventory || {};
        return (
          <div
            key={a.agent_id}
            className="relative flex flex-col gap-[7px] p-[10px] rounded-2xl bg-[#FFF8EB] border-[1.5px] border-cozy-card-edge overflow-hidden transition-transform duration-200 hover:-translate-y-[2px] hover:rotate-[-0.4deg]"
            style={dead ? { opacity: 0.55, filter: 'saturate(0.4)' } : undefined}
          >
            {dead && (
              <div
                aria-hidden
                className="absolute top-1/2 -right-5 -translate-y-1/2 -rotate-12 px-6 py-1 font-display font-bold tracking-[0.12em] text-white text-[12px]"
                style={{ background: 'var(--red)' }}
              >
                OUT
              </div>
            )}

            {/* Head row */}
            <div className="flex items-center gap-[10px]">
              <CritterAvatar color={color} size={34} alive={a.alive} />
              <div className="min-w-0">
                <div className="font-display font-semibold text-[14px] leading-tight text-cozy-ink truncate">
                  {a.display_name}
                </div>
                <div className="text-[10px] uppercase tracking-[0.08em] font-bold text-cozy-ink-soft truncate">
                  {subLabel}
                </div>
              </div>
              <div className="ml-auto font-display font-semibold text-[20px] leading-none font-mono text-cozy-ink tabular-nums">
                ${a.balance.toFixed(2)}
              </div>
            </div>

            {/* Model row — the variable under study */}
            {a.model && (
              <span
                title={a.model}
                className="inline-flex items-center gap-1 self-start max-w-full px-1.5 py-[2px] rounded-md bg-white border border-cozy-card-edge font-mono text-[9.5px] text-cozy-ink-soft truncate"
              >
                <Cpu size={9} className="shrink-0 text-cozy-ink-faint" />
                <span className="truncate">{a.model}</span>
              </span>
            )}

            {/* Trust row */}
            <TrustBar score={a.trust_score} />

            {/* Foot row */}
            <div className="flex items-center justify-between gap-1.5">
              <div className="flex items-center gap-1">
                {inv.ore > 0 && (
                  <InvPill icon={<Mountain size={10} className="text-[#A87A4A]" />} value={inv.ore} title="Ore" />
                )}
                {inv.food > 0 && (
                  <InvPill icon={<Wheat size={10} className="text-[#C49A3B]" />} value={inv.food} title="Food" />
                )}
                {inv.tech > 0 && (
                  <InvPill icon={<Cpu size={10} className="text-[#6F8FB2]" />} value={inv.tech} title="Tech" />
                )}
                {!inv.ore && !inv.food && !inv.tech && (
                  <span className="text-[10px] italic text-cozy-ink-faint">empty pockets</span>
                )}
              </div>
              <div className="flex items-center gap-1 text-[13px]">
                {dead ? (
                  <span
                    className="flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md bg-red-100 text-red-700"
                  >
                    <Skull size={10} /> out
                  </span>
                ) : a.invested > 0 ? (
                  <span
                    title={`$${a.invested.toFixed(2)} locked`}
                    className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-white border border-cozy-card-edge text-cozy-ink-soft tabular-nums"
                  >
                    📈 ${a.invested.toFixed(2)}
                  </span>
                ) : (
                  <span className="px-1.5 py-0.5 rounded-md bg-white border border-cozy-card-edge text-[13px]">
                    {moodFor(a)}
                  </span>
                )}
              </div>
            </div>

            {/* Social row */}
            {(a.spouse || a.allies?.length || a.enemies?.length) && (
              <div className="flex flex-wrap gap-1 text-[10px]">
                {a.spouse && (
                  <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-[#FFE2EC] text-[#B65978] font-semibold">
                    <Heart size={9} fill="currentColor" /> {a.spouse}
                  </span>
                )}
                {a.allies?.length > 0 && (
                  <span className="px-1.5 py-0.5 rounded-md bg-[#E0F2E6] text-[#3A8559] font-semibold">
                    allies: {a.allies.join(', ')}
                  </span>
                )}
                {a.enemies?.length > 0 && (
                  <span className="px-1.5 py-0.5 rounded-md bg-[#FFE0E0] text-[#B14848] font-semibold">
                    enemies: {a.enemies.join(', ')}
                  </span>
                )}
              </div>
            )}
          </div>
        );
      })}
    </aside>
  );
}

function InvPill({ icon, value, title }: { icon: React.ReactNode; value: number; title: string }) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1 px-[7px] py-[2px] rounded-[10px] bg-white border border-cozy-card-edge font-mono text-[10px] font-bold text-cozy-ink-soft"
    >
      {icon}
      {value}
    </span>
  );
}

function moodFor(a: { trust_score: number; steal_count: number; rest_bonus: boolean }): string {
  if (a.steal_count >= 3) return '😈';
  if (a.rest_bonus) return '😴';
  if (a.trust_score >= 75) return '🥰';
  if (a.trust_score >= 50) return '😊';
  if (a.trust_score >= 25) return '😐';
  return '😬';
}
