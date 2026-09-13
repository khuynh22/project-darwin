/**
 * Simulation time, mirroring `backend/app/oracle/clock.py`.
 *
 * The two must agree on what a beat is worth: the backend records ticks and the
 * renderer animates on them, so a mismatch would show walks at the wrong speed
 * while every number in the trace still looked correct.
 */

/** Ticks per beat. A beat is what the old turn loop called a turn. */
export const BEAT = 1000;

export const toBeats = (ticks: number): number => ticks / BEAT;
export const beats = (n: number): number => Math.round(n * BEAT);
