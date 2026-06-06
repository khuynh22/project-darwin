'use client';

import { Heart, Mountain, Cpu, Skull, Wheat } from 'lucide-react';
import type { AgentSnap, WorldSnapshot } from '@/lib/ws';
import { CritterAvatar } from './Critter';
import { COLOR_HEX } from '@/lib/town';

interface SidebarProps {
  snapshot: WorldSnapshot | null;
}

// Density tiers. The roster shares a fixed ~560px column with the Town, so the
// per-card budget shrinks as the roster grows. Each tier is purpose-built to
// stay legible and fit without scrolling or overlapping:
//   rich    (<=4): full cards
//   compact (5-7): two-line cards
//   mini   (8-10): two micro-line rows
type Tier = 'rich' | 'compact' | 'mini';

function tierFor(count: number): Tier {
  if (count <= 4) return 'rich';
  if (count <= 7) return 'compact';
  return 'mini';
}

const SPECIALTY: Record<string, { emoji: string; name: string }> = {
  ore: { emoji: '⛏️', name: 'Ore' },
  food: { emoji: '🍞', name: 'Food' },
  tech: { emoji: '⚙️', name: 'Tech' },
};

const ASIDE_PAD: Record<Tier, string> = { rich: 'p-3', compact: 'p-2.5', mini: 'p-2' };
const ASIDE_GAP: Record<Tier, string> = { rich: 'gap-2', compact: 'gap-1.5', mini: 'gap-1' };

const CARD_BASE =
  'relative rounded-2xl bg-[#FFF8EB] border-[1.5px] border-cozy-card-edge overflow-hidden shrink-0 transition-transform duration-200 hover:-translate-y-[2px] hover:rotate-[-0.4deg]';

export default function Sidebar({ snapshot }: SidebarProps) {
  const agents = snapshot?.agents ?? [];
  const alive = agents.filter((a) => a.alive).length;
  const tier = tierFor(agents.length);

  return (
    <aside
      className={`bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-3xl ${ASIDE_PAD[tier]} shadow-cozy-md flex flex-col ${ASIDE_GAP[tier]} h-full`}
    >
      <div className="flex items-center justify-between font-display font-semibold text-[14px] uppercase tracking-[0.1em] text-cozy-ink-soft px-1 pb-0.5 shrink-0">
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

      {agents.map((a) => (
        <RosterCard key={a.agent_id} a={a} tier={tier} />
      ))}
    </aside>
  );
}

function RosterCard({ a, tier }: { a: AgentSnap; tier: Tier }) {
  if (tier === 'rich') return <RichCard a={a} />;
  if (tier === 'compact') return <CompactCard a={a} />;
  return <MiniCard a={a} />;
}

/* ───────── Rich (<=4 critters) ───────── */
function RichCard({ a }: { a: AgentSnap }) {
  const dead = !a.alive;
  const color = COLOR_HEX[a.sprite] || '#FFCBA0';
  const spec = SPECIALTY[a.specialty];
  const subLabel = spec ? `${spec.emoji} ${spec.name.toLowerCase()} specialist` : a.provider;
  const inv = a.inventory || {};
  return (
    <div className={`${CARD_BASE} flex flex-col gap-[7px] p-[10px]`} style={deadStyle(dead)}>
      {dead && <OutRibbon />}

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
      <ModelChip model={a.model} color={color} />

      {/* Trust row */}
      <TrustBar score={a.trust_score} showLabel height={10} />

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
          {!hasInv(inv) && (
            <span className="text-[10px] italic text-cozy-ink-faint">empty pockets</span>
          )}
        </div>
        <div className="flex items-center gap-1 text-[13px]">
          {dead ? (
            <span className="flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md bg-red-100 text-red-700">
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

      <SocialTags a={a} />
    </div>
  );
}

/* ───────── Compact (5-7 critters) ───────── */
function CompactCard({ a }: { a: AgentSnap }) {
  const dead = !a.alive;
  const color = COLOR_HEX[a.sprite] || '#FFCBA0';
  const spec = SPECIALTY[a.specialty];
  const inv = a.inventory || {};
  const social = hasSocial(a);
  const showFoot = hasInv(inv) || social;
  return (
    <div className={`${CARD_BASE} flex flex-col gap-1 p-2`} style={deadStyle(dead)}>
      {/* Row 1: identity + balance */}
      <div className="flex items-center gap-2">
        <CritterAvatar color={color} size={28} alive={a.alive} />
        <div className="min-w-0 flex-1 flex items-center gap-1">
          <span className="font-display font-semibold text-[13px] leading-tight text-cozy-ink truncate">
            {a.display_name}
          </span>
          {spec && (
            <span title={`${spec.name} specialist`} className="text-[11px] leading-none shrink-0">
              {spec.emoji}
            </span>
          )}
        </div>
        <StatusGlyph a={a} dead={dead} />
        <div className="font-display font-semibold font-mono text-[16px] leading-none text-cozy-ink tabular-nums shrink-0">
          ${a.balance.toFixed(2)}
        </div>
      </div>

      {/* Row 2: model + trust */}
      <div className="flex items-center gap-2">
        <div className="min-w-0 max-w-[56%] shrink">
          <ModelChip model={a.model} color={color} dense />
        </div>
        <TrustBar score={a.trust_score} height={8} />
      </div>

      {/* Foot: inventory + social (only when present) */}
      {showFoot && (
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1 min-w-0">
            {inv.ore > 0 && (
              <InvPill icon={<Mountain size={9} className="text-[#A87A4A]" />} value={inv.ore} title="Ore" />
            )}
            {inv.food > 0 && (
              <InvPill icon={<Wheat size={9} className="text-[#C49A3B]" />} value={inv.food} title="Food" />
            )}
            {inv.tech > 0 && (
              <InvPill icon={<Cpu size={9} className="text-[#6F8FB2]" />} value={inv.tech} title="Tech" />
            )}
          </div>
          <SocialTags a={a} />
        </div>
      )}
    </div>
  );
}

/* ───────── Mini (8-10 critters) ───────── */
function MiniCard({ a }: { a: AgentSnap }) {
  const dead = !a.alive;
  const color = COLOR_HEX[a.sprite] || '#FFCBA0';
  const spec = SPECIALTY[a.specialty];
  const inv = a.inventory || {};
  return (
    <div className={`${CARD_BASE} flex flex-col gap-0.5 px-2 py-1`} style={deadStyle(dead)}>
      {/* Row 1: identity + balance */}
      <div className="flex items-center gap-1.5">
        <CritterAvatar color={color} size={22} alive={a.alive} />
        <span className="font-display font-semibold text-[12px] leading-none text-cozy-ink truncate min-w-0">
          {a.display_name}
        </span>
        {spec && (
          <span title={`${spec.name} specialist`} className="text-[10px] leading-none shrink-0">
            {spec.emoji}
          </span>
        )}
        <span className="ml-auto font-mono font-semibold text-[13px] leading-none text-cozy-ink tabular-nums shrink-0">
          ${a.balance.toFixed(2)}
        </span>
        <StatusGlyph a={a} dead={dead} />
      </div>

      {/* Row 2: model + trust + inventory + social, all compacted */}
      <div className="flex items-center gap-1.5">
        <div className="min-w-0 max-w-[44%] shrink">
          <ModelChip model={a.model} color={color} dense />
        </div>
        <TrustBar score={a.trust_score} height={6} />
        <InvMicro inv={inv} />
        <SocialBadges a={a} />
      </div>
    </div>
  );
}

/* ───────── Shared pieces ───────── */

function deadStyle(dead: boolean) {
  return dead ? { opacity: 0.55, filter: 'saturate(0.4)' } : undefined;
}

function hasInv(inv: Record<string, number>) {
  return (inv.ore || 0) > 0 || (inv.food || 0) > 0 || (inv.tech || 0) > 0;
}

function hasSocial(a: AgentSnap) {
  return Boolean(a.spouse || a.allies?.length || a.enemies?.length);
}

function OutRibbon() {
  return (
    <div
      aria-hidden
      className="absolute top-1/2 -right-5 -translate-y-1/2 -rotate-12 px-6 py-1 font-display font-bold tracking-[0.12em] text-white text-[12px]"
      style={{ background: 'var(--red)' }}
    >
      OUT
    </div>
  );
}

function ModelChip({ model, color, dense = false }: { model: string; color: string; dense?: boolean }) {
  if (!model) return null;
  return (
    <span
      title={model}
      className={`inline-flex items-center max-w-full rounded-full bg-[#FBE7C7] text-[#7A5A3A] font-mono truncate min-w-0 ${
        dense ? 'gap-1 pl-1 pr-1.5 py-[1px] text-[9px]' : 'gap-1.5 pl-1.5 pr-2.5 py-[3px] text-[11px] self-start'
      }`}
    >
      <span
        className={`rounded-full shrink-0 ${dense ? 'h-[5px] w-[5px]' : 'h-[7px] w-[7px]'}`}
        style={{ background: color }}
      />
      <span className="truncate">{model}</span>
    </span>
  );
}

function TrustBar({
  score,
  showLabel = false,
  height = 10,
}: {
  score: number;
  showLabel?: boolean;
  height?: number;
}) {
  const pct = Math.max(0, Math.min(100, score));
  return (
    <div className="flex items-center gap-1.5 flex-1 min-w-0">
      {showLabel && (
        <span className="text-[10px] uppercase tracking-[0.1em] text-cozy-ink-soft font-bold w-9 shrink-0">
          Trust
        </span>
      )}
      <div
        className="flex-1 rounded-[10px] overflow-hidden min-w-0"
        style={{ height, background: '#FFE7C9', boxShadow: 'inset 0 2px 0 rgba(74,58,46,0.06)' }}
      >
        <div className="trust-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="shrink-0 text-right font-mono text-[10px] font-bold text-cozy-ink-soft tabular-nums">
        {Math.round(pct)}
      </span>
    </div>
  );
}

// Mood emoji / invested marker / dead skull — the single right-aligned glyph
// used in the compact and mini tiers.
function StatusGlyph({ a, dead }: { a: AgentSnap; dead: boolean }) {
  if (dead) return <Skull size={12} className="text-[#B14848] shrink-0" />;
  if (a.invested > 0)
    return (
      <span title={`$${a.invested.toFixed(2)} invested`} className="text-[11px] leading-none shrink-0">
        📈
      </span>
    );
  return <span className="text-[12px] leading-none shrink-0">{moodFor(a)}</span>;
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

// Densest inventory form: a single emoji+count run, e.g. "⛏3 🍞1".
function InvMicro({ inv }: { inv: Record<string, number> }) {
  const parts: string[] = [];
  if ((inv.ore || 0) > 0) parts.push(`⛏${inv.ore}`);
  if ((inv.food || 0) > 0) parts.push(`🍞${inv.food}`);
  if ((inv.tech || 0) > 0) parts.push(`⚙${inv.tech}`);
  if (!parts.length) return null;
  return (
    <span title="Inventory" className="font-mono text-[9px] text-cozy-ink-soft whitespace-nowrap shrink-0">
      {parts.join(' ')}
    </span>
  );
}

// Readable social tags (rich + compact tiers).
function SocialTags({ a }: { a: AgentSnap }) {
  if (!hasSocial(a)) return null;
  return (
    <div className="flex flex-wrap items-center gap-1 text-[10px] min-w-0">
      {a.spouse && (
        <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-[#FFE2EC] text-[#B65978] font-semibold">
          <Heart size={9} fill="currentColor" /> {a.spouse}
        </span>
      )}
      {a.allies?.length > 0 && (
        <span className="px-1.5 py-0.5 rounded-md bg-[#E0F2E6] text-[#3A8559] font-semibold truncate">
          allies: {a.allies.join(', ')}
        </span>
      )}
      {a.enemies?.length > 0 && (
        <span className="px-1.5 py-0.5 rounded-md bg-[#FFE0E0] text-[#B14848] font-semibold truncate">
          enemies: {a.enemies.join(', ')}
        </span>
      )}
    </div>
  );
}

// Iconified social (mini tier): heart for spouse, dot+count for allies/enemies,
// names in the hover tooltip.
function SocialBadges({ a }: { a: AgentSnap }) {
  if (!hasSocial(a)) return null;
  return (
    <span className="flex items-center gap-1 shrink-0">
      {a.spouse && (
        <span title={`Married to ${a.spouse}`} className="text-[#B65978] flex items-center">
          <Heart size={10} fill="currentColor" />
        </span>
      )}
      {a.allies?.length > 0 && (
        <span
          title={`Allies: ${a.allies.join(', ')}`}
          className="flex items-center gap-0.5 text-[9px] font-bold text-[#3A8559]"
        >
          <span className="h-[6px] w-[6px] rounded-full bg-[#6FBF8E]" />
          {a.allies.length}
        </span>
      )}
      {a.enemies?.length > 0 && (
        <span
          title={`Enemies: ${a.enemies.join(', ')}`}
          className="flex items-center gap-0.5 text-[9px] font-bold text-[#B14848]"
        >
          <span className="h-[6px] w-[6px] rounded-full bg-[#E68A8A]" />
          {a.enemies.length}
        </span>
      )}
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
