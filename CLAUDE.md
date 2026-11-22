# Agentic Alert Triage

Read GLOSSARY.md for project terms and docs/adr/ before changing triage/.

- Read-only and simulated: tools never write; the approval gate never executes.
- Scoring rules (triage/score.py) and each case's expected answers are the user's ground truth: ask before changing them.
- B and C keep identical tools and call budget (ADR 0001).
- API keys come from environment variables only; never in code, logs or commits.
- The user is learning Python: before each change, say what and why in plain words; one small commit, then stop for review.
- Commits are authored by Blackvectra on purpose ("Unverified" on GitHub is expected); push only when the user asks.
