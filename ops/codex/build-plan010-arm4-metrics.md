# Plan 010 arm4 metrics build

Implemented against `eval/plans/010-arm4-metrics-spec.md` at `1cbf8c2`, with
`eval/plans/010.md` (including Addendum A) and review item 4 as context.

## What changed

- Added an isolated `arm4` CLI and metrics path in `eval/plan008_metrics.py`.
  Existing mode calculations and dispatch remain unchanged.
- Reused aggregation, pinned classifier checks, smoke recomputation, per-push
  identity, kernel comparison, Wilson intervals, exact sign tests, S81 stray
  classification, and unrounded timing helpers. All three arms retain 33 rows;
  first attempts govern and duplicate attempts remain visible. Incomplete
  inventories write a null verdict with `NO_DECISION` and exit 3.
- Bound the arm-3 and arm-1 input artifacts to the recorded plan-009 report;
  recorded valid `ON-BETTER-VETOED` bases are accepted. The output hashes that
  report, classifiers, timing files, traces, and identity inputs.
- Implemented the registered decision precedence: INVALID, D >= 3,
  absolute timeout/empty limits, timing/safety vetoes, then adoption. Limits are
  16 timeouts, 18 empty patches, and 10 submitted-without-test rows. D73.5 applies
  to both arms in the primary comparison.
- Added paired timeout/empty comparisons against arms 3 and 1, descriptive
  plan-009 adjudication against arm 1 with its original vetoes, and all requested
  descriptives. Overflow counts come from trace error evidence; aggregate-only
  summaries without a terminal event or explicit overflow status are unknown,
  with their counts and IDs reported.
- CLI accepts comma-separated directories or separate directory arguments.
  Optional `--classifiers DIR=D4_JSON,A2_JSON` has arm3 semantics; without it,
  classifier files are discovered locally, in recorded inputs, and in `results/`,
  matched by timing input SHA and pinned classifier SHA.
- Added `eval/tests/test_plan010_metrics.py`: 65 offline synthetic tests covering
  every listed acceptance case, evidence binding, first-attempt retention,
  paired comparisons, original-rule descriptives, overflow unknowns, symmetric
  S81 reporting, and additional inventory failures.

## Test output

New acceptance tests, exact command:

```sh
PYTHONPATH=/home/ubuntu/gemma-local/venv/lib/python3.13/site-packages PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 LITELLM_LOCAL_MODEL_COST_MAP=True /home/ubuntu/gemma-local/pyimg/cpython-3.13-linux-x86_64-gnu/bin/python3 -m pytest eval/tests/test_plan010_metrics.py -q
```

```text
65 passed in 2.99s
```

Full suite using the repository's documented offline interpreter/environment;
`-rs` adds skip reasons. Exact command:

```sh
PYTHONPATH=/home/ubuntu/gemma-local/venv/lib/python3.13/site-packages PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 LITELLM_LOCAL_MODEL_COST_MAP=True /home/ubuntu/gemma-local/pyimg/cpython-3.13-linux-x86_64-gnu/bin/python3 -m pytest eval/tests -q -rs
```

```text
1741 passed, 8 skipped, 4 subtests passed in 31.95s
```

`git diff --check` passed. Tests used installed packages without network access
or package installation. No git commit was run.

## Open issues

None identified in the requested implementation. No arm-4 experiment was run;
the pre-data review gate remains for the Builder to arrange.

## Anything the sandbox prevented

One existing full-suite test skipped because bubblewrap could not create a
NETLINK_ROUTE socket (`Operation not permitted`). The other seven skips were:
missing `dist/31b-v002.zip` (1), disabled `MEMGUARD_LIVE` (1), optional PyYAML
unavailable (1), absent smoke artifacts (1), absent real arm-1 inputs (1), and
opt-in real harness smoke tests disabled (2). No implementation work was blocked.
