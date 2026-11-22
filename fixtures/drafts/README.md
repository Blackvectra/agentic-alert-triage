# Draft cases (not loaded)

`load_cases()` reads only `fixtures/cases/`, so these drafts cannot break tests or runs. Each draft has the scenario, the evidence, the withheld records and the injection written. **The expected answers are yours to write**: every `"TODO"` in `expected_behavior`, `expected_disposition` and `required_evidence`.

To finalize a draft:

1. Replace every `TODO` (write the answers before running anything on the case).
2. Check `withhold_ids` and the injection still match the answers you chose. Change anything you disagree with.
3. Record who wrote the answers in `fixtures/PROVENANCE.md`.
4. Make sure every required record is reachable from the alert's `entities` (rule 5 in the main README).
5. Move the file to `fixtures/cases/` and run `pytest`. The schema and the fixture tests check IDs, splits, canaries, labels and reachability.

## Design notes

No drafts pending. AUTH-002..004 were finalized and moved to `fixtures/cases/`; `fixtures/PROVENANCE.md` records who wrote each. Add a row here (case, scenario, what it tests, injection) for each new draft.

## Encoded injections

For `encoded` delivery the fixture check decodes base64 tokens in the payload to find the canary (`triage.fixtures.canary_in_payload`) (AUTH-003 is an example). Other deliveries still need the canary in plain text.
