'use client';

import { Billboard, Text } from '@react-three/drei';
import {
  DOOR,
  EAVES,
  STOREY,
  WALL,
  facadeExtent,
  facadeFor,
  hipConeRadius,
  windowGrid,
} from '@/lib/architecture';
import type { Venue } from '@/lib/town';
import { venuePosition } from '@/lib/world3d';

const TRIM = '#8A7059';
const GLASS = '#CFE3F5';
const DOOR_COLOR = '#6B5544';
const STONE = '#D9CDBC';

/** Just clear of the wall, so a pane never fights the wall for the same pixel. */
const RELIEF = 0.04;

function Roof({ kind, wallHeight, color }: { kind: string; wallHeight: number; color: string }) {
  const spread = WALL + EAVES * 2;

  if (kind === 'flat') {
    return (
      <group position={[0, wallHeight, 0]}>
        <mesh position={[0, 0.09, 0]} castShadow receiveShadow>
          <boxGeometry args={[spread, 0.18, spread]} />
          <meshStandardMaterial color={color} roughness={0.8} />
        </mesh>
        {/* A parapet, so a flat roof reads as a building and not a cut-off box. */}
        {[
          [0, spread / 2 - 0.07],
          [0, -(spread / 2 - 0.07)],
        ].map(([x, z], i) => (
          <mesh key={i} position={[x, 0.34, z]} castShadow>
            <boxGeometry args={[spread, 0.34, 0.14]} />
            <meshStandardMaterial color={TRIM} roughness={0.85} />
          </mesh>
        ))}
        {[
          [spread / 2 - 0.07, 0],
          [-(spread / 2 - 0.07), 0],
        ].map(([x, z], i) => (
          <mesh key={`s${i}`} position={[x, 0.34, z]} castShadow>
            <boxGeometry args={[0.14, 0.34, spread]} />
            <meshStandardMaterial color={TRIM} roughness={0.85} />
          </mesh>
        ))}
      </group>
    );
  }

  if (kind === 'hip') {
    return (
      // A four-sided pyramid: a cone with four radial segments, turned so its
      // faces line up with the walls rather than its corners.
      <mesh position={[0, wallHeight + 0.5, 0]} rotation={[0, Math.PI / 4, 0]} castShadow>
        <coneGeometry args={[hipConeRadius(spread), 1.0, 4]} />
        <meshStandardMaterial color={color} roughness={0.78} flatShading />
      </mesh>
    );
  }

  const pitch = Math.atan2(1.15, WALL / 2);
  const slope = Math.hypot(WALL / 2 + EAVES, 1.15);
  return (
    <group position={[0, wallHeight, 0]}>
      {[1, -1].map((side) => (
        <mesh
          key={side}
          position={[0, 0.5, (side * (WALL / 2 + EAVES)) / 2]}
          rotation={[side * pitch, 0, 0]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[spread, 0.14, slope]} />
          <meshStandardMaterial color={color} roughness={0.78} />
        </mesh>
      ))}
      {/* Gable ends, or you can see straight through the loft from the side. */}
      {[1, -1].map((side) => (
        <mesh key={`g${side}`} position={[(side * WALL) / 2, 0.575, 0]}>
          <boxGeometry args={[0.08, 1.15, WALL]} />
          <meshStandardMaterial color={TRIM} roughness={0.9} />
        </mesh>
      ))}
    </group>
  );
}

/** One venue as a building you can walk up to, read the sign on, and go round. */
export default function VenueBlock({ venue }: { venue: Venue }) {
  const [x, , z] = venuePosition(venue);
  const facade = facadeFor(venue.id);
  const { wallHeight, height } = facadeExtent(facade);
  const front = WALL / 2;

  // Turned so the door faces the middle of town: you approach a front, not a
  // random side wall.
  const facing = Math.atan2(-x, -z);

  return (
    <group position={[x, 0, z]} rotation={[0, facing, 0]}>
      <mesh position={[0, 0.09, 0]} receiveShadow>
        <boxGeometry args={[WALL + 0.5, 0.18, WALL + 0.5]} />
        <meshStandardMaterial color={STONE} roughness={1} />
      </mesh>

      <mesh position={[0, wallHeight / 2 + 0.18, 0]} castShadow receiveShadow>
        <boxGeometry args={[WALL, wallHeight, WALL]} />
        <meshStandardMaterial color={venue.body} roughness={0.88} />
      </mesh>

      {/* A band at each floor line: the cheapest thing that stops a wall
          reading as one flat slab from two metres away. */}
      {Array.from({ length: facade.storeys }, (_, i) => (
        <mesh key={i} position={[0, 0.18 + STOREY * (i + 1) - 0.09, 0]} castShadow>
          <boxGeometry args={[WALL + 0.09, 0.12, WALL + 0.09]} />
          <meshStandardMaterial color={TRIM} roughness={0.9} />
        </mesh>
      ))}

      <group position={[0, 0.18, front]}>
        <mesh position={[0, DOOR.height / 2, RELIEF]} castShadow>
          <boxGeometry args={[DOOR.width + 0.16, DOOR.height + 0.1, 0.08]} />
          <meshStandardMaterial color={TRIM} roughness={0.9} />
        </mesh>
        <mesh position={[0, DOOR.height / 2, RELIEF * 1.6]}>
          <boxGeometry args={[DOOR.width, DOOR.height, 0.06]} />
          <meshStandardMaterial color={DOOR_COLOR} roughness={0.7} />
        </mesh>
        <mesh position={[DOOR.width * 0.34, DOOR.height * 0.5, RELIEF * 2.4]}>
          <sphereGeometry args={[0.045, 8, 8]} />
          <meshStandardMaterial color="#E8C87A" roughness={0.35} metalness={0.6} />
        </mesh>

        {windowGrid(facade).map((w, i) => (
          <group key={i} position={[w.x, w.y, 0]}>
            <mesh position={[0, 0, RELIEF]} castShadow>
              <boxGeometry args={[w.width + 0.12, w.height + 0.12, 0.07]} />
              <meshStandardMaterial color={TRIM} roughness={0.9} />
            </mesh>
            <mesh position={[0, 0, RELIEF * 1.8]}>
              <boxGeometry args={[w.width, w.height, 0.05]} />
              <meshStandardMaterial
                color={GLASS}
                roughness={0.15}
                metalness={0.25}
                emissive={GLASS}
                emissiveIntensity={0.12}
              />
            </mesh>
            <mesh position={[0, 0, RELIEF * 2.4]}>
              <boxGeometry args={[0.035, w.height, 0.03]} />
              <meshStandardMaterial color={TRIM} roughness={0.9} />
            </mesh>
          </group>
        ))}

        {facade.awning && (
          <mesh position={[0, DOOR.height + 0.42, 0.34]} rotation={[-0.42, 0, 0]} castShadow>
            <boxGeometry args={[DOOR.width + 1.5, 0.08, 0.85]} />
            <meshStandardMaterial color={venue.roof} roughness={0.75} />
          </mesh>
        )}

        {facade.columns &&
          [-1, 1].map((side) => (
            <mesh
              key={side}
              position={[side * (DOOR.width / 2 + 0.42), wallHeight / 2 - 0.18, 0.22]}
              castShadow
            >
              <cylinderGeometry args={[0.16, 0.18, wallHeight - 0.36, 10]} />
              <meshStandardMaterial color={STONE} roughness={0.95} />
            </mesh>
          ))}

        {/* The sign belongs on the building, where you read it by walking up. */}
        <group position={[0, wallHeight - 0.52, RELIEF * 2]}>
          <mesh castShadow>
            <boxGeometry args={[WALL * 0.72, 0.6, 0.09]} />
            <meshStandardMaterial color={venue.roof} roughness={0.8} />
          </mesh>
          <Text
            position={[0, 0, 0.06]}
            fontSize={0.34}
            color="#FFFBF3"
            anchorX="center"
            anchorY="middle"
            maxWidth={WALL * 0.66}
          >
            {venue.label}
          </Text>
        </group>

        {/* What the building is for, in the agent's own vocabulary: these are
            the ids it is offered when it stands here. */}
        {venue.actions.length > 0 && (
          <Text
            position={[0, wallHeight - 0.95, RELIEF * 2]}
            fontSize={0.15}
            color="#5B4A3C"
            anchorX="center"
            anchorY="middle"
            textAlign="center"
            maxWidth={WALL * 0.8}
          >
            {venue.actions.join('  ·  ')}
          </Text>
        )}
      </group>

      <Roof kind={facade.roof} wallHeight={wallHeight + 0.18} color={venue.roof} />

      {facade.chimney && (
        <mesh position={[WALL * 0.28, wallHeight + 1.16, -WALL * 0.2]} castShadow>
          <boxGeometry args={[0.42, 1.1, 0.42]} />
          <meshStandardMaterial color={TRIM} roughness={0.95} />
        </mesh>
      )}

      {/* Wayfinding from anywhere in town, unlike the sign on the front. */}
      <Billboard position={[0, height + 0.95, 0]}>
        <Text
          fontSize={0.62}
          color="#4A3A2E"
          anchorX="center"
          anchorY="middle"
          outlineWidth={0.03}
          outlineColor="#FFFBF3"
        >
          {venue.label}
        </Text>
      </Billboard>
    </group>
  );
}
