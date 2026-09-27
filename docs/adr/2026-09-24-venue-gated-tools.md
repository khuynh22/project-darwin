# ADR 4: Venue-gated tools, behind a flag

- **Status:** accepted
- **Date:** 2026-09-24
- **Deciders:** repository owner (product intent), principal-engineer (design)

## Context

Twenty-five actions in every prompt is affordable; forty-five is not.
`2026-09-13-venue-affordances-design.md` decided that any action stays
callable from anywhere and the walk to reach it is the only gate, and solved
prompt size by describing the current venue in full and summarising every
other venue in one line. That decision holds at six built venues. The four
content packs planned in `2026-09-24-venue-content-packs-design.md` grow the
world toward twenty venues and roughly fifty actions, at which point "callable
from anywhere" means every wake still pays for the full catalogue regardless
of where the agent is standing.

## Decision

Add a per-session flag, `venue_gating`. Under it, a prompt offers only the
actions available at the agent's current venue plus a new `travel` action;
`travel` is a major action, so walking costs the same turn a major action
would. The ungated world is unchanged and stays the default, so it remains a
frozen comparison condition.

## Consequences

Location becomes a commitment: leaving the Market to reach the Alley is now
observable in the trace, so an alibi built on "I was never near the theft"
has teeth. Per-wake prompt cost stops growing with the size of the world.
Against that: an agent can waste a wake standing in the wrong building,
traces from the two modes are not comparable without conditioning on the
flag, and the frozen-stimulus probes need a second baseline before gated runs
can be scored against them.

**Gating has no effect on any running session, CLI run, probe, or sweep
today.** `run_events` is the only function that reads `venue_gating`, and it
is called from nowhere in production — `main.py`, `scripts/run_simulation.py`,
`probe/replay.py`, `replay/reexecute.py`, and `sweep/cell.py` all still call
the lockstep `run_turn`. The flag is stored per session, validated, and
recorded on the trace's `RunManifest`, but setting `venue_gating: true` does
not change how a simulation behaves until something wires `run_events` into
an entry point, which is a separate, larger piece of work this pack does not
attempt.

A stub-roster diversity check (`backend/tests/test_gating_diversity.py`)
guards against the collapse risk named below: on a 3-agent, 60-beat, seed-7
run, gating produced 41 events, 10 distinct actions, a 49% travel share, and
zero rejections — no threshold was close.

## Reopen if

Gated stub runs show a collapsed action distribution that `DEFAULT_BIAS`
cannot fix, or the rejection rate in live runs stays above a few percent,
which would mean the venue block is not conveying the situation clearly
enough for the agent to act on it.
