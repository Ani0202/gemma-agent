#!/usr/bin/env bash
cd "/home/ubuntu/work/gemma/../gemma-wt/codex-plan010-arm4-metrics-fix" || exit 1
codex exec --sandbox workspace-write  -c model_reasoning_effort="medium" \
"Read AGENTS.md (your role: implementer) and CLAUDE.md. Implement: $(cat "/home/ubuntu/work/gemma/ops/codex/build-plan010-arm4-metrics-fix.spec")
Do NOT run git commit (the wrapper commits). Tests must run offline. End with: what changed, test output,
open issues, anything the sandbox prevented." </dev/null > "/home/ubuntu/work/gemma/ops/codex/build-plan010-arm4-metrics-fix.md" 2> "/home/ubuntu/work/gemma/ops/codex/build-plan010-arm4-metrics-fix.log"
rc=$?
git add -A && git commit -q -m "codex-build: plan010-arm4-metrics-fix" || echo "(nothing to commit)" >> "/home/ubuntu/work/gemma/ops/codex/build-plan010-arm4-metrics-fix.md"
exit $rc
