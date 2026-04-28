'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import Sidebar from '@/components/Sidebar';
import ThoughtLog from '@/components/ThoughtLog';
import { connectOracle, type WorldSnapshot } from '@/lib/ws';

const Arena = dynamic(() => import('@/components/Arena'), { ssr: false });

export default function Page() {
  const [snapshot, setSnapshot] = useState<WorldSnapshot | null>(null);

  useEffect(() => {
    const close = connectOracle((snap) => setSnapshot(snap));
    return close;
  }, []);

  const httpBase = process.env.NEXT_PUBLIC_ORACLE_HTTP || 'http://localhost:8000';

  async function step(turns = 1) {
    await fetch(`${httpBase}/run?turns=${turns}`, { method: 'POST' });
  }

  return (
    <main className="grid grid-cols-[1fr_360px] h-screen">
      <section className="flex flex-col">
        <header className="px-4 py-3 bg-arena-panel border-b border-black/40 flex items-center gap-3">
          <h1 className="text-arena-accent text-sm tracking-widest">PROJECT DARWIN — TURN {snapshot?.turn ?? 0}</h1>
          <div className="flex-1" />
          <button onClick={() => step(1)} className="bg-arena-accent text-black px-3 py-1 text-xs">
            STEP 1
          </button>
          <button onClick={() => step(10)} className="bg-arena-accent text-black px-3 py-1 text-xs">
            RUN 10
          </button>
          <button onClick={() => step(100)} className="bg-arena-accent text-black px-3 py-1 text-xs">
            RUN 100
          </button>
        </header>
        <div id="phaser-root" className="flex-1 bg-black">
          <Arena snapshot={snapshot} />
        </div>
        <ThoughtLog snapshot={snapshot} />
      </section>
      <Sidebar snapshot={snapshot} />
    </main>
  );
}
