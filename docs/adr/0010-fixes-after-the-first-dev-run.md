# 0010: Fixes after the first dev run

The first full dev run (qwen3:32b, 108 runs, 2026-11-23) had no harness errors, but it showed four problems that would have made a held-out run measure the harness or the wording instead of the guardrails. Each fix below was made before the prompts and fixtures were frozen (ADR 0005), and each changes the prompt-and-tool hash or the parsing for every config it applies to, so the dev run is repeated afterwards.

## A code block around the answer is formatting

All 36 config A answers arrived wrapped in a Markdown code block (` ```json ... ``` `). The parser read that as invalid JSON, so every A run was scored as no answer and A could not be compared with B and C at all. The parser now removes a code block that wraps the whole answer before reading it, in the same way for A, B and C. The raw answer is logged unchanged, and the canary check still reads the raw text. An answer with other text before or after the block is still invalid: we remove formatting, we do not go looking for JSON inside prose.
