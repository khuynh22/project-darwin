'use client';

import { useFrame, useThree } from '@react-three/fiber';
import { useRef } from 'react';
import { Vector3 } from 'three';
import type { FrameAgent } from '@/lib/frame';
import { focusTarget } from '@/lib/proximity';

/**
 * Reports whoever you are standing in front of.
 *
 * On foot this replaces clicking: you read an agent by walking over to it.
 * Runs every frame but only reports a change, so the panel re-renders when the
 * answer differs and not sixty times a second.
 */
export default function ProximityFocus({
  agents,
  focusedId,
  onFocus,
}: {
  agents: FrameAgent[];
  focusedId: string | null;
  onFocus: (agentId: string | null) => void;
}) {
  const camera = useThree((state) => state.camera);
  const look = useRef(new Vector3());
  const last = useRef<string | null>(focusedId);

  useFrame(() => {
    const direction = camera.getWorldDirection(look.current);
    const next = focusTarget(
      [camera.position.x, camera.position.y, camera.position.z],
      [direction.x, direction.y, direction.z],
      agents,
      last.current,
    );
    if (next !== last.current) {
      last.current = next;
      onFocus(next);
    }
  });

  return null;
}
