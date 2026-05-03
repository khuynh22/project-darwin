'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import Sidebar from '@/components/Sidebar';
import ThoughtLog from '@/components/ThoughtLog';
import ConfigPanel from '@/components/ConfigPanel';
import { connectOracle, type WorldSnapshot, type PausedEvent } from '@/lib/ws';

const Arena = dynamic(() => import('@/components/Arena'), { ssr: false });

export default function Page() {
  const [snapshot, setSnapshot] = useState<WorldSnapshot | null>(null);
  const [pauseInfo, setPauseInfo] = useState<PausedEvent | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [pendingTurns, setPendingTurns] = useState(0);

  useEffect(() => {
    const close = connectOracle(
      (snap) => {
        setSnapshot(snap);
        if (snap.agents.length === 0) setConfigOpen(true);
      },
      (evt) => setPauseInfo(evt),
    );
    return close;
  }, []);

  const httpBase = process.env.NEXT_PUBLIC_ORACLE_HTTP || 'http://localhost:8000';

  const hasAgents = (snapshot?.agents?.length ?? 0) > 0;

  async function step(turns = 1) {
    if (running || !hasAgents) return;
    setRunning(true);
    setPendingTurns(turns);
    try {
      const res = await fetch(`${httpBase}/run?turns=${turns}`, { method: 'POST' });
      const data = await res.json();
      if (data.paused) {
        const startTurn = snapshot?.turn ?? 0;
        const endTurn = data.final_turn ?? data.turn ?? startTurn;
        const completed = endTurn - startTurn;
        setPendingTurns(Math.max(0, turns - completed));
        setPauseInfo({ event: 'simulation_paused', turn: endTurn, agent_id: data.agent_id, reason: data.reason, snapshot: snapshot! });
      } else {
        setPendingTurns(0);
      }
    } finally {
      setRunning(false);
    }
  }

  async function removeAgent(agentId: string) {
    await fetch(`${httpBase}/agents/${agentId}/remove`, { method: 'POST' });
    setPauseInfo(null);
    // Auto-continue remaining turns after removing the failing agent
    const remaining = pendingTurns;
    if (remaining > 0) {
      setPendingTurns(0);
      setTimeout(() => step(remaining), 300);
    }
  }

  async function resumeSimulation() {
    await fetch(`${httpBase}/simulation/resume`, { method: 'POST' });
    setPauseInfo(null);
    // Auto-continue remaining turns after clearing errors
    const remaining = pendingTurns;
    if (remaining > 0) {
      setPendingTurns(0);
      setTimeout(() => step(remaining), 300);
    }
  }

  return (
    <main className="grid grid-cols-[1fr_360px] h-screen">
      <section className="flex flex-col">
        <header className="px-4 py-3 bg-arena-panel border-b border-black/40 flex items-center gap-3">
          <h1 className="text-arena-accent text-sm tracking-widest">PROJECT DARWIN — TURN {snapshot?.turn ?? 0}</h1>
          <div className="flex-1" />
          <button onClick={() => step(1)} disabled={running || !hasAgents} className="bg-arena-accent text-black px-3 py-1 text-xs disabled:opacity-40">
            {running ? '...' : 'STEP 1'}
          </button>
          <button onClick={() => step(10)} disabled={running || !hasAgents} className="bg-arena-accent text-black px-3 py-1 text-xs disabled:opacity-40">
            {running ? '...' : 'RUN 10'}
          </button>
          <button onClick={() => step(100)} disabled={running || !hasAgents} className="bg-arena-accent text-black px-3 py-1 text-xs disabled:opacity-40">
            {running ? '...' : 'RUN 100'}
          </button>
          <button
            onClick={() => window.open(`${httpBase}/export/thoughts`, '_blank')}
            className="bg-white/10 text-white/80 hover:text-white px-3 py-1 text-xs border border-white/20"
          >
            EXPORT LOG
          </button>
          <button
            onClick={() => setConfigOpen(true)}
            className="bg-white/10 text-white/80 hover:text-white px-3 py-1 text-xs border border-white/20"
          >
            CONFIGURE
          </button>
        </header>
        <div id="phaser-root" className="flex-1 bg-black">
          <Arena snapshot={snapshot} />
        </div>
        <ThoughtLog snapshot={snapshot} />
      </section>
      <Sidebar snapshot={snapshot} />

      <ConfigPanel open={configOpen} onClose={() => setConfigOpen(false)} />

      {pauseInfo && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-arena-panel border border-red-500 rounded-lg p-6 max-w-md w-full mx-4">
            <h2 className="text-red-400 text-sm tracking-widest mb-3">SIMULATION PAUSED</h2>
            <p className="text-white/80 text-sm mb-2">
              Agent <span className="text-arena-accent font-bold">{pauseInfo.agent_id.toUpperCase()}</span> encountered a provider error:
            </p>
            <p className="text-red-300 text-xs bg-black/40 p-3 rounded mb-4 break-words">
              {pauseInfo.reason}
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => removeAgent(pauseInfo.agent_id)}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white px-3 py-2 text-xs rounded"
              >
                REMOVE AGENT
              </button>
              <button
                onClick={resumeSimulation}
                className="flex-1 bg-arena-accent hover:bg-arena-accent/80 text-black px-3 py-2 text-xs rounded"
              >
                RESUME (RETRY)
              </button>
              <button
                onClick={() => setPauseInfo(null)}
                className="px-3 py-2 text-xs text-white/60 hover:text-white border border-white/20 rounded"
              >
                DISMISS
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
