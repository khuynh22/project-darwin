'use client';

import { Text } from '@react-three/drei';
import type { FrameAgent } from '@/lib/frame';

const BODY_RADIUS = 0.62;
const BODY_HEIGHT = 1.15;

/** One agent as a rounded pawn in its colour, with its id floating above. */
export default function AgentPawn({
  agent,
  selected = false,
  onSelect,
}: {
  agent: FrameAgent;
  selected?: boolean;
  onSelect?: (agentId: string) => void;
}) {
  const [x, , z] = agent.position;

  return (
    <group
      position={[x, 0, z]}
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

      {selected && (
        <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[BODY_RADIUS + 0.25, BODY_RADIUS + 0.5, 24]} />
          <meshBasicMaterial color="#E8956A" />
        </mesh>
      )}

      {/* Billboarded, like the venue labels: the orbit control exists so the
          camera can sit at odd angles, and a name that turns away is useless. */}
      <Text
        position={[0, BODY_HEIGHT + 0.55, 0]}
        fontSize={0.5}
        color="#4A3A2E"
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.035}
        outlineColor="#FFFBF3"
      >
        {agent.agentId}
      </Text>
    </group>
  );
}
