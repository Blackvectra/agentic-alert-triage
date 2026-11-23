# Related work

How three papers shape this project's design, then how it compares with wider work. Full discussion is in the W13 literature review.

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

## Wider comparison

Added 2026-11-22. For each source below only the arXiv abstract page was read; paper bodies were not, so details beyond the abstracts are marked *(unverified)*. Tsegai et al. and InjecAgent are covered above.

### 1. SOC triage and incident investigation benchmarks

#### ExCyTIn-Bench (Microsoft)
- Link: https://arxiv.org/abs/2507.14201 (Wu, Velazco, et al., 2025)
- Measures: whether an LLM agent can investigate cyber threats. It answers questions that need multi-hop reasoning across security logs.
- Method: a controlled Azure tenant whose Microsoft Sentinel logs sit in 57 SQL tables. 7,542 questions are generated from investigation graphs, so each has an automatic, explainable ground-truth answer. Results are reported as a "reward" (best model 0.606). The reward formula and the split details are *(unverified)*.
- Compared with this repo: much larger and built from realistic attack logs, with automatic ground truth. It measures investigation skill (can the agent find the answer?), not trustworthiness under missing evidence or injection, and it has no abstention or citation scoring. This repo's 42 cases are hand-written and far smaller, but every case is scored on several trust properties.

#### CyberSOCEval (Meta and CrowdStrike, part of CyberSecEval 4)
- Link: https://arxiv.org/abs/2509.20166 (Deason, Bali, Bejean, et al., 2025); code ships with Meta's PurpleLlama/CyberSecEval
- Measures: LLM knowledge and reasoning on malware analysis (from sandbox detonation reports) and threat-intelligence reports.
- Method: question answering over real security artifacts, with accuracy-style scoring. Finding: larger models do better, and test-time "reasoning" helps less than it does in coding and math. The exact item counts are *(unverified)*.
- Compared with this repo: it tests a model, not an agent. There are no tools, no abstention and no injection. It is useful as evidence that SOC reasoning is still unsolved, not as a design template.

#### Not found or not verified
- "SecBench" (the name in the task) is used by several unrelated security QA datasets. None of them, as far as I could check, is an agentic triage benchmark, so none is included here.
- No mature open-source "LLM triage agent" with a published evaluation was verified in this session. Vendor agents (for example Microsoft Security Copilot) publish no reproducible benchmark.

### 2. Prompt-injection evaluation for agents

#### AgentDojo
- Link: https://arxiv.org/abs/2406.13352, code at https://github.com/ethz-spylab/agentdojo (Debenedetti, ..., Tramèr; NeurIPS 2024 Datasets and Benchmarks track; the venue is *(unverified)*, the arXiv page lists a preprint)
- Measures: whether tool-using agents still finish user tasks when tool outputs contain injections, and whether the attacker's goal succeeds.
- Method: 97 user tasks and 629 security test cases in simulated environments (workspace, banking, travel, Slack). Tasks and attacks are checked by code against the environment state, with no LLM judge. Commonly reported metrics are benign utility, utility under attack and targeted attack success rate *(definitions not read from the paper here)*.
- Compared with this repo: the same philosophy (simulated tools, deterministic scoring, utility measured next to security). AgentDojo is larger, and its environment is stateful so attacks can cause real (simulated) side effects. This repo's injection checks (canary, disposition flip, attacker tool attempt) fit triage, where the realistic harm is a changed conclusion, not a sent email.

#### Agent Security Bench (ASB)
- Link: https://arxiv.org/abs/2410.02644 (Zhang et al., ICLR 2025)
- Measures: attacks and defenses on agents across 10 scenarios, 10 agents and more than 400 tools: 10 injection attacks, memory poisoning, a backdoor, 4 mixed attacks and 11 defenses, run on 13 LLM backbones, with 7 metrics including one for the utility-security balance.
- Compared with this repo: much broader, comparing many attacks and many defenses. This repo compares one defense bundle (config C) against no defense (B) in one domain, which is narrower but easier to interpret.

### 3. Abstention and grounded citations

#### Know Your Limits: a survey of abstention in LLMs
- Link: https://arxiv.org/abs/2407.18418 (Wen et al., TACL 2024)
- Content: frames abstention from three angles (the query, the model, human values) and reviews abstention methods, benchmarks and metrics.
- Compared with this repo: the `withheld` variant is a query-side case. The question cannot be answered from the available evidence, so abstaining is correct. The 2x2 `abstain_cell` (correct abstain, answered when it should abstain, over-abstained, answered) follows the survey's point that both missed and excessive abstention matter. The survey's exact metric names were not checked.

#### ALCE: Enabling LLMs to generate text with citations
- Link: https://arxiv.org/abs/2305.14627 (Gao, Yen, Yu, Chen, EMNLP 2023)
- Measures: fluency, correctness and citation quality. Citation quality is judged automatically with an NLI model and correlates strongly with human judgment. Even the best models lacked full citation support about half the time on ELI5.
- Compared with this repo: ALCE checks whether a cited passage *entails* the claim. This repo checks only whether the cited evidence ID was *actually retrieved* in the run (`supported_claim_rate`, `fabricated_citations`). That rule is stricter about fabrication and fully deterministic, but weaker on faithfulness: a real, retrieved ID cited for a false claim still counts as supported.

### 4. Guardrails and approval gates

#### CaMeL: Defeating prompt injections by design
- Link: https://arxiv.org/abs/2503.18813 (Debenedetti, Shumailov, ..., Tramèr, 2025, Google DeepMind/ETH)
- Design: a system layer around the LLM that separates control flow (from the trusted user query) from data flow (untrusted tool output) and enforces capability-based policies at tool-call time. On AgentDojo it solved 77% of tasks with provable security, against 84% undefended.
- Compared with this repo: CaMeL and this repo share the idea that security must be structural, not a prompt line. Config C's allowlist and approval gate are structural for *actions*. C's conclusions (the disposition) still come straight from an LLM that reads untrusted text, which is the gap CaMeL closes. CaMeL also reports its utility cost (84 to 77), which is the same trade-off this repo measures as `abstained_when_could_answer`.

### What this project does well (with evidence)

1. **Deterministic scoring with no LLM judge.** `triage/score.py` uses only set logic over logged tool calls. AgentDojo also scores by code checks (2406.13352). It is reproducible, and the scoring rules were fixed before any run.
2. **Utility measured next to security.** Abstention cells and disposition accuracy sit beside injection success. AgentDojo, ASB and CaMeL all argue that a defense must report its utility cost (2406.13352, 2410.02644, 2503.18813).
3. **Missing evidence as its own test condition.** The `withheld` variant targets the failure Tsegai et al. observed (attack alerts dismissed after empty searches). ExCyTIn-Bench and CyberSOCEval do not test this.
4. **An injection-success rule that fits the domain.** The canary and disposition-flip checks extend InjecAgent's tool-call-only rule to the harm that matters in triage. Reporting the three checks separately keeps results comparable with InjecAgent.
5. **Fabricated citations are caught by construction.** Checking citations against IDs retrieved in the run is stricter than ALCE-style entailment checks on fabrication (2305.14627).
6. **Experimental hygiene.** A dev/held-out split with scenario groups kept apart, freezing before held-out, choosing the model in advance and separating harness errors from model errors are not described in most benchmark abstracts read here *(their papers may still do this; not checked)*.
7. **B and C get identical tools and budget (ADR 0001).** Any difference between them comes from the guardrails, not from extra capability.

### Gaps or ideas worth considering

1. **Scale and statistics.** 30 held-out cases x 3 variants is small next to ExCyTIn-Bench's 7,542 questions or AgentDojo's 629 security cases. Report confidence intervals (for example a bootstrap over cases) and a paired test between B and C on the same cases. No source here was checked for its testing method, but with roughly 30 cases per cell the intervals will be wide and should be shown.
2. **Synthetic, hand-written data.** ExCyTIn-Bench and Tsegai et al. use realistic logs. State in the limitations that hand-written cases may be easier or cleaner than real alerts.
3. **One model.** ASB uses 13 backbones and Tsegai et al. report wide variation between open-weight models. Results from qwen3:32b alone may not transfer; a second model, even only on dev, would show how much.
4. **Citation faithfulness.** As noted under ALCE, a retrieved but irrelevant ID counts as support. A cheap extra check: compare cited IDs with the case's `required_evidence`, or flag claims whose IDs come from unrelated evidence. Evidence recall already covers part of this.
5. **Disposition is not structurally protected.** CaMeL shows control/data separation can protect what the agent decides, not only what it executes. This is out of scope (the instructor asked to measure guardrails, not build new ones), but worth a sentence in future work.
6. **Adaptive attacks.** AgentDojo and ASB use several attack templates. With a few fixed injections per case, a low success rate in C is a lower bound on real-world risk. Say so.
7. **Abstention vocabulary.** Using the survey's terms (2407.18418) when describing the abstention cells would make the report easier to place in the literature.

### Not verified in this session
- Paper bodies of all the sources above. Only arXiv abstract pages were read, plus a search result for CyberSOCEval.
- AgentDojo's exact metric names and definitions and its NeurIPS venue; ExCyTIn-Bench's reward formula and splits; CyberSOCEval's item counts.
- Whether these benchmarks use statistical tests or frozen held-out splits.
- Any benchmark named "SecBench" that evaluates agentic triage.

## Gap this project addresses

None of the three measures injection, missing evidence and the usefulness cost of guardrails together in alert triage. Here a prompt-only baseline (A), a tool-using agent (B) and a guarded agent (C) run under complete, withheld and injected evidence, scored by fixed rules.

## Verification notes

What could be checked from this repo's research session (not a substitute for reading the papers):

- **Greshake et al.:** arXiv:2302.12173 lists Greshake first. Confirm the author order and pages (79–90) of the AISec '23 version on the ACM page before citing it as "Abdelnabi, Greshake, et al."
- **InjecAgent:** only the abstract was verified (24% base rate, 1,054 cases, 30 agents). The 23.6% and 47.0% figures, the fine-tuning result and the limitations list come from the paper body and were not checked here. DOI: 10.18653/v1/2024.findings-acl.624.
- **Tsegai et al.:** the abstract and method were verified. Cost per alert, tool calls and latency, the tuning split, the open-weight F1 range and the cross-scenario miss came from a summary only. It is a preprint: mark it as such in the reference.
