Implemented [bin/pack](/home/ubuntu/work/gemma-wt/codex-pack/bin/pack), offline tests, and usage documentation. Includes strict validation, YAML fallback, deterministic ZIPs, and manifest checksum updates.

Tests: **162 passed offline**.

Open issue: baseline acceptance remains unmet. Bundles are absent from this worktree; main-checkout originals contain prohibited `../` includes. Corrected temporary copies pass both parsers.

Sandbox: main-checkout bundles are outside writable roots and were left unchanged. No commit made.
