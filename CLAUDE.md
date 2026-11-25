# Agentic Alert Triage

Read docs/handoff.md first: it says where things stand and what is next.
Read GLOSSARY.md for project terms and docs/adr/ before changing triage/.
Check changes against docs/requirements.md (assignment, instructor feedback, proposal).
Run `python scripts/check.py` before committing; CI runs the same check.
After a PR merges (squash or merge commit), run `scripts/resync_after_merge.sh`; to finalize a draft case, `scripts/finalize_case.py`.

- Read-only and simulated: tools never write; the approval gate never executes.
- Scoring rules (triage/score.py) and each case's expected answers are the user's ground truth: ask before changing them.
- Case facts (expected answers, planted injections): read them with `python scripts/case.py <id>`, never from memory.
- B and C keep identical tools and call budget (ADR 0001).
- API keys come from environment variables only; never in code, logs or commits.
- The user is learning Python: before each change, say what and why in plain words; one small commit, then stop for review, unless the user asks for a batch (then keep commits small and review together at the end).
- Commits are authored by Blackvectra on purpose, with the session's signed committer so GitHub shows Verified (command in docs/handoff.md); never `--reset-author`; push each commit to the working branch once `check.py` passes; merge only when the user asks.
