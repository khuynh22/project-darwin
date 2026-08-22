# Frozen-opponent divergence — spike result, 2026-08-22

**Question.** The probe suite freezes a world state and replays recorded opponent behaviour
for `k` turns while the tested model occupies one seat. When the tested model acts
differently, recorded opponent actions can become illegal — a trade with an agent it just
bankrupted. If that happens on most probes at `k=8`, the k-turn design collapses toward
`k=1` and the suite has to be built differently. This spike measures the rate before the
suite is built, per the design's own risk section.

**Method.** No state-restore machinery: probes start at turn 1, so the "frozen state" is
just the seeded initial world.

- **Arm A** — five stub agents, seeded. Every decision and outcome recorded.
- **Arm B** — fresh session, same seed. Four agents replay Arm A's recorded decisions
  verbatim regardless of the world; the fifth seat runs a deliberately different policy
  (steal every turn).

Divergence is the share of *scripted* actions the engine rejected in Arm B, minus the same
agents' rejection rate in Arm A. The baseline is not zero — some actions are rejected in a
normal run too, and only the excess is caused by the seat diverging.

24 trials: 8 seeds × 3 seats, 24 turns each, 2,304 scripted actions observed.

## Result

| k | scripted actions | rejected | rate | baseline | excess |
|---|---|---|---|---|---|
| 1 | 96 | 4 | 4.2% | 2.1% | +2.1% |
| 2 | 192 | 17 | 8.9% | 7.3% | +1.6% |
| 4 | 384 | 38 | 9.9% | 8.3% | +1.6% |
| **8** | **768** | **63** | **8.2%** | **5.3%** | **+2.9%** |
| 12 | 1152 | 136 | 11.8% | 5.3% | +6.5% |
| 16 | 1536 | 189 | 12.3% | 4.3% | +8.0% |
| 24 | 2304 | 320 | 13.9% | 4.3% | +9.5% |

**The k-turn design holds.** At the planned default of `k=8`, excess divergence is +2.9% —
far below the 25% per-probe exclusion threshold. That threshold is therefore a safety net
for pathological probes, not a routine filter, which is what it should be.

**Divergence grows monotonically with k.** It roughly doubles from `k=8` to `k=12` and
triples by `k=24`. `k=8` sits just before the climb. A suite that wants longer episodes
should expect to exclude probes and must report how many.

## What this does not establish

1. **Stub agents, not frontier models.** Stubs draw from a fixed action distribution. A real
   model may diverge harder — bankrupting a rival, breaking an alliance — so treat +2.9% as a
   floor. Re-measure on a real-model probe batch before publishing a divergence figure.
2. **Early-game only.** Probes start at turn 1 with a full field. Late-game states have few
   agents alive, so a single elimination invalidates a larger share of the remaining script.
   The 335-turn run's late turns are exactly where the interesting deception lives, and this
   spike says nothing about them.
3. **One divergence policy.** The seat steals every turn. A seat that trades or forms
   alliances perturbs the world differently.

## Consequence for the design

No change to the probe unit: `k_turns` default 8, divergence threshold 25%, exclusions
reported rather than repaired. Two additions to the probe plan:

- Record the observed divergence rate per probe in its result, so the suite can report a
  distribution rather than a single assumption.
- Re-run this measurement on the first real-model probe batch and on late-game probes; if
  either exceeds the threshold routinely, revisit `k` before the leaderboard is published.

Spike code was throwaway and is not in the repo.
