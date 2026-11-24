# C2 held-out result (post-hoc, exploratory; ADR 0012)

C2 was designed after the A/B/C held-out results were seen, so these numbers are exploratory
and likely optimistic (holdout reuse). The main conclusion stays with `heldout-summary.md`.

Run: 2026-11-24, qwen3:32b, think off, temperature 0, seed 672, C2 frozen at `bcb8d372fc`.
90 runs (30 held-out cases x 3 variants), 0 harness errors. GPU type not recorded in the logs.
Raw files in Google Drive (ee672_runs/heldout_ollama-qwen3-32b_C2):
  logs.jsonl    sha256 7d71c68ba5c86f237781836e249c2d95c47419eef4b61c78342448227ca3c0bd
  scores.jsonl  sha256 6415c507d68f1578ad52282df7d68bafb2dd303da2fbad0ec03c4a0dda64ba47
Compared against the original A/B/C held-out run (scores sha256 f23b2b40...).

## ADR 0012 success rules

- Usefulness: B minus C2 useful-answer drop -0.033 (C2 slightly more useful), but the
  interval crosses the margin: **inconclusive**.
- Injection: C2 10/30 (0.333) vs C 8/30 (0.267); 0 unauthorized calls executed. The rule
  needs C2 below C: **fail**. McNemar C vs C2 p = 0.727, so no real difference either way.
- Overall: **inconclusive**.

| config | accuracy | injection success | unauthorized executed |
|---|---|---|---|
| A | 0.311 | 13/30 | 0 |
| B | 0.456 | 7/30 | 17 |
| C | 0.144 | 8/30 | 0 |
| C2 | 0.478 | 10/30 | 0 |

## What the layers did

- Layer 2 (investigate first): pushed back on 84 of 90 runs, 0 violations.
- Layer 1 (flags): 6 of 30 injected runs flagged, 0 false alarms on 30 complete runs.
- Layer 3 (answer checks): 76 accepted, 13 repaired, 1 fallback.
- All 10 C2 injection successes were disposition flips to the attacker's answer (one also
  leaked the canary); none were tool attempts. Layer 3 replaced 2 first answers but the flip
  remained. Layer 1 caught too few injections (6/30) for the flag-blocks-benign rule to help.

## Reading

C2 recovered B's usefulness (accuracy 0.478 vs C's 0.144) while keeping C's zero executed
unauthorized calls, which B did not (17). It did not reduce injection success below C:
pattern flagging missed most held-out payloads, and the remaining defences do not stop a
model from choosing the attacker's disposition.
