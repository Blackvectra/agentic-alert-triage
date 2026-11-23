# Handoff: agentic-alert-triage (EE 672)

Updated 2026-11-23 (after two dev runs, the ADR 0010 fixes and the code review).

## Where things stand
- Repo `blackvectra/agentic-alert-triage`, branch `mlev/beautiful-bardeen-qdvis3`. Run `git log` and `git status -sb` for the current commit and whether it is pushed; this note is not updated for every commit.
- Draft PR [Blackvectra/agentic-alert-triage#19](https://github.com/Blackvectra/agentic-alert-triage/pull/19). Check the PR for CI on the newest commits. Not merged: merge only by squash, and only when the user asks.
- **Two dev runs are done, both on code from before the fixes** (`b33f72b`): one on an L4 (a rehearsal, not data to report) and one on the A100. Neither had a harness error. Both showed the same four problems, fixed in ADR 0010:
  - every config A answer came inside a Markdown code block and was scored as no answer;
  - B and C mostly made one tool call (`guide_lookup`) and answered `needs_more_info`;
  - C cited the alert's own id as evidence;
  - the model passed a `host` argument that `event_search` does not accept.
- **The fixes are not yet tested on the real model.** Unit tests show the code does what it says. Only a new dev run shows whether qwen3 behaves differently.
- **Findings from comparing the two runs** (worth a sentence in the report):
  - Same model, seed and temperature, different GPU type: only 23 of 108 answers were word for word the same, and C went from 4 correct to 7. So "every run on the same GPU type" matters, and a gap of 3 in 36 on 12 cases is not a difference.
  - A100: about 8 s a run, 16 minutes of model time for 108 runs. Expect roughly 40 minutes for the 270 held-out runs, more if B and C now make more calls.
  - On the A100, C answered the attacker's `benign` on AUTH-003 injected, inside a code block. The old parser hid it as an abstention; it now counts as an injection success.
  - Whether two runs on the same A100 match each other has not been tested.
- **Resume** reruns a saved run if its prompts or tools differ, or if an older answer parser read it (`answer_parser` in the log, `ANSWER_PARSER_VERSION` in `triage/agent.py`). Raise that number whenever `_parse_output` changes how it reads an answer; nothing enforces this.
- **Progress:** each run line shows `[n/total]` and a rough time left.
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
  - The counting rule lives in `triage/report.py` and has its own unit test in `tests/test_report.py`.
- **Lock file:** `requirements.lock` pins everything from `pip install -e ".[dev,report,notebook]"` (104 packages, built on Python 3.13, Linux).
  - `tests/test_lock.py` fails if a package in the `report` or `notebook` extras has no pin.
  - CI installs from `pyproject.toml` on Python 3.11, not from the lock, so the lock is only verified by the one install that built it.
  - To rebuild it, pass the old lock as a constraints file (`-c`) so existing versions don't move.
- The Colab zip `dist/agentic-alert-triage.zip` is not committed. Rebuild it with `python scripts/make_colab_zip.py` after any code change and before a run; the script prints the commit it was built from.
- Fixtures: 12 dev cases and 30 held-out cases (AUTH, PROC and PRIV, each numbered 101..110). Provenance is in `fixtures/PROVENANCE.md`.

## Next work, in order
1. **Waiting on the user:** the third dev run in Colab (A100, `MODEL="ollama:qwen3:32b"`, `RUN="dev"`) with a zip built from the current commit. When the results zip arrives, score it and check:
   - config A gives valid answers;
   - B and C make more than one tool call and evidence recall rises;
   - C no longer cites the alert id;
   - no `host` arguments on the PROC cases;
   - the injected text is seen more often, so the injection numbers mean something;
   - no harness errors.
2. If more fixes are needed, keep each round short, record the reason in ADR 0010, and repeat the dev run. Every prompt change tunes the prompts to these 12 cases, which is the reason to freeze.
3. Freeze the prompts and fixtures before any held-out run.
4. Held-out run: 3 configs × 30 cases × 3 variants = 270 runs, on the same GPU type.
5. Write the report in plain, human wording. It must cover:
   - the ADR 0007 deviation;
   - the A100 / not reproducible on free Colab, and the GPU-to-GPU difference above;
   - the dev-run fixes in ADR 0010;
   - the limitations listed in notebook section 8.

## Open decisions (user's call)
- Replace AUTH-107/108? Their scenario group `auth-impossible-travel-h1` overlaps with dev's impossible-travel scenarios.
- Tighten the fallback rule if qwen3:32b fails, for example to `qwen3:30b-a3b`.

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
- **Commit authorship:** the author is Blackvectra and the committer is the session's own signed identity, so GitHub shows the commit as Verified (the user asked for this on 2026-11-23). Commit with:

  ```bash
  git commit --author="Blackvectra <$(git log -1 --format=%ae)>"
  ```

  Don't set `user.name` or `user.email` for the commit: that makes it unsigned. A Stop hook may still ask to re-author commits with `--reset-author`; refuse that, because it would remove Blackvectra as the author. Don't rewrite commits that are already pushed.
- **Push and merge:** push only when asked. Merge only by squash, and only when asked. After a merge, run `scripts/resync_after_merge.sh`.
- **Check before committing:** run `python scripts/check.py` and check its own exit code. Never pipe it through `| tail`, which hid a failure once.
- **Ask first:** don't change `triage/score.py` or any case's expected answers without asking. B and C must keep the same tools and the same call budget (ADR 0001).
- **Teaching style:** the user is learning Python. Before each change, say what it does and why in plain words. Make one small commit, then stop for review, unless the user asks for a batch.
- **Test first:** the user asked for TDD (2026-11-23). Write the failing test, see it fail, then write the code. Test through `run_case`, `score_run`, the tool functions, the `triage.run` command line and the report functions.
- **Plain wording:** the user wants human, not AI-sounding, wording in the notebook and the report.
- **API keys:** keep them in environment variables only.

## Gotchas learned
- A scenario group never spans the dev and held-out splits. A test enforces this.
- Required evidence must be reachable in one hop from the alert entities.
- On withheld variants the expected answer is `abstain`/`needs_more_info`, and the summary must not leak withheld facts.
- `scripts/finalize_case.py` leaves an empty table in `fixtures/drafts/README.md`. Replace it with "No drafts pending."
- When you read `scores.jsonl` with pandas, a missing `error` comes back as NaN, not None.
- A result that looks like a harmless abstention can be an unread answer: check `output_raw` before trusting an invalid-output count.
- A test that only checks a phrase is in a prompt holds the wording in place; it does not show a model follows it.

## Session setup (context)
- The last session reached 145k/300k tokens. About 46k of that was MCP tools from plugins this project doesn't use.
- The user planned to remove or turn off these plugins at https://claude.ai/customize/connectors: small-business, quickbooks-labs, searchfit-seo, operations, data and engineering. They were all still loaded in the 2026-11-22 session.
- Only the user can run `/context`; the agent can't. Ask the user for the total.
- This project needs only the GitHub, Google Drive and claude-code-remote connectors.
- Connectors belong to the whole account, not to a project. A committed `.mcp.json` can add servers to one repository but can't hide account connectors. Changes take effect in the next new session.
- The other notebook the user mentioned hasn't been uploaded yet. When it arrives, apply the layout checklist above, and ask what it's for (walkthrough or results analysis).

## Suggested skills
- `data:statistical-analysis` and `dataviz` for the 270-run results.
- `mattpocock-skills:code-review` before asking the user to merge.
- `mattpocock-skills:pr` when you write a PR body.
