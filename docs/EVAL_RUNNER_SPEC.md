# Agent eval runner spec (draft, dec 011 item 6)
Goal: run a bundle on dev tasks locally (stub or real vLLM endpoint), producing patches + verification results.

## Environment requirement (MANDATORY)
The agent's in-task pytest (Container A) and verification (Container B) must see the SAME environment as
gold-local, i.e. the scorer docker image as emulated in `eval/kaggle/gold_calibration.py::patch_subprocess_deps`:
1. Host python = `/home/ubuntu/gemma-local/pyimg` (Dockerfile.public mirror: pytest, pytest-timeout==2.1.0,
   typer, build backends, imp.py/telnetlib.py; nothing else). SubprocessManager venvs use
   system_site_packages=True, so ANY extra host package leaks into the sandbox. Harness itself lives in
   `/home/ubuntu/gemma-local/venv` but sandbox venvs must be created from pyimg.
2. `install_test_dependencies` is imported **by name** in `swegemma.evaluate`, `swegemma.harness.verification`,
   `swegemma.harness.sample_verification` and `container_setup` (internal call). The runner must patch EVERY
   such binding (module attribute in each importing module), not just `container_setup`. Acceptance test:
   assert all four names resolve to the patched function before the first task.
3. Same wheel selection as gold (highest-version base wheels <20MB, skip_base_pkgs), then
   `setup.py --fast-path <repo>`. Reuse patch_subprocess_deps; do not fork the logic.
4. Self-check at startup: run the gold patch on 2 known-clean dev tasks through the runner's own env; abort if
   either fails (guards against env drift).
## Other requirements
- Concurrency N against one endpoint; per-task wall time, tokens, tool-call counts logged to runs/<name>/.
- Results file results/<run>.jsonl with schema header line; resumable (skip finished ids).
- Scratch in /tmp only; record any /workspace stray files and test-file edits per task.
