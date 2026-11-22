# 0009: Tool descriptions name what the tools can return

Held-out cases added host records a case depends on (PROC-102) and new event types (`helpdesk_ticket`, `registry_value_set`). The `entity_lookup` description said "a user account or IP address", although fixtures also hold host, group and role records, and `event_search` gave no hint of what an `event_type` name looks like, the same failure ADR 0005 fixed. A model that trusts the descriptions could miss required evidence because of wording, which would measure the description, not the guardrails.

We changed only the descriptions, identically for B and C (ADR 0001): `entity_lookup` names every entity kind, and `event_search` gives example type names and says to omit `event_type` when unsure. Tool behavior is unchanged. A test fails if a fixture uses an entity kind the description does not name. This is a pre-freeze change under ADR 0005; the prompt-and-tool hash changes, so earlier dev runs re-run on resume.
