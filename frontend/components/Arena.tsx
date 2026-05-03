'use client';

import { useEffect, useRef, useState } from 'react';
import type { WorldSnapshot } from '@/lib/ws';
import { ensureGame, syncSnapshot } from '@/lib/phaser/scene';

export default function Arena({ snapshot }: { snapshot: WorldSnapshot | null }) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!containerRef.current) return;
        try {
            const game = ensureGame(containerRef.current);
            return () => {
                game?.destroy(true);
            };
        } catch (err) {
            setError(String(err));
        }
    }, []);

    useEffect(() => {
        if (snapshot) syncSnapshot(snapshot);
    }, [snapshot]);

    if (error) {
        return (
            <div className="w-full h-full flex items-center justify-center text-red-400 text-xs p-4">
                Phaser failed to initialize: {error}
            </div>
        );
    }

    return <div ref={containerRef} className="w-full h-full" />;
}
