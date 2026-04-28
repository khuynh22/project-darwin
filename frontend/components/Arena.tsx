'use client';

import { useEffect, useRef } from 'react';
import type { WorldSnapshot } from '@/lib/ws';
import { ensureGame, syncSnapshot } from '@/lib/phaser/scene';

export default function Arena({ snapshot }: { snapshot: WorldSnapshot | null }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const game = ensureGame(containerRef.current);
    return () => {
      game?.destroy(true);
    };
  }, []);

  useEffect(() => {
    if (snapshot) syncSnapshot(snapshot);
  }, [snapshot]);

  return <div ref={containerRef} className="w-full h-full" />;
}
