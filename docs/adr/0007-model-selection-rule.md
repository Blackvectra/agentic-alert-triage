# The experiment model is chosen on dev data by a capability rule fixed in advance

Status: accepted 2026-11-22, before any qwen2.5:14b run and before any held-out case exists.

The proposal leaves the model to be "chosen based on cost and tool-calling support", and qwen2.5:7b (ADR 0004) failed the AUTH-001 dry run even with all evidence retrieved, so a larger free model, qwen2.5:14b, is tested. To keep the choice from being tuned to the hypothesis, the rule is fixed now, before its results are seen. Run the same dev dry run with both models (same cases, prompts, tools and settings). Choose the model that, across configs B and C, (1) more often returns valid output, (2) more often retrieves the required evidence, and (3) more often reaches the correct disposition on the complete variant, compared in that order. Guardrail outcomes (injection success, abstention, unsupported recommendations, unauthorized tool use) are not used for the choice. On a tie, keep qwen2.5:7b, the faster model. Both models are free and fit the free Colab T4 GPU. The choice is final before any held-out case is written, all 270 held-out runs use the one chosen model, and ADR 0004 is updated to name it.

Applied by `python scripts/select_model.py <run folders or zips>` (`triage/select.py`). A harness error such as an Ollama HTTP 500 counts as invalid output (decided 2026-11-22).
