# Requirements

What this project must deliver. Check every change against this file. Wording under "Assignment" and "Instructor feedback" is quoted as the author provided it.

## Assignment

> Prototype a sandboxed AI assistant that summarizes synthetic security alerts and queries a small set of read-only lookup tools. Compare a prompt-only baseline with structured tool inputs, evidence-linked responses, explicit abstention, and human confirmation for proposed actions. Evaluate factual correctness, unsupported recommendations, inappropriate tool-use attempts, and per-alert processing cost. Keep all scenarios simulated and assess whether guardrails improve reliability without excessive loss of usefulness.

## Instructor feedback on the proposal

> I think the proposal has good experimental rigor and clearly defined security boundaries. Directions I would recommend moving forward:
> * Define objective criteria for supported claims, unauthorized tool-use attempts, successful prompt injections, and appropriate abstention. Validate references against actual tool outputs.
> * Build a basic end-to-end prototype by implementing one alert family across all three configurations before expanding the scenario set. Confirm that logging and automated scoring work correctly first.
> * Start with one execution of the 30 held-out cases across three conditions and configurations (270 evaluations). Treat repeated trials as optional.
>
> Prioritize measurable guardrail effectiveness over expanding agent capabilities - this is sufficient as a final project.

## Proposal commitments (summary)

From the approved semester proposal (EE 672, "Trustworthy Agentic AI for Security Alert Triage"):

- Three alert families: suspicious authentication, suspicious process execution, account or privilege changes.
- 12 development cases and 30 held-out cases (10 per family), authored by the student; no outside dataset. Expected disposition and required evidence written before any run; related scenarios stay in one split.
- Configs: A prompt-only, B tool-using, C guarded. B and C share tools and call budget. C adds validated tool inputs, evidence references, explicit abstention and human confirmation for proposed actions.
- Variants per held-out case: complete, withheld, injection-bearing, each with its own expected answer.
- One fixed tool-capable model, chosen on cost and tool-calling support. Prompts and fixtures frozen before testing.
- Reported: disposition accuracy, macro-F1, share of supported claims, unsupported recommendations, inappropriate tool-use attempts vs. calls executed, per-alert latency and cost, abstention rate alongside answer coverage.
- Stated limits: results describe these synthetic scenarios, not a real SIEM; C changes several things at once, so no single guardrail can be credited.

## Where each requirement is met

| Requirement | Where |
|---|---|
| Read-only tools, simulated scenarios | `triage/tools.py`, `triage/gate.py`, `fixtures/cases/` |
| A vs. B vs. C | `triage/agent.py` (`PROMPTS`, `run_case`) |
| Objective scoring rules | `triage/score.py`, README "Scoring rules" |
| Factual correctness | disposition accuracy, macro-F1, supported claims (`triage/report.py`) |
| Unsupported recommendations | ADR 0006, `score.py` |
| Inappropriate tool use | unauthorized attempts vs. executed |
| Per-alert cost | tokens and seconds per run; $0 with the local model (ADR 0004) |
| Usefulness loss | abstention 2x2 (`abstained_when_could_answer`) |
| One family end to end first | suspicious_auth AUTH-001..004 |
| Model choice | ADR 0004, ADR 0007 |
