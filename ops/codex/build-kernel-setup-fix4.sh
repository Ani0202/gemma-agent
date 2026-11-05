#!/usr/bin/env bash
cd "/home/ubuntu/work/gemma-wt/codex-kernel-setup-fix" || exit 1
codex exec --sandbox workspace-write -c model_reasoning_effort="medium" \
"Read AGENTS.md (your role: implementer) and CLAUDE.md. Implement: $(cat "/home/ubuntu/work/gemma/ops/codex/build-kernel-setup-fix4.spec")
Do NOT run git commit (the wrapper commits). Tests must run offline. End with: what changed, test output,
open issues, anything the sandbox prevented." </dev/null > "/home/ubuntu/work/gemma/ops/codex/build-kernel-setup-fix4.md" 2> "/home/ubuntu/work/gemma/ops/codex/build-kernel-setup-fix4.log"
rc=$?
git add -A && git commit -q -m "codex-build: kernel-setup-fix4" || echo "(nothing to commit)" >> "/home/ubuntu/work/gemma/ops/codex/build-kernel-setup-fix4.md"
exit $rc
