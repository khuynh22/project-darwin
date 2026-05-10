'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import {
  ChevronsRight,
  Download,
  Play,
  RotateCcw,
  Settings2,
  Square,
  StepForward,
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import ThoughtLog from '@/components/ThoughtLog';
import PublicLog from '@/components/PublicLog';
import HexArena from '@/components/HexArena';
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
import { connectOracle, type WorldSnapshot, type PausedEvent } from '@/lib/ws';

// Auto-play tick must be >= sigil walk duration so movement completes before next turn.
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

  return (
    <main className="flex flex-col h-screen bg-zinc-950">
      {/* Header */}
      <header className="flex-shrink-0 px-4 py-2 bg-zinc-900/95 backdrop-blur border-b border-zinc-800 flex items-center gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-2">
            <span
              aria-hidden
              className="inline-block h-2 w-2 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(96,165,250,0.8)]"
            />
            <h1 className="text-zinc-100 text-sm font-semibold tracking-wide">
              Project Darwin
            </h1>
          </div>
          <span className="text-zinc-400 text-xs font-mono bg-zinc-800/80 px-2 py-0.5 rounded border border-zinc-700/60">
            Turn {snapshot?.turn ?? 0}
          </span>
          {running && (
            <span className="text-blue-300 text-xs flex items-center gap-1.5">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
              thinking…
            </span>
          )}
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-1.5">
          <Button
            variant="default"
            size="sm"
            onClick={() => step(1)}
            disabled={running || !hasAgents || autoPlay}
          >
            <StepForward size={13} /> Step
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={() => step(10)}
            disabled={running || !hasAgents || autoPlay}
          >
            <ChevronsRight size={13} /> +10
          </Button>
          <Button
            variant={autoPlay ? 'danger' : 'success'}
            size="sm"
            onClick={toggleAutoPlay}
            disabled={!hasAgents}
          >
            {autoPlay ? (
              <>
                <Square size={12} /> Stop
              </>
            ) : (
              <>
                <Play size={12} /> Auto
              </>
            )}
          </Button>
        </div>
        <div className="w-px h-5 bg-zinc-800" />
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => window.open(`${httpBase}/export/thoughts`, '_blank')}
          >
            <Download size={13} /> Export
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setConfigOpen(true)}>
            <Settings2 size={13} /> Config
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={resetSim}
            className="text-red-400/80 hover:text-red-300 hover:bg-red-950/40"
          >
            <RotateCcw size={13} /> Reset
          </Button>
        </div>
      </header>

      {/* Main content: 3-column layout */}
      <div className="flex-1 flex min-h-0">
        {/* Left: Arena + Logs */}
        <div className="flex-1 flex flex-col min-w-0">
          <HexArena snapshot={snapshot} running={running} />

          {/* Bottom: Public feed + Private thoughts */}
          <div className="flex-shrink-0 h-48 flex border-t border-zinc-800">
            <PublicLog snapshot={snapshot} />
            <div className="w-px bg-zinc-800" />
            <ThoughtLog snapshot={snapshot} />
          </div>
        </div>

        {/* Right sidebar */}
        <Sidebar snapshot={snapshot} running={running} />
      </div>

      {/* Config modal */}
      <ConfigPanel open={configOpen} onClose={() => setConfigOpen(false)} />

      {/* Pause dialog */}
      <Dialog
        open={pauseInfo !== null}
        onOpenChange={(open) => {
          if (!open) setPauseInfo(null);
        }}
      >
        <DialogContent size="sm" className="border-red-900/70">
          <DialogHeader>
            <DialogTitle className="text-red-300">Simulation paused</DialogTitle>
            <DialogDescription>
              Agent{' '}
              <span className="text-blue-300 font-semibold">{pauseInfo?.agent_id}</span>{' '}
              encountered an error.
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <p className="text-red-200/90 text-xs bg-zinc-950/80 border border-zinc-800 p-3 rounded-lg break-words font-mono leading-relaxed">
              {pauseInfo?.reason}
            </p>
          </DialogBody>
          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPauseInfo(null)}
            >
              Dismiss
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => pauseInfo && removeAgent(pauseInfo.agent_id)}
            >
              Remove agent
            </Button>
            <Button variant="primary" size="sm" onClick={resumeSimulation}>
              Retry
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
