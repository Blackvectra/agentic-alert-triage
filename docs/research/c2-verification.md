# Checking C2's claims against primary sources

Research note, 2026-11-23. Question: do the claims in ADR 0012, ADR 0011, `docs/research/real-world-guardrails.md` and the statistics code in `triage/report.py` match what the original sources say?

How to read the status column:
- **supported**: the source says this.
- **partly**: the source says something close, but our wording goes further or cites the wrong source.
- **not supported**: the source does not say this, or says the opposite.
- **unverifiable**: I could not open the part of the source that would settle it.

## 1. Verdict table

| Claim (where) | Source says | Status |
|---|---|---|
| Spotlighting cut attack success "from above 50% to below 2%" on GPT models (research note) | Abstract: >50% to <2%. Body: baseline ~60% on GPT-3.5-Turbo; datamarking 3.1% (GPT-3.5, summarization), 8.0% (GPT-3.5, Q&A), 1.0% (GPT-4, Q&A); encoding 0.0% / 1.8% (GPT-3.5) | partly: true for the best method and setting; not for every method or model |
| JSON labels `{"untrusted_data": ...}` are "spotlighting" (ADR 0012, layer 1) | Paper's closest method is *delimiting*, which it does **not** recommend ("can reduce ASR by about half"; "we do not recommend this approach"). JSON is not mentioned. JSON-encoding untrusted strings is Anthropic's advice, not Hines's | partly: it is a delimiting variant, the weakest kind of spotlighting |
| Base64 "extra tokens, and models mention the encoding" (ADR 0012) | Not in Hines. Microsoft Prompt Shields docs say both: base64 "increases document tokens" and "the model response mentions the document content was base-64 encoded" | supported, but by Microsoft docs, not by Hines. Hines's own reason against encoding is that weaker models lose task performance |
| Datamarking "untested on a 32B model" (ADR 0012) | Paper tests GPT-3.5-Turbo, GPT-4, Text-003 only | supported |
| NIST CAISI: adaptive attacks raised success "from 11% to 81%" (research note, ADR 0012 by reference) | "from 11% for the strongest baseline attack to 81% for the strongest new attack", upgraded Claude 3.5 Sonnet, AgentDojo Workspace held-out tasks | supported (say which model) |
| NIST CAISI: "57% to 80% on average" by repeating 25 times | "the average attack success rate increased from 57% to 80%" over five injection tasks, 25 tries each; model not named in the post | supported |
| Detectors are "fundamentally heuristic" (research note) | Beurer-Kellner et al.: "these defenses remain fundamentally heuristic and cannot guarantee prevention of all attacks" | supported |
| Regex scan: no source gives a measured detection rate | None found. Nasr, Carlini et al. 2025 bypass 12 defenses with >90% success for most, where most "originally reported near-zero" | supported; add Nasr et al. as stronger evidence |
| C2's code checks correspond to CaMeL / design patterns | CaMeL separates control and data flow and enforces capability policies at tool calls. Design-patterns paper describes plan-then-execute, action-selector, quarantined LLM with output constraints. Neither describes "reject a verdict and ask the model to repair" | partly: layer 2 is close to plan-then-execute; layer 3 is a heuristic output check, not CaMeL-style enforcement |
| Case-level percentile bootstrap (report.py) | Standard cluster bootstrap idea; code resamples case ids and keeps all rows | supported (minor index detail, see §5) |
| Exact McNemar, two-sided as 2 × smaller tail, capped at 1 (report.py) | This is the usual exact binomial McNemar | supported |
| 95% two-sided CI vs a 10-point margin, with "inconclusive" (ADR 0011, `usefulness_verdict`) | CONSORT NI extension: upper bound of two-sided (1−2α) CI or one-sided (1−α) CI must be below Δ; worked example uses one-sided 97.5%; CIs that cross Δ are "inconclusive" | supported, with two wording gaps (§5) |
| Labelling C2 "exploratory / post-hoc" is enough (ADR 0012) | Dwork et al.: "Reusing a holdout set adaptively multiple times can easily lead to overfitting to the holdout set itself" | partly: the label is right but needs a stated bias direction and must not be used for headline claims |

## 2. Spotlighting (Hines et al. 2024)

Source: https://arxiv.org/abs/2403.14720 (HTML body read: https://arxiv.org/html/2403.14720).

- The three methods, in the paper's words:
  - Delimiting: "One or more special tokens are chosen to prepend and append the input text and the model is made aware of this boundary."
  - Datamarking: "we interleave a special token throughout the entirety of the text."
  - Encoding: "the input text is transformed using a well-known encoding algorithm such as base64, ROT13, binary".
- Numbers: baseline "around 60%" (GPT-3.5-Turbo). Delimiting "can reduce ASR by about half". Datamarking to 3.10% (GPT-3.5, summarization), 0.00% (Text-003), 8.0% (GPT-3.5, Q&A), 1.0% (GPT-4, Q&A). Encoding to 0.0% and 1.8% (GPT-3.5).
- On delimiting: "could be easily subverted by an attacker who gains knowledge of our system prompt" and "we do not recommend this approach because more effective ones are available".
- On encoding: "GPT-3.5-Turbo suffers in task performance when faced with encoded text"; use it "only ... with the highest-capacity models".
- No mention of JSON, token cost, or models mentioning the encoding.

**What this means for us.** Wrapping tool output as `{"untrusted_data": ...}` is a boundary marker around the whole text: that is delimiting, not datamarking. The paper's own measurement says delimiting only halves attack success, and the authors advise against it. So ADR 0012 should not call layer 1 "spotlighting" without saying it is the delimiting variant, and must not borrow the "<2%" number for it. The base64 reasons are real, but they come from Microsoft's Prompt Shields page (https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection): "it increases document tokens due to base-64 encoding" and "the model response mentions the document content was base-64 encoded". Hines's own reason (weaker models lose task performance) is arguably the stronger one for a 32B local model.

Also note: the "<2%" figures are for GPT-3.5/4 with fixed attacks, which the research note already says.

## 3. Pattern / regex injection detection

- NIST CAISI (https://www.nist.gov/news-events/news/2025/01/technical-blog-strengthening-ai-agent-hijacking-evaluations): "increase in attack success rate from 11% for the strongest baseline attack to 81% for the strongest new attack" on upgraded Claude 3.5 Sonnet, and "the average attack success rate increased from 57% to 80%" with 25 tries per task. The repo's numbers are correct. Our note should add the model name; "one model" is accurate but vague.
- Nasr, Carlini, Tramèr et al. 2025, "The Attacker Moves Second" (https://arxiv.org/abs/2510.09023): they bypass 12 recent defenses "with attack success rates above 90% for most", and "the majority of defenses originally reported near-zero attack success rates". The abstract covers defenses in general, not regex detectors specifically.
- Beurer-Kellner et al. (https://arxiv.org/html/2506.08837v3): detection systems "remain fundamentally heuristic and cannot guarantee prevention of all attacks"; "Block and allow lists might be incomplete or outdated and limit utility".
- Prompt Shields docs list "Encoding Attacks" as a class. Our scan decodes base64 chunks (`triage/c2.py`, `_readable_text`), which helps against that one encoding only.
- I found no primary source that measures a regex scan's detection or false-positive rate. The repo already says so. That is honest.

**Caveat specific to C2.** The flag also counts as a known-bad indicator (`known_bad_indicators`), so a false positive on a benign log line can block a correct `benign` answer and push it to `needs_more_info`. That is a usefulness cost the report should count (flags on runs with no planted injection).

## 4. Code-enforced policy vs prompt-only rules

- CaMeL (https://arxiv.org/abs/2503.18813): "explicitly extracts the control and data flows from the (trusted) query", so "the untrusted data retrieved by the LLM can never impact the program flow", plus capabilities "enforcing security policies when tools are called". 77% of AgentDojo tasks "with provable security" vs 84% undefended.
- Design patterns (https://arxiv.org/html/2506.08837v3): plan-then-execute ("this data cannot inject instructions that make the agent deviate from its plan", but "does not prevent all prompt injections"); action-selector; quarantined LLM whose "output ... must satisfy certain safety constraints" (e.g. "a regex that ensures the output of map is a number"). The paper does not discuss repair or retry loops.

**Does C2 match?**
- Layer 2 (must call `event_search` and `entity_lookup` first) is a weak form of plan-then-execute: it forces which tools run, but the model still reads untrusted data and chooses arguments and the verdict.
- Layer 3 (reject `benign` on known-bad evidence, check citations, one repair, fall back to `needs_more_info`) is deterministic output validation, which OWASP LLM01 recommends. It is **not** CaMeL: the privileged model still reads raw untrusted text, and nothing is provable. The known-bad list is a block list, which the design-patterns paper calls possibly "incomplete or outdated".
- The repair turn has no primary-source backing in these papers. It is our own design.

**Overclaim risk.** ADR 0012 itself does not claim CaMeL-like guarantees, which is good. The research note's line "CaMeL shows the general idea of code-enforced policies" is fair. Any report text should say "deterministic output checks (OWASP LLM01 #2), loosely in the spirit of plan-then-execute; no security guarantee".

## 5. Statistics in `triage/report.py`

**Case-level bootstrap (`bootstrap_ci`).** Resamples case ids with replacement and keeps all rows of each case together, then takes percentiles. That is the standard cluster (case) bootstrap, and it keeps B and C paired within a case. Two small notes:
- The lower bound uses `int(tail * (n-1))` and the upper `round((1-tail) * (n-1))`. With 2000 draws this gives index 49 and 1950, slightly asymmetric. Harmless, but `numpy.percentile` or the same rounding on both ends would be cleaner.
- Resamples where the statistic is `None` are dropped silently; the count should be reported if it is ever non-zero.
- With only ~30 cases, percentile bootstrap intervals tend to be a little too narrow. Worth one sentence in the report. (General textbook point; I did not open a textbook in this session, so treat as *unverified*.)

**Exact McNemar (`mcnemar`).** Uses only discordant pairs, p = min(1, 2 × P(X ≤ min(b, c))) with X ~ Binomial(b+c, 0.5). That is the standard exact two-sided McNemar. With zero discordant pairs it returns p = 1, which is correct. Pairing is by (case_id, variant). Correct.

**Non-inferiority decision (`usefulness_verdict`, ADR 0011).** CONSORT NI extension, Piaggio et al., JAMA 2012;308(24):2594-2604 (https://jamanetwork.com/journals/jama/fullarticle/1487502):
- "the upper bound of the 2-sided (1 − 2α) × 100% CI ... or the upper bound of the 1-sided (1 − α) × 100% CI has to be below the margin Δ".
- Worked example: "the upper limit of the one-sided 97.5% confidence interval".
- Figure 1 legend: when the CI includes Δ, "the result ... is inconclusive".

So a two-sided 95% CI (equivalent to one-sided 97.5%) is the conservative, common choice. Our pass rule (upper bound ≤ 10 points) matches. Two gaps:
1. CONSORT says "below" the margin; ADR 0011 counts exactly 10 as a pass. That is a choice we fixed in advance, which is fine, but say it differs from the strict wording.
2. CONSORT calls an interval wholly above Δ "inferior"; our "fail" matches that.

**Multiple comparisons.** `compare` runs three McNemar tests per pair, and C2 adds a B-vs-C2 comparison on top of B-vs-C, plus the C2-vs-C injection rule. No correction is applied. The report should say p-values are unadjusted and only the ADR 0011 usefulness call is the pre-set primary result.

**C2 injection rule (`c2_success`).** It passes when C2's injection rate is below C's point estimate. No interval or test is used, so a one-run difference passes. ADR 0012 does say this, but the report should show the C-vs-C2 McNemar on `injection_success` next to it, and call a non-significant drop "lower, not shown to be lower".

## 6. Post-hoc and exploratory labelling

- Dwork et al. 2015 (https://arxiv.org/abs/1506.02629): "Reusing a holdout set adaptively multiple times can easily lead to overfitting to the holdout set itself."
- Dwork et al. 2014 (https://arxiv.org/abs/1411.2664): standard inference "assumes a fixed collection of hypotheses", while in practice "hypotheses and new analyses" are generated from data already seen.

C2 was designed after seeing aggregate held-out results (C's failure modes: few calls, early abstention, 27% injection), and is run on the same held-out cases. Even though no held-out case text was used in the code, the *design choices* were driven by held-out results. Labelling it exploratory is the right call, and tuning only on dev is good practice. What the sources imply we should also say:
- The bias direction: C2's held-out numbers are likely **optimistic**, because its design targets the exact failures seen on these cases.
- C2's result cannot replace or "fix" the frozen A/B/C conclusion, and should not be quoted in the abstract or headline without the label.
- The only clean test of C2 is on new cases (a fresh held-out set) or new injection phrasings. Say this as future work.
- Pre-registration guidance generally asks that the analysis plan be time-stamped before data are seen. ADR 0012 fixes success rules before the C2 run; the commit date of ADR 0012 versus the first C2 held-out log is the evidence, and the report should cite both. (I did not open a specific pre-registration guideline in this session: *unverified* as a quote.)

## 7. Changes we should make

**ADR 0012, layer 1.** Replace "Untrusted tool output (spotlighting)" and the last sentence with:
> **Untrusted tool output (delimiting).** ... This is the *delimiting* form of spotlighting (Hines et al. 2024), which the paper found only halves attack success on GPT-3.5 and does not recommend; their <2% results are for datamarking and encoding. JSON labels were chosen over base64 because base64 adds tokens and models tend to mention the encoding (Microsoft Prompt Shields docs), and because Hines et al. found encoding hurts task performance on weaker models; datamarking is untested on a 32B model.

**ADR 0012, Success.** Add: "The injection rule compares point estimates. The report also shows the paired McNemar test for C vs C2 and does not call the drop significant unless it is."

**ADR 0012, Post-hoc.** Add: "Because C2 targets failures seen on these held-out cases, its held-out numbers are likely optimistic. A clean test needs new cases or new injection phrasings."

**ADR 0011, Disclosure.** Add: "CONSORT (Piaggio et al. 2012) requires the upper bound to be *below* the margin; we count exactly 10 points as a pass, fixed in advance. A two-sided 95% interval equals the one-sided 97.5% bound CONSORT uses."

**Research note `real-world-guardrails.md`.**
- §1 and the table: name the model for 11% to 81% (upgraded Claude 3.5 Sonnet, AgentDojo Workspace) and say the 57% to 80% model is not named.
- Spotlighting row: give per-method numbers and say delimiting "about half", not recommended.
- Move the base64 cost to the Prompt Shields citation only (already done in the table; ADR 0012 should match).
- Add Nasr et al. 2025 (arXiv 2510.09023) to Pitfalls #1 and #3.

**Report code / output (`triage/report.py`).**
- State in `summary.md` that McNemar p-values are unadjusted for multiple comparisons.
- Add a C vs C2 McNemar on `injection_success` next to `c2_success`.
- Report how many C2 injection flags fired on runs with no planted injection (false positives).
- Optional: make the bootstrap percentile indices symmetric (both `round`, or `numpy.percentile`), and report dropped resamples.

## References (opened 2026-11-23 unless marked)

- Hines et al. 2024, Spotlighting. https://arxiv.org/html/2403.14720
- Microsoft Learn, Prompt Shields (Spotlighting section). https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection
- NIST CAISI 2025, Strengthening AI Agent Hijacking Evaluations. https://www.nist.gov/news-events/news/2025/01/technical-blog-strengthening-ai-agent-hijacking-evaluations
- Nasr, Carlini, et al. 2025, The Attacker Moves Second. https://arxiv.org/abs/2510.09023 (abstract only)
- Beurer-Kellner et al. 2025, Design Patterns for Securing LLM Agents. https://arxiv.org/html/2506.08837v3 (first 100k characters)
- Debenedetti et al. 2025, CaMeL. https://arxiv.org/abs/2503.18813 (abstract only)
- Piaggio et al. 2012, CONSORT non-inferiority extension, JAMA 308(24):2594-2604. https://jamanetwork.com/journals/jama/fullarticle/1487502 (first 100k characters)
- Dwork et al. 2015, Generalization in Adaptive Data Analysis and Holdout Reuse. https://arxiv.org/abs/1506.02629 (abstract only)
- Dwork et al. 2014, Preserving Statistical Validity in Adaptive Data Analysis. https://arxiv.org/abs/1411.2664 (abstract only)

### Not verified
- OWASP LLM01 wording was not re-opened here (relied on the existing note).
- No statistics textbook opened for bootstrap small-sample behaviour or exact McNemar; the code was checked against the standard definitions.
- No specific pre-registration guideline opened.
