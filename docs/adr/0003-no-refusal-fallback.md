# Provider refusals are logged, never rerouted to another model

Status: applies only when the optional Anthropic adapter is used (see ADR 0004).

The provider can decline a request (`stop_reason: "refusal"`, e.g. category `cyber`), which is plausible for injected security content. We do not enable the provider's automatic fallback to another model, because that would answer some runs with a different model and break the single-fixed-model design. A refusal is logged with its category and scored under the existing rules (no output means invalid output: an abstention in C, no answer in B); the report shows refusal counts per config separately so provider refusals are not mistaken for guardrail-driven abstentions.
