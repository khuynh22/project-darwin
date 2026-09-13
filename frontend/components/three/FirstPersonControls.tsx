'use client';

import { PointerLockControls } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useMemo, useRef } from 'react';
import { Vector3 } from 'three';
import {
  EYE_HEIGHT,
  RUN_SPEED,
  STOPPED,
  WALK_SPEED,
  clampToWorld,
  resolveMove,
  smoothVelocity,
  step,
  venueBlockers,
  walkVelocity,
  type Keys,
  type Velocity,
} from '@/lib/firstPerson';

const KEY_MAP: Record<string, keyof Keys> = {
  KeyW: 'forward',
  ArrowUp: 'forward',
  KeyS: 'back',
  ArrowDown: 'back',
  KeyA: 'left',
  ArrowLeft: 'left',
  KeyD: 'right',
  ArrowRight: 'right',
};

/**
 * Where you are standing when you arrive.
 *
 * Offset east of centre on purpose: the Casino sits at (0, 9) and due north of
 * the middle of the south edge is its back wall, so spawning at x=0 has you
 * walk face-first into a building. From here the gap between the Casino and
 * the Bank is open and the town reads as somewhere you can enter.
 */
export const SPAWN: [number, number] = [10, 19];

/**
 * You, standing in the town.
 *
 * Pointer lock for looking, WASD for walking, shift to run. Velocity ramps in
 * and coasts out rather than switching on and off, because an instant start and
 * a dead stop are what make keyboard movement feel jerky however high the frame
 * rate is. The camera never leaves eye height — there is no flying, because the
 * point is to be a person down among the agents rather than a drone above them.
 *
 * Movement decisions live in `lib/firstPerson.ts`; this owns only the camera,
 * the clock and the keyboard.
 */
export default function FirstPersonControls({
  onLockChange,
}: {
  onLockChange?: (locked: boolean) => void;
}) {
  const camera = useThree((state) => state.camera);
  const keys = useRef<Keys>({ forward: false, back: false, left: false, right: false });
  const running = useRef(false);
  // Reused across frames: a fresh Vector3 every frame is how a smooth walk
  // turns into a stutter once the garbage collector notices.
  const facing = useRef(new Vector3());
  // Carried between frames so a key press ramps up and a release coasts down.
  const velocity = useRef<Velocity>(STOPPED);
  const blockers = useMemo(() => venueBlockers(), []);

  useEffect(() => {
    const [x, z] = SPAWN;
    camera.position.set(x, EYE_HEIGHT, z);
    camera.lookAt(0, EYE_HEIGHT, 0);
  }, [camera]);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      const key = KEY_MAP[e.code];
      if (key) {
        keys.current[key] = true;
        // Arrow keys scroll the page underneath the canvas otherwise.
        e.preventDefault();
      }
      if (e.code === 'ShiftLeft' || e.code === 'ShiftRight') running.current = true;
    };
    const up = (e: KeyboardEvent) => {
      const key = KEY_MAP[e.code];
      if (key) keys.current[key] = false;
      if (e.code === 'ShiftLeft' || e.code === 'ShiftRight') running.current = false;
    };
    // Releasing a key while the tab is hidden never fires, and you come back
    // walking into a wall forever.
    const clear = () => {
      keys.current = { forward: false, back: false, left: false, right: false };
      running.current = false;
      // Coasting into a hidden tab and back would resume mid-stride.
      velocity.current = STOPPED;
    };

    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    window.addEventListener('blur', clear);
    return () => {
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
      window.removeEventListener('blur', clear);
    };
  }, []);

  useFrame((_, rawDelta) => {
    // A backgrounded tab resumes with a huge delta and teleports you across
    // the plaza; one frame at 20fps is as far as anyone may travel at once.
    const delta = Math.min(rawDelta, 0.05);

    const direction = camera.getWorldDirection(facing.current);
    const yaw = Math.atan2(-direction.x, -direction.z);
    const speed = running.current ? RUN_SPEED : WALK_SPEED;

    const target = walkVelocity(keys.current, yaw, speed);
    velocity.current = smoothVelocity(velocity.current, target, delta);
    const { dx, dz } = step(velocity.current, delta);
    // Checked after smoothing, not before, or the deceleration never runs and
    // releasing a key stops you dead.
    if (dx === 0 && dz === 0) return;

    const from = clampToWorld([camera.position.x, camera.position.z]);
    const [x, z] = resolveMove(from, [from[0] + dx, from[1] + dz], blockers);
    camera.position.set(x, EYE_HEIGHT, z);
  });

  return (
    <PointerLockControls
      onLock={() => onLockChange?.(true)}
      onUnlock={() => onLockChange?.(false)}
    />
  );
}

