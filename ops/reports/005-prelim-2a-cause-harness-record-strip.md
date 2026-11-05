# Report 005-prelim: 2a cause is the competition's own harness (RECORD strip), so the dec 027 2a STOP threshold is met

## 1. Question for the Director
The local stage-2a diagnosis meets the dec 027 item 2a STOP condition ("the scorer may share it"). Should I
(A) stop the artifact branch and go straight to the single GPU re-time of e4b-v001 (cap 1.4), or
(B) first run the free Kaggle CPU 2a session, unfixed install() on 2 tasks, so we record the real fallback count and duration on Kaggle, and then do (A)?

## 2. Pre-registration (eval/plans/004.md, written 18:15Z before any run)
Stage 2a outcomes: (i) pip/backend absent in OUR venv only -> artifact -> 2b; (ii) wheel/ABI selection inside the competition's
own harness or wheelhouse (the scorer may share it) -> STOP, artifact conclusion void, report; (iii) no fallback -> environment differs, report.
Ship cap: (i) (cap+S)x125+30 <= 660 and (ii) (cap+0.875+0.75S)x125+30 <= 660.

## 3. What I did
- Kernel-setup-fix round 4 (branch codex/kernel-setup-fix c4c9528): timing kernel now reproduces the Docker order
  (Dockerfile.public tools -> workspace editable install -> base-tar injection -> competition setup.py). No PIP_* prefixes (dec 027 item 1).
  setup_calls logging is on.
- Local acceptance, both modes, on rich_3006 + fastapi_14986: results/plan003_kernel_setup_acceptance_r4local.json.
- Independent Codex review of my causal claim: ops/codex/review-20261105T190713.md.

## 4. Results (n=2 tasks, 1 sample each, local x86 bwrap, no network; this is NOT scorer timing)
| task | mode | editable rc | Retrying lines | setup.py s | setup total s |
|---|---|---|---|---|---|
| rich_3006 | SETUP_FIX=0 | 1 | 5 | 8.85 | 11.6 |
| fastapi_14986 | SETUP_FIX=0 | 1 | 5 | 8.59 | 11.8 |
| rich_3006 | SETUP_FIX=1 (Docker order) | 1 | 5 | 8.77 | 16.9 |
| fastapi_14986 | SETUP_FIX=1 (Docker order) | 0 | 0 | 0.59 | 9.1 |
Source: results/plan003_kernel_setup_acceptance_r4local.json (rows[].setup_calls). No pass-rate data in this report, so no CIs or discordant pairs.

Mechanism (Codex: SUPPORTED as a published-harness hazard, finding 3): swegemma container_setup.py builds the base tar with
the task's OWN package included (the skip set covers only pytest/pip/...) and strips '/RECORD' (line 266). Injection runs after the
editable install. rich: 13.4.2 editable installs fine with a RECORD, then the injected 15.0.0 dist-info (no RECORD) wins
-> pip `uninstall-no-record-file` -> one index fallback -> 5 Retrying lines. fastapi passes only because of metadata
directory-enumeration order (Codex reproduced the order flip synthetically, finding 4). This is task-dependent luck, not protection.

What is NOT established (Codex finding 1, BLOCKING against my earlier claim):
- "S ~ 210 s is a scorer property" is NOT SUPPORTED. Locally there is ONE fallback call per setup.py, and it takes ~8 s
  (DNS fails fast). The ~103 s/call hang came from the plan-003 repro under a different network condition. The Kaggle v000 timing kept
  no setup output, so we don't know its cause or call count there.
- The deployed scorer image digest is unknown (mutable tags). Docker runs network_mode=none, so the scorer could pay ~8 s or
  ~100+ s per fallback, depending on how the offline network fails.
- Codex finding 2 (BLOCKING for eval/, not for this decision): eval/sandbox_env.py (our quality-eval sandbox) still injects
  before the editable install and uses a constant cache name, so it does not match Docker. Only agent_timing.py was fixed. To fix before any
  quality eval that depends on setup.

Consequence for the ship rule: keep the interim rule. Max measured S = 212 s -> (i) cap <= 1.507 min; (ii) at cap 1.4:
(1.4+0.875+0.75x3.533)x125+30 = 645.6 <= 660. e4b-v001 (cap 1.4) passes both conditions. The cap-4.0 path (e4b-v002)
needs S ~ 10 s on scorer-equivalent hardware, and the evidence above doesn't support that.

## 5. Options
A. STOP now (strict reading of 2a). Skip 2b. Use the one GPU timing run on e4b-v001 cap 1.4 (dec 027 item 5) to measure real agent time
   and setup with setup_calls logging. Fastest route to a first submission. We lose the chance to learn whether Kaggle's fallback is
   ~8 s or ~103 s, so cap stays at ~1.4 indefinitely unless the timing run itself shows it (it will, since setup_calls logging is on).
B. Kaggle CPU 2a first (0 GPU quota, ~20 min, unfixed install() on the same 2 tasks, internet OFF, starter image pinned),
   then A. That answers Codex's open question 2 (fallback count and duration on Kaggle). It doesn't change the rule by itself, because the scorer image is unverified,
   but it tells us whether the 207-211 s was 2x103 s hangs. Cost: one more cycle before the GPU run.
C. A + bundle-side mitigation research: nothing in agent.yaml controls harness setup (the clock starts after setup, but setup
   still counts toward the 12 h), so there's no bundle lever here. Listed only to rule it out.

## 6. Recommendation
**A**, with a modification: the v001 GPU re-time kernel already logs setup_calls, so it answers question B's "how long does the
fallback take on Kaggle" on L4x4 directly, which saves a separate CPU session. I'm requesting authorization to push that ONE
Kaggle L4x4 timing run of e4b-v001 (dist/e4b-v001.zip sha256=f2ced9c97ee1447cb3a78c0ebf65f4ecaff90c84b18313645d5d043c62d277e9)
on eval/plans/004-gpu-retime-ids.txt (8 ids, verification skipped) within the existing weekly Kaggle plan (~1.5 L4x4 h).
Prerequisite: merge the kernel-setup-fix agent_timing.py changes (round 4) into the timing kernel after one codex-review of
the merge diff. I'll fix eval/sandbox_env.py (finding 2) in parallel, CPU only.
No SUBMIT yet. Report 005 (final) follows the re-time, with the cap derivation for your codex-ask check.
