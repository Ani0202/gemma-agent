# Plan 009 metrics implementation

Added `arm3smoke` and `arm3` to `eval/plan008_metrics.py`, with offline tests in
`eval/tests/test_plan009_metrics.py`. No commit, GPU use, network requests, cloud
resources, holdout access, task text output, or changes to protected directories.

Functions added: `sign_test`, `_headers`, `_finite_number`, `arm3_timing`,
`thinking_criterion`, `_classifier`, `arm3smoke_metrics`, `aggregate_arm`,
`_quantiles`, `_id_count`, `summarize_arm`, `environment_metrics`, `arm3_decision`,
`arm3_metrics`, and `arm3_cli`.

Aggregation validates inventory before classifier/trace loading, includes timeout
rows, rejects within-directory duplicates with exit 3, retains the earliest supplied
directory for cross-directory duplicates, and lists every duplicated id and its dirs.
Both classifier revisions are hash-bound to timing inputs and paired to every row.
New schemas hash all consumed timing, classifier, trace, id-list and definition-source
files, plus optional smoke JSON. Trace-derived output is limited to counts and ids.
Kernel-code differences are candidates for Director review, not automatic vetoes.

Legacy modes retain their pre-extension script fingerprint
`b9c2cb5efed8a5d2e0e3b0bcbb0f530f4cc8ab59dcb3daa0d414c42dabe4557a`.
This deliberately preserves byte-identical JSON, including schema, under the explicit
compatibility requirement; new modes hash the current script. New definitions are
merged only into new-mode schemas. The existing smoke test's current-file-hash
expectation was updated to the frozen legacy fingerprint. Existing metric calculations,
assertions (17 / 12 / 23 / 7), and old-mode JSON structures are unchanged.
Tests compare legacy outputs against the pre-change source git blob
`9119467d4ec6de8b4fec253f5379608fd1c1bda4`, using identical inputs and import paths.

## Validation

Runner (documented in `eval/README_AGENT_EVAL.md`):

```sh
PYTHONPATH=/home/ubuntu/gemma-local/venv/lib/python3.13/site-packages \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 LITELLM_LOCAL_MODEL_COST_MAP=True \
/home/ubuntu/gemma-local/pyimg/cpython-3.13-linux-x86_64-gnu/bin/python3 \
-m pytest eval/tests/test_plan009_metrics.py eval/tests/test_plan008_metrics.py \
eval/tests/test_plan007_report.py -q
```

Output: **201 passed, 2 skipped in 3.02s**. Skips are existing saved-run-dependent
checks whose paths are absent in this worktree. New saved-run tests actually ran,
reading artifacts from `/home/ubuntu/work/gemma` without writing there.
System `python3` lacks pytest; the documented image interpreter required no installation.
`git diff --check` passed.

Also ran the pre-change file and changed file in `base` mode with identical inputs
and import paths: `cmp /tmp/plan009-base-before.json /tmp/plan009-base-after.json`
passed byte-for-byte. Synthetic old smoke/arm2 output comparisons also pass.
Self-pair CLI output is `/tmp/plan009-self.json`; smoke output is
`/tmp/plan009-smoke.json`. Self-pair metrics are 0/0 discordants, p=1.0,
4/33 resolved per arm, and 12 empty patches per arm. Thinking-off smoke (i) fails
and verdict is `INVALID (smoke i)`. The first two saved thinking-on traces pass the
criterion directly. Output tests reject strings longer than 200 characters outside
schema definitions. Tests cover all specified sign-test values, inventory failures,
first-attempt precedence, missing evidence, safety evidence, hash binding, and drift.

## Open issues and unavailable evidence

Acceptance (b) requests KEEP-OFF for arm-1 self-pairing, but those same files have
**7 governing H rows**. The requested decision rule requires INVALID whenever
arm3 H>=5, with no exemptions. The implementation and test preserve that literal
rule: self-pair decision is INVALID, while discordants remain zero. This is an
explicit unresolved spec conflict; it is not hidden by a self-pair exemption.
The user was asked which behavior governs. All other requested acceptance checks pass.

`plan007_arm1_summary.py` defines no context-overflow predicate, so the descriptive
field says `not available`; no error-text heuristic was invented. Saved arm-1
headers lack Docker image digest, package versions, model id and agent/verification
path hashes; absent fields are null. The available git SHA is not misrepresented as
a path-specific hash. GPU names/count and setup/verification timing are available.
Test-file edits and stray-file rows use the existing plan007 fields and definitions;
missing safety evidence is reported as `not available` and cannot pass that check.
Identity verification remains external (`plan009_identity.py` and journal), as
requested; smoke records header hashes and checks agreement, not external identity.

Sandbox prevented nothing required. All writes stayed in the worktree or `/tmp`.
