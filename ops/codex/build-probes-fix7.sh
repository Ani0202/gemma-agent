#!/usr/bin/env bash
cd "/home/ubuntu/work/gemma-wt/kernel-gate-finfix" || exit 1
codex exec --sandbox workspace-write  -c model_reasoning_effort="medium" \
"Read AGENTS.md (your role: implementer) and CLAUDE.md. Implement: $(cat "/home/ubuntu/work/gemma/ops/codex/build-probes-fix7.spec")
Do NOT run git commit (the wrapper commits). Tests must run offline. End with: what changed, test output,
open issues, anything the sandbox prevented." </dev/null > "/home/ubuntu/work/gemma/ops/codex/build-probes-fix7.md" 2> "/home/ubuntu/work/gemma/ops/codex/build-probes-fix7.log"
rc=$?
git add -A && git commit -q -m "codex-build: probes-fix7 (P1 deadline, G1 flag, signed diffs, b_note, legacy key, attribution)" || echo "(nothing to commit)" >> "/home/ubuntu/work/gemma/ops/codex/build-probes-fix7.md"
exit $rc
