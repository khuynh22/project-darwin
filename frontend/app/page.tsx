'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ChevronsRight,
  Download,
  Eye,
  EyeOff,
  Play,
  RotateCcw,
  ScanEye,
  Settings2,
  Square,
  StepForward,
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import ThoughtLog from '@/components/ThoughtLog';
import PublicLog from '@/components/PublicLog';
import Town from '@/components/Town';
import ConfigPanel from '@/components/ConfigPanel';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { connectOracle, type PausedEvent, type WorldSnapshot } from '@/lib/ws';

// Auto-play tick must be >= walk duration so movement completes before next turn.
const AUTO_PLAY_DELAY_MS = 3700;

export default function Page() {
  const [snapshot, setSnapshot] = useState<WorldSnapshot | null>(null);
  const [pauseInfo, setPauseInfo] = useState<PausedEvent | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [pendingTurns, setPendingTurns] = useState(0);
  const [autoPlay, setAutoPlay] = useState(false);
  const autoPlayRef = useRef(false);

  useEffect(() => {
    const close = connectOracle(
      (snap) => {
        setSnapshot(snap);
        if (snap.agents.length === 0) setConfigOpen(true);
      },
      (evt) => {
        setPauseInfo(evt);
        autoPlayRef.current = false;
        setAutoPlay(false);
      },
    );
    return close;
  }, []);

  const httpBase = process.env.NEXT_PUBLIC_ORACLE_HTTP || 'http://localhost:8000';
  const hasAgents = (snapshot?.agents?.length ?? 0) > 0;

  const step = useCallback(
    async (turns = 1) => {
      if (!hasAgents) return;
      setRunning(true);
      setPendingTurns(turns);
      try {
        const res = await fetch(`${httpBase}/run?turns=${turns}`, { method: 'POST' });
        const data = await res.json();
        if (data.paused) {
          setPendingTurns(0);
          setPauseInfo({
            event: 'simulation_paused',
            turn: data.final_turn ?? data.turn,
            agent_id: data.agent_id,
            reason: data.reason,
            snapshot: snapshot!,
          });
          autoPlayRef.current = false;
          setAutoPlay(false);
        } else {
          setPendingTurns(0);
        }
      } finally {
        setRunning(false);
      }
    },
    [hasAgents, httpBase, snapshot],
  );

  useEffect(() => {
    autoPlayRef.current = autoPlay;
  }, [autoPlay]);

  useEffect(() => {
    if (!autoPlay || running || !hasAgents) return;
    const timer = setTimeout(() => {
      if (autoPlayRef.current) step(1);
    }, AUTO_PLAY_DELAY_MS);
    return () => clearTimeout(timer);
  }, [autoPlay, running, hasAgents, snapshot?.turn, step]);

  function toggleAutoPlay() {
    autoPlayRef.current = !autoPlay;
    setAutoPlay(!autoPlay);
  }

  async function removeAgent(agentId: string) {
    await fetch(`${httpBase}/agents/${agentId}/remove`, { method: 'POST' });
    setPauseInfo(null);
    const r = pendingTurns;
    if (r > 0) {
      setPendingTurns(0);
      setTimeout(() => step(r), 300);
    }
  }

  async function resumeSimulation() {
    await fetch(`${httpBase}/simulation/resume`, { method: 'POST' });
    setPauseInfo(null);
    const r = pendingTurns;
    if (r > 0) {
      setPendingTurns(0);
      setTimeout(() => step(r), 300);
    }
  }

  async function resetSim() {
    if (!confirm('Reset entire simulation? All data will be lost.')) return;
    autoPlayRef.current = false;
    setAutoPlay(false);
    await fetch(`${httpBase}/reset`, { method: 'POST' });
    setConfigOpen(true);
  }

  // Keyboard shortcuts: S = Step, Space = Auto, R = Reset
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (e.key === ' ' || e.key === 'Spacebar') {
        e.preventDefault();
        if (hasAgents) toggleAutoPlay();
      } else if (e.key === 's' || e.key === 'S') {
        if (hasAgents && !running && !autoPlay) step(1);
      } else if (e.key === 'r' || e.key === 'R') {
        resetSim();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoPlay, running, hasAgents]);

  const turn = snapshot?.turn ?? 0;
  const aliveCount = snapshot?.agents.filter((a) => a.alive).length ?? 0;
  const totalAgents = snapshot?.agents.length ?? 0;
  const treasury = snapshot?.agents.reduce((sum, a) => sum + a.balance, 0) ?? 0;
  const vis = snapshot?.balance_visibility;

  return (
    <main className="relative z-[1] mx-auto max-w-[1440px] px-[22px] pt-[14px] pb-[22px]">
      {/* Header */}
      <header className="flex items-center justify-between gap-6 bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-[22px] px-4 py-[10px] shadow-cozy mb-3">
        <div className="flex items-center gap-3">
          <div
            className="w-[38px] h-[38px] rounded-[12px] grid place-items-center text-[20px]"
            style={{ background: '#FFC089', boxShadow: '0 2px 0 rgba(74,58,46,0.08)' }}
          >
            🌱
          </div>
          <div>
            <h1 className="font-display font-semibold text-[19px] leading-none text-cozy-ink">
              Project Darwin
            </h1>
            <div className="text-[11px] font-bold uppercase tracking-[0.06em] text-cozy-ink-soft mt-[3px]">
              A tiny town of LLM critters
            </div>
          </div>
        </div>

        <div className="flex items-center gap-[10px]">
          <StatPill label="Turn" value={String(turn).padStart(2, '0')} mono />
          <StatPill label="Alive" value={`${aliveCount}/${totalAgents}`} />
          <StatPill label="Treasury" value={`$${treasury.toFixed(2)}`} mono />
          {vis && hasAgents && <VisPill vis={vis} />}
          {running && (
            <span className="flex items-center gap-1.5 text-[11px] font-semibold text-cozy-accent">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-cozy-accent animate-pulse" />
              thinking…
            </span>
          )}
        </div>

        <div className="flex items-center gap-[10px]">
          <Button
            variant="default"
            onClick={() => step(1)}
            disabled={running || !hasAgents || autoPlay}
          >
            <StepForward size={14} /> Step
          </Button>
          <Button
            variant="default"
            onClick={() => step(10)}
            disabled={running || !hasAgents || autoPlay}
          >
            <ChevronsRight size={14} /> +10
          </Button>
          <Button
            variant={autoPlay ? 'success' : 'primary'}
            onClick={toggleAutoPlay}
            disabled={!hasAgents}
          >
            <span className="dot" />
            {autoPlay ? (
              <>
                <Square size={12} /> Auto · ON
              </>
            ) : (
              <>
                <Play size={12} /> Auto
              </>
            )}
          </Button>
          <div className="w-px h-6 bg-cozy-card-edge mx-1" />
          <Button
            variant="ghost"
            onClick={() => window.open(`${httpBase}/export/thoughts`, '_blank')}
          >
            <Download size={14} /> Export
          </Button>
          <Button variant="ghost" onClick={() => setConfigOpen(true)}>
            <Settings2 size={14} /> Config
          </Button>
          <Button variant="ghost" onClick={resetSim}>
            <RotateCcw size={14} /> Reset
          </Button>
        </div>
      </header>

      {/* Main: Town + Roster */}
      <div className="grid grid-cols-[1fr_340px] gap-[14px] mb-3">
        <Town snapshot={snapshot} running={running} />
        <Sidebar snapshot={snapshot} />
      </div>

      {/* Logs */}
      <div className="grid grid-cols-2 gap-[14px]">
        <PublicLog snapshot={snapshot} />
        <ThoughtLog snapshot={snapshot} />
      </div>

      <div className="text-center text-[11px] font-semibold text-cozy-ink-soft mt-3">
        <Kbd>S</Kbd> Step &nbsp;·&nbsp; <Kbd>Space</Kbd> Auto &nbsp;·&nbsp; <Kbd>R</Kbd> Reset
      </div>

      <ConfigPanel open={configOpen} onClose={() => setConfigOpen(false)} />

      <Dialog
        open={pauseInfo !== null}
        onOpenChange={(open) => {
          if (!open) setPauseInfo(null);
        }}
      >
        <DialogContent size="sm">
          <DialogHeader>
            <DialogTitle className="!text-[#B14848]">A critter got stuck</DialogTitle>
            <DialogDescription>
              Agent <span className="font-display font-semibold text-cozy-ink">{pauseInfo?.agent_id}</span>{' '}
              ran into an error.
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <p className="text-[12px] font-mono leading-relaxed bg-[#FFF6E6] border border-cozy-card-edge p-3 rounded-xl break-words text-cozy-ink-soft">
              {pauseInfo?.reason}
            </p>
          </DialogBody>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPauseInfo(null)}>
              Dismiss
            </Button>
            <Button
              variant="outline"
              onClick={() => pauseInfo && removeAgent(pauseInfo.agent_id)}
            >
              Remove agent
            </Button>
            <Button variant="primary" onClick={resumeSimulation}>
              Retry
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}

function StatPill({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div
      className="flex flex-col gap-[2px] px-3 py-[6px] rounded-[14px] border-[1.5px] border-cozy-card-edge"
      style={{ background: '#FFF6E6', minWidth: 76 }}
    >
      <span className="text-[9px] font-bold uppercase tracking-[0.1em] text-cozy-ink-soft">
        {label}
      </span>
      <span
        className={`font-display font-semibold text-[18px] leading-none text-cozy-ink ${
          mono ? 'font-mono' : ''
        }`}
      >
        {value}
      </span>
    </div>
  );
}

function VisPill({ vis }: { vis: 'public' | 'fuzzy' | 'hidden' }) {
  const Icon = vis === 'public' ? Eye : vis === 'hidden' ? EyeOff : ScanEye;
  return (
    <span
      title={`Balance visibility for this run: ${vis}`}
      className="flex items-center gap-1 text-[10px] uppercase tracking-wider font-bold text-cozy-ink-soft px-2 py-1 rounded-lg border border-cozy-card-edge bg-[#FFF6E6]"
    >
      <Icon size={11} /> {vis}
    </span>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="font-mono bg-cozy-card border border-cozy-card-edge rounded-md px-[6px] py-[1px] text-[10px] shadow-[0_2px_0_rgba(74,58,46,0.08)] text-cozy-ink">
      {children}
    </kbd>
  );
}
