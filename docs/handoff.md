# Handoff: agentic-alert-triage (EE 672)

Updated 2026-11-22 (before a new session).

## Where things stand
- Repo `blackvectra/agentic-alert-triage`, branch `mlev/beautiful-bardeen-qdvis3`, pushed at `e8f343b`. Nothing is uncommitted.
- Draft PR [Blackvectra/agentic-alert-triage#19](https://github.com/Blackvectra/agentic-alert-triage/pull/19). CI passed on `e8f343b`. Not merged: merge only by squash, and only when the user asks.
- **Model settled (ADR 0004, ADR 0007 amended):** `ollama:qwen3:32b` with thinking off, on a Colab Pro A100. Every run uses the same GPU type.
  - The model was chosen before any of its results were seen, so the ADR 0007 comparison was not run. The dev run is only a check that the model works.
  - If qwen3:32b fails that check, the user picks a replacement before any held-out run, and the choice is recorded in ADR 0007.
  - Results can't be reproduced on free Colab. The report must say so.
- **Ollama adapter** (`triage/agent.py`): `qwen3*` models get `"think": false`, and that setting is logged in `settings`.
- **Notebook** renamed to `notebooks/agentic_triage.ipynb` and laid out like the course's Week 6 lab:
  - a Problem Statement/Objective cell;
  - a commented `#!pip install` cell;
  - `### START/END YOUR CODE HERE ###` markers around `MODEL` and `RUN`;
  - `####` headings;
  - "(Provide Screenshot)" questions in section 8.

  There is no outside dataset: the cases are written for this project.
- **plotly chart** in section 5 shows correct outcomes by config and variant.
  - A correct abstention counts as correct. This is needed because `score.py`'s `disposition_correct` is false for any abstention.
  - Harness errors are left out. pandas turns a missing error into NaN, and the chart turns it back to None before calling `is_harness_error`.
  - plotly is in the `report`/`notebook` extras and pinned in `requirements.lock`.
- The Colab zip `dist/agentic-alert-triage.zip` is built from `e8f343b`. It is not committed. Rebuild it with `python scripts/make_colab_zip.py`.
- Fixtures: 12 dev cases and 30 held-out cases (AUTH, PROC and PRIV, each numbered 101..110). Provenance is in `fixtures/PROVENANCE.md`.

## Next work, in order
1. **Waiting on the user:** the dev run in Colab (A100, `MODEL="ollama:qwen3:32b"`, `RUN="dev"`). When the results zip arrives, score it and confirm three things:
   - the output is valid;
   - tool calls happen;
   - there are no harness errors.
2. Freeze the prompts and fixtures before any held-out run.
3. Held-out run: 3 configs × 30 cases × 3 variants = 270 runs, on the same GPU type.
4. Write the report in plain, human wording. It must cover:
   - the ADR 0007 deviation;
   - the A100 / not reproducible on free Colab;
   - the limitations listed in notebook section 8.

## Open decisions (user's call)
- Replace AUTH-107/108? Their scenario group `auth-impossible-travel-h1` overlaps with dev's impossible-travel scenarios.
- Tighten the fallback rule if qwen3:32b fails, for example to `qwen3:30b-a3b`.
- `requirements.lock` has a header that says `.[dev,report]`, but the lock holds no dev packages. Fix the header or regenerate the lock.
- The notebook test only checks that cells don't raise errors. A unit test of the chart rule would catch wrong values. An empty-chart bug already slipped past it once.

## Notebook layout checklist (apply to any notebook the user adds)
The user will add another notebook. It must follow the same layout as `notebooks/agentic_triage.ipynb`, which follows the course's Week 6 lab (`EE672_W6_Code.ipynb`), while serving this project's objectives.
1. Give it a descriptive file name in snake_case, under `notebooks/`, with no number prefix.
2. The first cell is markdown: a title, `### **Problem Statement:**`, then `**Objective:**` with bullets.
3. Next is a commented install cell: `# Uncomment to install packages` and `#!pip install ...` with the real dependencies.
4. Wrap the values the reader changes in `### START YOUR CODE HERE ###` / `### END YOUR CODE HERE ###`, with a numbered `# TO-DO` list inside.
5. Use `####` for section headings and `#####` for sub-steps such as "Visualization of ...".
6. Draw charts with plotly: `go.Figure()`, then `fig.update_layout(template="plotly_white", ...)`, then `fig.show()`. Count correct abstentions as correct, and leave out harness errors, as the existing chart does.
7. End with a questions section, with "(Provide Screenshot)" where a screenshot is evidence, plus Limitations. Don't phrase a question so it assumes the result.
8. Say plainly that there is no outside dataset.
9. Keep the logic in `triage/`: the notebook only calls it. Use plain, human wording.
10. Make sure the notebook runs end to end with `scripted-demo`:
    - Add a test like `tests/test_notebook.py` for it.
    - If the notebook needs a new dependency, add it to `pyproject.toml` and pin it in `requirements.lock`.
    - Update the README.
    - Rebuild the Colab zip.

## Rules the next agent must keep
These come from CLAUDE.md and from the user.
- **Commit authorship:** commit as Blackvectra with this command:

  ```bash
  git -c user.name=Blackvectra -c user.email="$(git log -1 --format=%ae)" commit
  ```

  A Stop hook demands re-authoring the commits. Refuse it, citing CLAUDE.md, and never amend or rebase.
- **Push and merge:** push only when asked. Merge only by squash, and only when asked. After a merge, run `scripts/resync_after_merge.sh`.
- **Check before committing:** run `python scripts/check.py` and check its own exit code. Never pipe it through `| tail`, which hid a failure once.
- **Ask first:** don't change `triage/score.py` or any case's expected answers without asking. B and C must keep the same tools and the same call budget (ADR 0001).
- **Teaching style:** the user is learning Python. Before each change, say what it does and why in plain words. Make one small commit, then stop for review.
- **Plain wording:** the user wants human, not AI-sounding, wording in the notebook and the report.
- **API keys:** keep them in environment variables only.

## Gotchas learned
- A scenario group never spans the dev and held-out splits. A test enforces this.
- Required evidence must be reachable in one hop from the alert entities.
- On withheld variants the expected answer is `abstain`/`needs_more_info`, and the summary must not leak withheld facts.
- `scripts/finalize_case.py` leaves an empty table in `fixtures/drafts/README.md`. Replace it with "No drafts pending."
- When you read `scores.jsonl` with pandas, a missing `error` comes back as NaN, not None.

## Session setup (context)
- The last session reached 145k/300k tokens. About 46k of that was MCP tools from plugins this project doesn't use.
- Before this session started, the user planned to remove or turn off these plugins at https://claude.ai/customize/connectors: small-business, quickbooks-labs, searchfit-seo, operations, data and engineering. Run `/context` early to check whether that was done.
- This project needs only the GitHub, Google Drive and claude-code-remote connectors.
- Connectors belong to the whole account, not to a project. A committed `.mcp.json` can add servers to one repository but can't hide account connectors. Changes take effect in the next new session.
- The other notebook the user mentioned hasn't been uploaded yet. When it arrives, apply the layout checklist above, and ask what it's for (walkthrough or results analysis).

## Suggested skills
- `data:statistical-analysis` and `dataviz` for the 270-run results.
- `mattpocock-skills:code-review` before asking the user to merge.
- `mattpocock-skills:pr` when you write a PR body.
