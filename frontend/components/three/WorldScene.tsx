'use client';

import { Bounds, OrbitControls } from '@react-three/drei';
import { Canvas } from '@react-three/fiber';
import type { ReactNode } from 'react';
import type { WorldFrame } from '@/lib/frame';
import { VENUES } from '@/lib/town';
import { GROUND } from '@/lib/world3d';
import AgentPawn from '@/components/three/AgentPawn';
import FirstPersonControls from '@/components/three/FirstPersonControls';
import VenueBlock from '@/components/three/VenueBlock';
import { EYE_HEIGHT } from '@/lib/firstPerson';

/**
 * The 3-D stage: ground, lights, venues, camera.
 *
 * A playback renderer and nothing more -- it holds no game logic and reads only
 * what a trace already carries. That is what lets it lag the backend without
 * blocking anything.
 */
export type ViewMode = 'overview' | 'walk';

export default function WorldScene({
  frame,
  mode = 'overview',
  selectedId,
  onSelect,
  onLockChange,
  children,
}: {
  frame?: WorldFrame | null;
  mode?: ViewMode;
  selectedId?: string | null;
  onSelect?: (agentId: string) => void;
  onLockChange?: (locked: boolean) => void;
  children?: ReactNode;
}) {
  const walking = mode === 'walk';

  return (
    <Canvas
      shadows
      camera={
        walking
          ? { position: [0, EYE_HEIGHT, 22], fov: 70, near: 0.1, far: 400 }
          : { position: [0, 34, 40], fov: 42 }
      }
      // The viewer paints its own background; without this the canvas is
      // transparent and the page shows through the world.
      onCreated={({ gl }) => gl.setClearColor('#FFF4E3')}
    >
      {/* At eye height the ground runs to a hard edge against the clear colour.
          Fog hides the seam and gives the plaza some depth; overview looks down
          on it from outside, where fog would only wash the town out. */}
      {walking && <fog attach="fog" args={['#FFF4E3', 26, 95]} />}

      <hemisphereLight args={['#FFF4E3', '#E8C9A0', 1.05]} />
      <directionalLight
        position={[18, 30, 14]}
        intensity={1.5}
        castShadow
        shadow-mapSize={[1024, 1024]}
      />

      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[GROUND * 2.4, GROUND * 2.4]} />
        <meshStandardMaterial color="#FFE9CE" roughness={1} />
      </mesh>

      {/* Fit the camera to the town instead of hardcoding a position. A fixed
          camera assumes a wide canvas, and this one is often taller than it is
          wide -- which silently clips the outer venues off both edges. `observe`
          refits on resize so that cannot come back. */}
      {/* Bounds re-aims the camera to frame its children, which is exactly
          wrong when the camera is a person's head. Only the overview fits. */}
      {walking ? (
        VENUES.map((venue) => <VenueBlock key={venue.id} venue={venue} />)
      ) : (
        <Bounds fit clip observe margin={1.25}>
          {VENUES.map((venue) => (
            <VenueBlock key={venue.id} venue={venue} />
          ))}
        </Bounds>
      )}

      {/* Outside the Bounds on purpose. Bounds refits whenever its children
          change, so an agent walking in would re-aim the camera on every turn.
          The venues are fixed, so fitting to them alone is stable. */}
      {frame?.agents.map((agent) => (
        <AgentPawn
          key={agent.agentId}
          agent={agent}
          selected={agent.agentId === selectedId}
          // Not while walking: the click that grabs the pointer would also
          // pick whoever happens to be under the crosshair. On foot you
          // choose someone by walking up to them.
          onSelect={walking ? undefined : onSelect}
        />
      ))}

      {children}

      {walking ? (
        <FirstPersonControls onLockChange={onLockChange} />
      ) : (
        <OrbitControls
          makeDefault
          enablePan
          minDistance={12}
          maxDistance={90}
          // Stop just above the horizon: below it the ground plane fills the view
          // and the world reads as a flat wall.
          maxPolarAngle={Math.PI / 2.15}
          target={[0, 0, 0]}
        />
      )}
    </Canvas>
  );
}
