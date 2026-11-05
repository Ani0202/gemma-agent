Implemented Round 3:

- Added offline `--no-deps` installs, recursive dependency closure using sandbox markers, runtime copy fallback, and `missing_tool_deps` logging.
- Added non-fatal `pip_check` with bounded output.
- Preserved `SETUP_FIX=0`, single-file staging, and image pin.

Tests: 451 passed, 4 skipped, 1 deselected. The excluded memguard test failed because this sandbox inherits `oom_score_adj=1000`; it expects `0`.

Acceptance remains unverified: `bwrap` was blocked creating the network namespace. Existing acceptance results were preserved. No commit created.
