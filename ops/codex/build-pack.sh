#!/usr/bin/env bash
cd "/home/ubuntu/work/gemma/../gemma-wt/codex-pack" || exit 1
codex exec --sandbox workspace-write  -c model_reasoning_effort="medium" \
"Read AGENTS.md (your role: implementer) and CLAUDE.md. Implement: $(cat "/home/ubuntu/work/gemma/ops/codex/build-pack.spec")
Do NOT run git commit (the wrapper commits). Tests must run offline. End with: what changed, test output,
open issues, anything the sandbox prevented." </dev/null > "/home/ubuntu/work/gemma/ops/codex/build-pack.md" 2> "/home/ubuntu/work/gemma/ops/codex/build-pack.log"
rc=$?
git add -A && git commit -q -m "codex-build: pack" || echo "(nothing to commit)" >> "/home/ubuntu/work/gemma/ops/codex/build-pack.md"
exit $rc
