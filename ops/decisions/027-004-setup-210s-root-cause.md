DECISION: approve-with-changes
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: Per-task setup delay traced to our test harness (likely not the scorer); verifying on a free CPU session before one GPU re-timing.
---
I spot-checked results/plan003_pip_fallback_repro.json: a hung fallback takes 103.4 / 103.3 s (5 retries). Two calls predict 206.8 s, and Kaggle measured 207.4-210.8 s; four calls predict 413.4 s, and verification took 410-412 s. The match is convincing, and the plan-003 pre-registration came before the results. Option B is approved, with these fidelity changes:

1. FIDELITY RULE for the timing kernel (it binds the kernel-setup-fix build): our kernel may only be changed to reproduce what the scorer image provides (Dockerfile.public: pip plus the listed tool set, installed offline into the sandbox venv). It must NOT add anything the scorer lacks. Remove spec item 2 (the PIP_NO_INDEX/PIP_RETRIES=0/PIP_TIMEOUT prefix) from the timing kernel. It would hide a real fallback hang that the scorer WOULD pay whenever a hidden repo's build backend isn't in that tool set. If the build already includes it, take it out and re-run its acceptance without it. The setup_calls logging (spec item 3) stays and is the important part: any fallback has to be visible.
2. CPU-only Kaggle verification session (no GPU quota; internet OFF; starter docker_image pinned; no model):
   a. FIRST run the UNFIXED install() on 2 tasks (1 rich, 1 fastapi), capturing the full setup.py output in setup_calls. This proves WHY the offline install fails (no pip in the venv, missing backend, or cp313-vs-py3.12 wheel/ABI mismatch). If the cause is wheel/ABI selection inside the competition's own harness or wheelhouse, the scorer may share it: then STOP, the artifact conclusion is void, and report it.
   b. Then run the FIXED kernel on the same 8 + 8 fresh dev ids. Gate: setup <= 30 s per task, editable install rc 0 on all 16, zero pip "Retrying" lines.
   Write the results to results/kaggle_setup_cpu_check.json. Log the session in ops/budget/kaggle.md (CPU, 0 GPU quota).
3. Only if 2b passes: the ONE GPU re-time of v000 at cap 5 (dec 022 item 3, artifact branch), 8 fresh dev ids, verification skipped. Log it. This measures agent time; v000 at cap 5 is NOT a ship candidate.
4. SHIP-CAP RULE (it adds to dec 022 item 1; both conditions must hold):
   (i) (cap + max measured setup on 4xL4) x 125 + 30 <= 660, and
   (ii) a fallback stress case: (cap + 0.25 x 3.5 + 0.75 x max measured setup) x 125 + 30 <= 660, i.e. 25% of hidden tasks pay the ~210 s fallback because their build backend isn't in the image.
   With ~10 s setup that gives a cap of ~4.0 min. Build e4b-v002 at that cap (and the 31B equivalent once a 31B timing exists) after item 3. Hidden repos may use backends the public four don't, so (ii) is the honest margin. Don't relax it without evidence.
5. If 2b fails (setup still >= 60 s): fall back to e4b-v001 (cap 1.4, sha256 f2ced9c9...e9) and re-time that instead, as dec 022 says. Still only one GPU timing run for this question.
6. In parallel, CPU only: continue dec 022 item 4 (diff survives truncation, patch hygiene, trimming tool output). Those levers matter at cap 4 as well.
7. Next report (005): the 2a cause, the CPU gate, the GPU re-time, and the proposed first-submission bundle with its cap derivation under item 4. I'll run a codex-ask adversarial check before authorizing that submission.

Reasoning: the evidence says our kernel is at fault, but a timing harness is only useful if it's faithful. Making our kernel faster than the scorer is the one way this can turn into a zero-score timeout. A free CPU session proves both the cause and the fix before we spend the single GPU run. The 25% stress margin costs ~0.8 min of cap and protects against hidden repos whose build backend isn't preinstalled.
