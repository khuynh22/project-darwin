'use client';

import { Billboard, Text } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useRef } from 'react';
import type { Group } from 'three';
import type { FrameAgent } from '@/lib/frame';
import { easeInOutCubic, facingAngle, lerp3, walkDuration } from '@/lib/motion';
import type { Vec3 } from '@/lib/world3d';

// Person-sized, so standing next to one reads as standing next to someone.
const BODY_RADIUS = 0.32;
const BODY_HEIGHT = 1.7;

// A step's worth of rise and fall. Enough to read as walking from across the
// plaza, small enough not to look like hopping when you are stood next to it.
const BOB_HEIGHT = 0.07;
const BOB_STEPS = 9;

/**
 * One agent, walking to wherever this turn put it.
 *
 * The trace records where an agent stood on each turn and says nothing about
 * the space between, so the walk is a rendering choice and carries no claim:
 * the agent is at the recorded position whenever a turn is settled.
 */
export default function AgentPawn({
  agent,
  selected = false,
  onSelect,
}: {
  agent: FrameAgent;
  selected?: boolean;
  onSelect?: (agentId: string) => void;
}) {
  const group = useRef<Group>(null);

  // Mutable and outside React on purpose: this changes every frame, and a
  // re-render per frame per agent is how ten agents become a slideshow.
  const walk = useRef({
    from: agent.position,
    to: agent.position,
    elapsed: 0,
    duration: 0,
    facing: 0,
  });

  useFrame((_, rawDelta) => {
    const node = group.current;
    if (!node) return;

    const state = walk.current;

    // A new turn landed: walk from wherever the body actually is, not from
    // where the last turn nominally put it, or a fast scrub teleports.
    if (state.to !== agent.position) {
      const current: Vec3 = [node.position.x, 0, node.position.z];
      state.from = current;
      state.to = agent.position;
      state.elapsed = 0;
      state.duration = walkDuration(current, agent.position);
    }

    const delta = Math.min(rawDelta, 0.05);
    state.elapsed = Math.min(state.elapsed + delta, state.duration);
    const t = state.duration === 0 ? 1 : state.elapsed / state.duration;
    const eased = easeInOutCubic(t);

    const [x, , z] = lerp3(state.from, state.to, eased);
    const walking = t < 1;
    const bob = walking ? Math.abs(Math.sin(eased * Math.PI * BOB_STEPS)) * BOB_HEIGHT : 0;
    node.position.set(x, bob, z);

    if (walking) {
      state.facing = facingAngle(state.from, state.to, state.facing);
    }
    node.rotation.y = state.facing;
  });

  return (
    <group
      ref={group}
      position={agent.position}
      onClick={(e) => {
        // Without this the ray carries on and every pawn behind this one is
        // selected too, so the last in depth order wins.
        e.stopPropagation();
        onSelect?.(agent.agentId);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        document.body.style.cursor = 'pointer';
      }}
      onPointerOut={() => {
        document.body.style.cursor = '';
      }}
    >
      <mesh position={[0, BODY_HEIGHT / 2, 0]} castShadow receiveShadow>
        <capsuleGeometry args={[BODY_RADIUS, BODY_HEIGHT - BODY_RADIUS * 2, 4, 12]} />
        <meshStandardMaterial
          color={agent.color}
          roughness={0.6}
          emissive={selected ? '#E8956A' : '#000000'}
          emissiveIntensity={selected ? 0.55 : 0}
        />
      </mesh>

      {/* Which way it is facing, so a walking agent reads as going somewhere
          rather than sliding. */}
      <mesh position={[0, BODY_HEIGHT * 0.72, -BODY_RADIUS * 0.85]}>
        <sphereGeometry args={[BODY_RADIUS * 0.28, 10, 10]} />
        <meshStandardMaterial color="#3A2E24" roughness={0.9} />
      </mesh>

      {selected && (
        <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[BODY_RADIUS + 0.2, BODY_RADIUS + 0.38, 24]} />
          <meshBasicMaterial color="#E8956A" />
        </mesh>
      )}

      {/* Billboarded explicitly: the group turns to face where the agent is
          walking, and a name that turns away with it is useless. */}
      <Billboard position={[0, BODY_HEIGHT + 0.42, 0]}>
        <Text
          fontSize={0.34}
          color="#4A3A2E"
          anchorX="center"
          anchorY="middle"
          outlineWidth={0.02}
          outlineColor="#FFFBF3"
        >
          {agent.agentId}
        </Text>
      </Billboard>
    </group>
  );
}
