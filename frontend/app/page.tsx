'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { createSession } from '@/lib/ws';

export default function Landing() {
  const router = useRouter();
  const [creating, setCreating] = useState(false);

  async function newSimulation() {
    setCreating(true);
    try {
      const id = await createSession();
      router.push(`/session/${id}`);
    } catch {
      setCreating(false);
    }
  }

  return (
    <main className="relative z-[1] min-h-screen grid place-items-center px-6">
      <div className="bg-cozy-card border-[1.5px] border-cozy-card-edge rounded-[28px] shadow-cozy px-10 py-12 max-w-[520px] text-center">
        <div
          className="w-[64px] h-[64px] rounded-[18px] grid place-items-center text-[34px] mx-auto mb-5"
          style={{ background: '#FFC089', boxShadow: '0 2px 0 rgba(74,58,46,0.08)' }}
        >
          🌱
        </div>
        <h1 className="font-display font-semibold text-[28px] leading-tight text-cozy-ink">
          Project Darwin
        </h1>
        <p className="text-[13px] font-bold uppercase tracking-[0.06em] text-cozy-ink-soft mt-1">
          A tiny town of LLM critters
        </p>
        <p className="text-cozy-ink-soft text-sm mt-5 leading-relaxed">
          Spin up your own private economic-survival simulation. Each one gets a
          shareable link — bring your own API keys, configure 3–10 critters, and
          watch them work, trade, scheme, and survive.
        </p>
        <div className="mt-7">
          <Button variant="primary" onClick={newSimulation} disabled={creating}>
            <Sparkles size={15} /> {creating ? 'Creating…' : 'New simulation'}
          </Button>
        </div>
        <p className="text-cozy-ink-soft text-[11px] mt-4">
          Anonymous · no account needed · your link is your save
        </p>
      </div>
    </main>
  );
}
