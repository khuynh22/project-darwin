'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import Sidebar from '@/components/Sidebar';
import ThoughtLog from '@/components/ThoughtLog';
import PublicLog from '@/components/PublicLog';
import WorldMap from '@/components/WorldMap';
import ConfigPanel from '@/components/ConfigPanel';
import { connectOracle, type WorldSnapshot, type PausedEvent } from '@/lib/ws';

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

  const step = useCallback(async (turns = 1) => {
    if (!hasAgents) return;
    setRunning(true);
    setPendingTurns(turns);
    try {
      const res = await fetch(`${httpBase}/run?turns=${turns}`, { method: 'POST' });
      const data = await res.json();
      if (data.paused) {
        setPendingTurns(0);
        setPauseInfo({ event: 'simulation_paused', turn: data.final_turn ?? data.turn, agent_id: data.agent_id, reason: data.reason, snapshot: snapshot! });
        autoPlayRef.current = false;
        setAutoPlay(false);
      } else {
        setPendingTurns(0);
      }
    } finally {
      setRunning(false);
    }
  }, [hasAgents, httpBase, snapshot]);

  useEffect(() => { autoPlayRef.current = autoPlay; }, [autoPlay]);
  useEffect(() => {
    if (!autoPlay || running || !hasAgents) return;
    const timer = setTimeout(() => { if (autoPlayRef.current) step(1); }, 500);
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
    if (r > 0) { setPendingTurns(0); setTimeout(() => step(r), 300); }
  }

  async function resumeSimulation() {
    await fetch(`${httpBase}/simulation/resume`, { method: 'POST' });
    setPauseInfo(null);
    const r = pendingTurns;
    if (r > 0) { setPendingTurns(0); setTimeout(() => step(r), 300); }
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
      <header className="flex-shrink-0 px-4 py-2 bg-zinc-900 border-b border-zinc-800 flex items-center gap-3">
        <div className="flex items-center gap-2">
          <h1 className="text-blue-400 text-sm font-semibold tracking-wide">Project Darwin</h1>
          <span className="text-zinc-500 text-xs font-mono bg-zinc-800 px-2 py-0.5 rounded">Turn {snapshot?.turn ?? 0}</span>
          {running && <span className="text-zinc-500 text-xs animate-pulse">running...</span>}
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-1.5">
          <button onClick={() => step(1)} disabled={running || !hasAgents || autoPlay}
            className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-3 py-1 text-xs rounded-md disabled:opacity-30 transition-colors border border-zinc-700">
            Step
          </button>
          <button onClick={() => step(10)} disabled={running || !hasAgents || autoPlay}
            className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-3 py-1 text-xs rounded-md disabled:opacity-30 transition-colors border border-zinc-700">
            +10
          </button>
          <button onClick={toggleAutoPlay} disabled={!hasAgents}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors border ${autoPlay ? 'bg-red-600 border-red-500 text-white' : 'bg-emerald-700 border-emerald-600 text-white'
              } disabled:opacity-30`}>
            {autoPlay ? 'Stop' : 'Auto'}
          </button>
        </div>
        <div className="w-px h-4 bg-zinc-700" />
        <div className="flex items-center gap-1.5">
          <button onClick={() => window.open(`${httpBase}/export/thoughts`, '_blank')}
            className="text-zinc-400 hover:text-zinc-200 text-xs px-2 py-1 rounded-md hover:bg-zinc-800 transition-colors">Export</button>
          <button onClick={() => setConfigOpen(true)}
            className="text-zinc-400 hover:text-zinc-200 text-xs px-2 py-1 rounded-md hover:bg-zinc-800 transition-colors">Config</button>
          <button onClick={resetSim}
            className="text-red-400/70 hover:text-red-400 text-xs px-2 py-1 rounded-md hover:bg-red-950/30 transition-colors">Reset</button>
        </div>
      </header>

      {/* Main content: 3-column layout */}
      <div className="flex-1 flex min-h-0">
        {/* Left: World map + Logs */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* World map (venues + agents) */}
          <WorldMap snapshot={snapshot} />

          {/* Bottom: Public feed + Private thoughts */}
          <div className="flex-shrink-0 h-48 flex border-t border-zinc-800">
            <PublicLog snapshot={snapshot} />
            <div className="w-px bg-zinc-800" />
            <ThoughtLog snapshot={snapshot} />
          </div>
        </div>

        {/* Right sidebar */}
        <Sidebar snapshot={snapshot} />
      </div>

      {/* Config modal */}
      <ConfigPanel open={configOpen} onClose={() => setConfigOpen(false)} />

      {/* Pause modal */}
      {pauseInfo && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-red-800 rounded-xl shadow-2xl p-5 max-w-md w-full mx-4">
            <h2 className="text-red-400 text-sm font-semibold mb-2">Simulation Paused</h2>
            <p className="text-zinc-300 text-sm mb-1">
              Agent <span className="text-blue-400 font-semibold">{pauseInfo.agent_id}</span> encountered an error:
            </p>
            <p className="text-red-300 text-xs bg-zinc-950 p-3 rounded-lg mb-4 break-words font-mono">{pauseInfo.reason}</p>
            <div className="flex gap-2">
              <button onClick={() => removeAgent(pauseInfo.agent_id)} className="flex-1 bg-red-700 hover:bg-red-600 text-white px-3 py-2 text-sm rounded-lg transition-colors">Remove Agent</button>
              <button onClick={resumeSimulation} className="flex-1 bg-blue-600 hover:bg-blue-500 text-white px-3 py-2 text-sm rounded-lg transition-colors">Retry</button>
              <button onClick={() => setPauseInfo(null)} className="px-3 py-2 text-sm text-zinc-400 hover:text-white border border-zinc-700 rounded-lg transition-colors">Dismiss</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
