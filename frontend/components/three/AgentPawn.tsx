'use client';

import { Billboard, Text } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useRef, type MutableRefObject } from 'react';
import type { Group } from 'three';
import AgentBody, { type Gait } from '@/components/three/AgentBody';
import type { FrameAgent } from '@/lib/frame';
import { BODY, advancePhase } from '@/lib/gait';
import { easeInOutCubic, facingAngle, lerp3, walkDuration } from '@/lib/motion';
import type { Vec3 } from '@/lib/world3d';

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);

/** Room for the body, for the selection ring and the label above it. */
const SELECT_RADIUS = 0.34;

/**
 * One agent, walking to wherever the world put it.
 *
 * Two sources of timing, and which one applies is a property of the frame.
 *
 * A frame carrying a real walk window (`arrivesAt > departsAt`) is animated on
 * **simulation time**: the agent leaves when it left and arrives when it
 * arrived, because the backend charged that journey against the clock and the
 * economy accrued while it happened. Rendering it at some other speed would
 * show a walk the world did not take.
 *
 * A live snapshot carries no clock, so the walk falls back to a render-side
 * duration. That remains a rendering choice and carries no claim about the
 * world -- the agent is at the recorded position whenever the move is settled.
 */
export default function AgentPawn({
  agent,
  selected = false,
  onSelect,
  tick,
}: {
  agent: FrameAgent;
  selected?: boolean;
  onSelect?: (agentId: string) => void;
  /** Current simulation tick. A ref, so scrubbing does not re-render the scene. */
  tick?: MutableRefObject<number>;
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

  // Written every frame and read by AgentBody, which is why it is a ref and
  // not a prop: ten agents re-rendering per frame is a slideshow.
  const gait = useRef<Gait>({ phase: 0, walking: false });

  useFrame((_, rawDelta) => {
    const node = group.current;
    if (!node) return;

    const state = walk.current;
    const onClock = tick !== undefined && agent.arrivesAt > agent.departsAt;

    let from: Vec3;
    let to: Vec3;
    let progress: number;

    if (onClock) {
      // Straight off the clock: no per-frame state, so scrubbing backwards and
      // jumping around land on exactly the position that tick describes.
      from = agent.from;
      to = agent.position;
      progress = clamp01(
        (tick.current - agent.departsAt) / (agent.arrivesAt - agent.departsAt),
      );
    } else {
      // A new position landed: walk from wherever the body actually is, not from
      // where the last frame nominally put it, or a fast scrub teleports.
      if (state.to !== agent.position) {
        const current: Vec3 = [node.position.x, 0, node.position.z];
        state.from = current;
        state.to = agent.position;
        state.elapsed = 0;
        state.duration = walkDuration(current, agent.position);
      }
      const delta = Math.min(rawDelta, 0.05);
      state.elapsed = Math.min(state.elapsed + delta, state.duration);
      from = state.from;
      to = state.to;
      progress = state.duration === 0 ? 1 : state.elapsed / state.duration;
    }

    // Eased rather than linear, which keeps the endpoints and the duration the
    // clock dictates while losing the robotic constant-speed start and stop.
    const eased = easeInOutCubic(progress);
    const [x, , z] = lerp3(from, to, eased);
    const walking = progress > 0 && progress < 1;

    // The gait is driven by ground actually covered this frame, so the legs
    // keep up with the body whatever the walk's duration works out to be.
    const stepped = Math.hypot(x - node.position.x, z - node.position.z);
    gait.current.phase = advancePhase(gait.current.phase, walking ? stepped : 0);
    gait.current.walking = walking;

    node.position.set(x, 0, z);

    if (walking) {
      state.facing = facingAngle(from, to, state.facing);
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
      <AgentBody color={agent.color} gait={gait} />

      {/* A hit target the raycaster can actually hit: picking a stick figure
          limb by limb misses between the arms and the body. */}
      <mesh position={[0, BODY.height / 2, 0]} visible={false}>
        <capsuleGeometry args={[SELECT_RADIUS, BODY.height - SELECT_RADIUS * 2, 4, 8]} />
      </mesh>

      {selected && (
        <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[SELECT_RADIUS + 0.18, SELECT_RADIUS + 0.34, 24]} />
          <meshBasicMaterial color="#E8956A" />
        </mesh>
      )}

      {/* Billboarded explicitly: the group turns to face where the agent is
          walking, and a name that turns away with it is useless. */}
      <Billboard position={[0, BODY.height + 0.32, 0]}>
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
