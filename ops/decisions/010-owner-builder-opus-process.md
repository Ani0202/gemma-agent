DECISION: approve
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: Builder switched to Opus at owner request; debugging moved to a fast local loop to cut Kaggle round-trips.
---
Owner instruction (Aniket, 2026-11-05): the Builder now runs on Opus (config.env BUILDER_MODEL=opus, session restarted 14:06Z, commit eb83d75). Decision 009 still governs priorities. This adds process rules:

1. No more blind remote iteration. The gold adapter took about 10 Kaggle smoke round-trips and the env fix is on diag4, each taking 30 min to 3 h. From now on, before pushing a Kaggle kernel, reproduce the failing path locally on this x86 VM through bin/job at low priority (RAM < 4 GB, keep 15 GB disk free): same wheelhouse, same subprocess sandbox, and 1–3 failing tasks from data/. Iterate locally in minutes, and push to Kaggle only to confirm.
2. Read the source first. When an official harness call fails (evaluate.py, verification.py, sandbox setup), read the relevant source in one pass and write down the full contract (signatures, env, plugins, how deps get installed) before changing code. Don't add one diagnostic per round-trip.
3. Delegate the env fix to Codex if gold-diag4 doesn't recover fastapi/requests. Give bin/codex-build a precise spec: make the local subprocess sandbox install the task's test deps from the offline wheelhouse and neutralize stray pytest plugins (e.g. langsmith). The acceptance test is gold passing on a named set of 5 currently-failing tasks across fastapi and requests, run locally. Review its result yourself.
4. Two-strike rule: if the same blocker survives 2 remote attempts, stop and write a short report on what's known, what you'll try, and the expected cost, instead of a third blind push.
5. Housekeeping: the 14:06Z journal line says "config.env conflict resolved", but the markers were actually in ops/journal.md (config.env never had a conflict). Append a one-line correction. Commit the uncommitted ops/logs, ops/.digest_day and ops/digest_pending changes in your next cycle commit as usual.
6. Opus usage is heavier. If you hit a usage limit, checkpoint with CONTINUE and say so in STATE.md. If limits start stalling work, the Director moves to Sonnet first.

Reasoning: the delay has come from slow feedback loops more than from model capability, so the model upgrade only pays off with a fast local loop. Splits still gate all quality work, and E4B timing (dec 009 item 4) can proceed in parallel.
