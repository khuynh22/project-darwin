'use client';

import { useFrame } from '@react-three/fiber';
import { useRef, type MutableRefObject } from 'react';
import type { Group } from 'three';
import { BODY, bobHeight, limbAngle, type Limb } from '@/lib/gait';

/** Shared, mutable, and written by the pawn every frame — see AgentPawn. */
export type Gait = { phase: number; walking: boolean };

const SKIN = '#E8C4A0';
const HAIR = '#4A3A2E';
const SHOE = '#3A2E24';
const TROUSERS = '#5A4B3C';

const HIP_Y = BODY.legLength;
const SHOULDER_Y = HIP_Y + BODY.torsoHeight * 0.86;
const HEAD_Y = HIP_Y + BODY.torsoHeight + BODY.headRadius;

/** Fraction of an arm covered by a sleeve; the rest is forearm. */
const SLEEVE = 0.46;

/**
 * A limb hanging from its joint, so rotating the parent group swings it.
 *
 * Two segments, because a sleeve in the agent's colour roughly doubles how
 * much of that colour you can see. Identity here is colour, and after the
 * switch from a solid capsule to a person the shirt alone was a sliver you
 * could not pick out across the plaza.
 */
function Limb({
  length,
  radius,
  upper,
  lower,
  foot,
}: {
  length: number;
  radius: number;
  upper: string;
  lower: string;
  foot?: boolean;
}) {
  const upperLength = length * SLEEVE;
  const lowerLength = length - upperLength;
  return (
    <group>
      <mesh position={[0, -upperLength / 2, 0]} castShadow>
        <capsuleGeometry args={[radius, Math.max(0.01, upperLength - radius), 4, 8]} />
        <meshStandardMaterial color={upper} roughness={0.72} />
      </mesh>
      <mesh position={[0, -upperLength - lowerLength / 2, 0]} castShadow>
        <capsuleGeometry
          args={[radius * 0.92, Math.max(0.01, lowerLength - radius), 4, 8]}
        />
        <meshStandardMaterial color={lower} roughness={0.8} />
      </mesh>
      {foot && (
        <mesh position={[0, -length + radius * 0.4, radius * 0.9]} castShadow>
          <boxGeometry args={[radius * 2.1, radius * 1.2, radius * 3.4]} />
          <meshStandardMaterial color={SHOE} roughness={0.9} />
        </mesh>
      )}
    </group>
  );
}

/**
 * An agent as a person: head, torso, two arms, two legs, walking.
 *
 * The body faces **+Z**, deliberately against the three.js -Z convention: at
 * rest that puts the face toward the overview camera instead of the back of the
 * head. The toes, the forward lean and `motion.facingAngle` all follow it.
 *
 * Identity is still colour — the shirt carries it, because it is the largest
 * surface and the thing you can pick out across the plaza. Skin and hair are
 * shared, so the colour is never ambiguous.
 *
 * The pose is driven from a mutable ref rather than props: this changes every
 * frame, and a re-render per frame per agent turns ten agents into a slideshow.
 */
export default function AgentBody({
  color,
  gait,
}: {
  color: string;
  gait: MutableRefObject<Gait>;
}) {
  const joints = useRef<Partial<Record<Limb, Group | null>>>({});
  const body = useRef<Group>(null);

  useFrame(() => {
    const { phase, walking } = gait.current;

    for (const limb of ['leftLeg', 'rightLeg', 'leftArm', 'rightArm'] as Limb[]) {
      const joint = joints.current[limb];
      if (joint) joint.rotation.x = walking ? limbAngle(phase, limb) : 0;
    }

    if (body.current) {
      body.current.position.y = walking ? bobHeight(phase) : 0;
      // Leans into the walk. Upright while walking reads as gliding.
      body.current.rotation.x = walking ? 0.055 : 0;
    }
  });

  return (
    <group ref={body}>
      <group position={[0, HEAD_Y, 0]}>
        <mesh castShadow>
          <sphereGeometry args={[BODY.headRadius, 16, 16]} />
          <meshStandardMaterial color={SKIN} roughness={0.85} />
        </mesh>
        {/* Hair as a cap, offset back (-Z), so the face reads as the front even
            from behind — which is where you see an agent walking away. */}
        <mesh position={[0, BODY.headRadius * 0.28, -BODY.headRadius * 0.12]} castShadow>
          <sphereGeometry args={[BODY.headRadius * 1.03, 16, 16, 0, Math.PI * 2, 0, 1.15]} />
          <meshStandardMaterial color={HAIR} roughness={0.95} />
        </mesh>
        {[-1, 1].map((side) => (
          <mesh
            key={side}
            position={[
              side * BODY.headRadius * 0.36,
              BODY.headRadius * 0.06,
              BODY.headRadius * 0.88,
            ]}
          >
            <sphereGeometry args={[BODY.headRadius * 0.14, 8, 8]} />
            <meshStandardMaterial color="#2C2218" roughness={1} />
          </mesh>
        ))}
      </group>

      {/* Torso tapers to the waist, which is most of what makes a shape read as
          a person rather than a bollard. */}
      <mesh position={[0, HIP_Y + BODY.torsoHeight / 2, 0]} castShadow receiveShadow>
        <cylinderGeometry
          args={[BODY.torsoWidth * 0.72, BODY.torsoWidth * 0.54, BODY.torsoHeight, 14]}
        />
        <meshStandardMaterial color={color} roughness={0.7} />
      </mesh>

      <mesh position={[0, HIP_Y + 0.02, 0]} castShadow>
        <cylinderGeometry args={[BODY.hipWidth * 1.24, BODY.hipWidth * 1.1, 0.13, 12]} />
        <meshStandardMaterial color={TROUSERS} roughness={0.85} />
      </mesh>

      {[
        { limb: 'leftArm' as Limb, x: -BODY.shoulderWidth },
        { limb: 'rightArm' as Limb, x: BODY.shoulderWidth },
      ].map(({ limb, x }) => (
        <group
          key={limb}
          ref={(node) => {
            joints.current[limb] = node;
          }}
          position={[x, SHOULDER_Y, 0]}
        >
          <Limb
            length={BODY.armLength}
            radius={BODY.limbRadius * 0.86}
            upper={color}
            lower={SKIN}
          />
        </group>
      ))}

      {[
        { limb: 'leftLeg' as Limb, x: -BODY.hipWidth * 0.62 },
        { limb: 'rightLeg' as Limb, x: BODY.hipWidth * 0.62 },
      ].map(({ limb, x }) => (
        <group
          key={limb}
          ref={(node) => {
            joints.current[limb] = node;
          }}
          position={[x, HIP_Y, 0]}
        >
          <Limb
            length={BODY.legLength}
            radius={BODY.limbRadius}
            upper={TROUSERS}
            lower={TROUSERS}
            foot
          />
        </group>
      ))}
    </group>
  );
}
