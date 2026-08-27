'use client';

import { Text } from '@react-three/drei';
import type { Venue } from '@/lib/town';
import { venuePosition } from '@/lib/world3d';

const HEIGHT = 1.6;
const SIZE = 5.2;

/** One venue as a raised district: a plinth, a roof slab, and a floating label. */
export default function VenueBlock({ venue }: { venue: Venue }) {
  const [x, , z] = venuePosition(venue);

  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, HEIGHT / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[SIZE, HEIGHT, SIZE]} />
        <meshStandardMaterial color={venue.body} roughness={0.85} />
      </mesh>

      <mesh position={[0, HEIGHT + 0.35, 0]} castShadow>
        <boxGeometry args={[SIZE + 0.5, 0.7, SIZE + 0.5]} />
        <meshStandardMaterial color={venue.roof} roughness={0.7} />
      </mesh>

      {/* Billboarded so the label stays readable from any camera angle -- the
          whole point of the orbit control is looking from odd angles. */}
      <Text
        position={[0, HEIGHT + 1.5, 0]}
        fontSize={0.85}
        color="#4A3A2E"
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.045}
        outlineColor="#FFFBF3"
      >
        {venue.label}
      </Text>
    </group>
  );
}
