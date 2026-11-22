# Related work

How three papers shape this project's design. Full discussion is in the W13 literature review.

## Greshake, Abdelnabi, et al. (2023): indirect prompt injection

Threat model for the **injected** variant. An attacker never talks to the model; they plant instructions in content the model retrieves, and the model cannot reliably tell data from instructions. Demonstrations only, with no success rates. The authors are pessimistic about prompt- and filter-based defenses.

- Used here: injections sit in attacker-controlled evidence fields (rule names, command lines, user agents) that the agent reaches only through tools. `injection.delivery` follows their delivery methods; `injection.intent` follows their impact taxonomy.
- Design consequence: C's "tool results are data" prompt line is the kind of defense they call fragile, so injection success above zero in C is an expected finding. The allowlist and approval gate are structural and stop harmful tool calls from executing regardless.

## Zhan, Liang, Ying, Kang (2024): InjecAgent

The measurement precedent: 1,054 cases and 30 agents, with success meaning the agent made the attacker's tool call. ReAct-prompted GPT-4 was vulnerable 24% of the time (abstract); a hacking prompt added to the injection raised the rate.

- Used here: the tool-call rule is one of the three injection checks in `triage/score.py`. This project adds the canary and the disposition flip, because in triage a changed conclusion is the realistic harm.
- Report the three checks separately as well as combined, so results compare with InjecAgent's tool-call-only rate.

## Tsegai, Kantchelian, Yao, Gao (2026): LLM-based alert triage (preprint)

Closest related work. Agents start from the alert alone and query a live SIEM (1,247 alerts, one attack scenario). Every standard approach missed at least 40.4% of attack-related alerts (abstract). Attack alerts were dismissed when searches came back empty. Injection is not tested.

- Used here: the **withheld** variant tests the empty-search failure directly. The report counts how often each config calls a withheld-evidence case benign (`predicted_disposition` in score rows).
- Report the missed-attack rate (false negatives on true_positive cases) alongside macro-F1, as they do.
- Their open-weight results varied widely by model, so results from one local model may not transfer. State this in the limitations.
- Their multi-agent design (AIDA) is future work: the instructor's guidance is to measure guardrails, not add agent capabilities.

## Gap this project addresses

None of the three measures injection, missing evidence and the usefulness cost of guardrails together in alert triage. Here a prompt-only baseline (A), a tool-using agent (B) and a guarded agent (C) run under complete, withheld and injected evidence, scored by fixed rules.

## Verification notes

What could be checked from this repo's research session (not a substitute for reading the papers):

- **Greshake et al.:** arXiv:2302.12173 lists Greshake first. Confirm the author order and pages (79–90) of the AISec '23 version on the ACM page before citing it as "Abdelnabi, Greshake, et al."
- **InjecAgent:** only the abstract was verified (24% base rate, 1,054 cases, 30 agents). The 23.6% and 47.0% figures, the fine-tuning result and the limitations list come from the paper body and were not checked here. DOI: 10.18653/v1/2024.findings-acl.624.
- **Tsegai et al.:** the abstract and method were verified. Cost per alert, tool calls and latency, the tuning split, the open-weight F1 range and the cross-scenario miss came from a summary only. It is a preprint: mark it as such in the reference.
