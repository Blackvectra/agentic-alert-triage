# Spec: test and lookup guardrails (from the C2 retro)

Status: ready to build. Seams agreed with the user.

## Problem Statement

While building C2's report section, three avoidable slips cost time or accuracy:

- Report tests failed three times with `KeyError`s because the test helpers build scored rows by hand, and those hand copies had drifted from what scoring really writes. Nothing checks that they match, so the next drift could instead let a test pass while the real report crashes.
- The agent stated a case fact (PROC-003's expected disposition) from memory instead of reading the case file, and was wrong. Looking a case up takes several steps, so guessing is tempting.
- The project check installs and runs the tests but does no linting, so unused imports or shadowed names from quick edits go unnoticed.

## Solution

- A contract test ties the test helpers to the real scorer: if scoring adds, drops or renames a field, the test helpers fail loudly until they are updated.
- A small read-only command prints a case's expected answers and planted injections, with a one-line pointer in CLAUDE.md so agents use it instead of memory.
- The project check gains a lint step, so local runs and CI both catch lint errors.

## User Stories

1. As the project owner, I want test helpers to fail when they no longer match scored rows, so that report tests cannot pass on data the real pipeline never produces.
2. As the project owner, I want one shared helper for injection results in tests, so that a change to the injection fields is a one-place edit.
3. As an agent writing a report test, I want a helper that already has every scored field, so that I do not hit `KeyError`s for fields my test does not care about.
4. As an agent, I want the contract test's failure message to name the missing or extra keys, so that I can fix the helper without hunting.
5. As the project owner, I want the contract to come from the real scoring function, so that the test cannot agree with itself by construction.
6. As an agent answering a question about a case, I want one command that prints its expected disposition per variant, so that I state ground truth instead of guessing.
7. As an agent, I want that command to show which fields carry a planted injection, so that I can reason about injection results without opening JSON by hand.
8. As the project owner, I want the case command to be read-only, so that it can never change a case's expected answers (they are ground truth).
9. As an agent, I want a clear error for an unknown case id, so that a typo is not mistaken for "no such facts".
10. As a learner reading the code, I want the case command to be short and plain, so that I can follow it.
11. As the project owner, I want CLAUDE.md to point to the case command in one line, so that every agent finds it without extra context load.
12. As the project owner, I want linting in the same check that CI runs, so that local and CI results never disagree.
13. As an agent, I want lint failures reported as a failed check step, so that I fix them before committing, like a failing test.
14. As the project owner, I want the linter installed from the existing dev extra, so that the check still starts from a clean environment with one install line.
15. As the project owner, I want the first lint pass to fix existing findings in their own small commit, so that the lint step lands green.

## Implementation Decisions

- **Contract seam: the scoring function.** The contract test scores one minimal fake log against one real case through the public scoring function, then compares key sets: the general row helper's keys must equal the scored row's keys, and the new shared injection helper's keys must equal the scored injection result's keys. Values are not compared here; existing scoring tests cover values.
- **Shared injection helper.** Lives with the other test helpers; takes `success` (and optionally the other three flags, defaulting to false). Every hand-built injection dict in the report tests switches to it.
- **Case lookup command.** A new script under the scripts folder, standard library only, taking one case id. It prints, per variant, the expected disposition and any planted-injection fields. It only reads the fixture file; it never writes. An unknown id exits non-zero with a message naming the id.
- **CLAUDE.md pointer.** One line: case facts (expected answers, injections) come from the case command, never from memory.
- **Lint step.** The linter becomes the third step of the project check, after install and before or after tests (after install is required). It is added to the dev extra so the clean environment installs it. Default rule set; no project-wide config beyond what the first pass needs.
- **Not changed:** scoring rules, any case's expected answers, configs A/B/C/C2, the frozen results.

## Testing Decisions

- Good tests here check behaviour through public seams: the scorer's output shape, and the case command's printed output. They do not inspect helper internals.
- **Seam 1, contract test** (report tests module): scored row keys equal row helper keys; scored injection keys equal injection helper keys. Prior art: the existing report tests that build rows with the row helper, and the scoring tests that call the scoring function.
- **Seam 2, case command** (new test): run the command on a real case and assert each variant's expected disposition appears; run it on an unknown id and assert a non-zero exit. Prior art: tests that load real fixture files (the C2 check that the indicator list names no case ids).
- **Seam 3, project check** (existing, unchanged as a seam): no new test; a lint failure fails the check like a test failure.
- Work test-first, one seam per small commit, with the usual pause for review.

## Out of Scope

- A faster, reusing mode for the project check (retro item 4).
- Removing the duplicated "run the check before committing" line from CLAUDE.md (retro item 5).
- Strict lint rule sets or a formatter.
- Any change to scoring, cases, configs or results.
- The remaining C2 work (dev runs, freeze, held-out run).

## Further Notes

- Source: the retro run after commit f0e54bc on the working branch.
- No issue tracker is configured for this repo, so this spec lives as a file. Running the skills setup would let future specs go to a tracker.
