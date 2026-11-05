Implemented the runner, scripted OpenAI stub, offline tests, and usage documentation. Extended calibration binding patching and captured agent diffs before test edits are stripped.

Tests: `370 passed, 2 skipped, 4 subtests passed`. Used the existing pyimg pytest via `PYTHONPATH`; the harness venv lacks pytest.

Open issue: full E2E remains unverified because the sandbox denied localhost socket creation. The opt-in test was attempted and skipped.

No commits made.
