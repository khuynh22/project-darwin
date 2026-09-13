'use client';

import { useFrame, useThree } from '@react-three/fiber';
import { useRef } from 'react';
import { Vector3 } from 'three';
import type { FrameAgent } from '@/lib/frame';
import { focusTarget, focusVenue } from '@/lib/proximity';
import type { Venue } from '@/lib/town';

/**
 * Reports whoever you are standing in front of, and which building.
 *
 * On foot this replaces clicking: you read an agent by walking over to it, and
 * a building by walking up to its door. Runs every frame but only reports a
 * change, so a panel re-renders when the answer differs and not sixty times a
 * second.
 */
export default function ProximityFocus({
  agents,
  focusedId,
  onFocus,
  venues = [],
  focusedVenueId = null,
  onVenueFocus,
}: {
  agents: FrameAgent[];
  focusedId: string | null;
  onFocus: (agentId: string | null) => void;
  venues?: Venue[];
  focusedVenueId?: string | null;
  onVenueFocus?: (venueId: string | null) => void;
}) {
  const camera = useThree((state) => state.camera);
  const look = useRef(new Vector3());
  const last = useRef<string | null>(focusedId);
  const lastVenue = useRef<string | null>(focusedVenueId);

  useFrame(() => {
    const direction = camera.getWorldDirection(look.current);
    const eye: [number, number, number] = [
      camera.position.x,
      camera.position.y,
      camera.position.z,
    ];
    const forward: [number, number, number] = [direction.x, direction.y, direction.z];

    const next = focusTarget(eye, forward, agents, last.current);
    if (next !== last.current) {
      last.current = next;
      onFocus(next);
    }

    if (!onVenueFocus) return;
    const nextVenue = focusVenue(eye, forward, venues, lastVenue.current);
    if (nextVenue !== lastVenue.current) {
      lastVenue.current = nextVenue;
      onVenueFocus(nextVenue);
    }
  });

  return null;
}
