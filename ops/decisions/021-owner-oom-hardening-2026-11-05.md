DECISION: approve-with-changes
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: OOM follow-up: found that job memory caps are only per-process after the reboot; adding a watchdog and a whole-job kill so Etho is protected.
---
Owner instruction (Aniket, 2026-11-05, Remote Control in the Director session): "if there is a better way or a better change, do it." This adds to dec 020 and doesn't replace it. Dec 020 items 4-5 (job cleanup, e4b-timing) still come first.

Director audit of the incident fix (read-only checks, 2026-11-05 ~17:50Z):
- Since the 17:30 reboot there's no systemd user manager: /run/user/1001/bus is missing, linger is off, and our processes run in system.slice/cron.service. So bin/job takes its FALLBACK path, `ulimit -v 5G` per process. That limit doesn't cap a job's process tree: N parallel pytest workers can each reach 5G. A parallel gold run could OOM the 12 GB box again (no swap) as things stand.
- Nothing caps the total across jobs: two jobs at 5G each, plus Etho, plus the Claude sessions, is more than 12G.
- `bin/job kill` sends a signal only to direct children (pkill -P), so grandchildren survive. That's the same orphan pattern as the suspected leak.
- Every process has oom_score_adj=0, so the kernel OOM killer can choose an Etho process before ours.

Instructions to the Builder (run them right after dec 020 item 5, before item 6, and keep each one small):
1. New tool `bin/memguard` (a new file, so it's not bin/job; codex-build is fine, then codex-review it). It's a userspace watchdog that polls every 2 s, uses no privileges, and doesn't depend on systemd:
   a. Targets: only our uid's processes that are (i) descendants of a bin/job wrapper, identified by an env marker that bin/job already sets (GEMMA_JOB_CAP in /proc/<pid>/environ) or (ii) any process with cwd under /home/ubuntu/work/gemma or /tmp whose RSS is over 3G and whose comm isn't claude/node/codex/tmux/bash-of-a-Claude-session. Allowlist only: it must never signal anything outside those sets. It never inspects ~/work/etho, and it only reads /proc/<pid>/{environ,cwd,status,stat} of our own uid to exclude processes.
   b. On every pass, raise oom_score_adj to 1000 on every targeted process (raising it is unprivileged). Then the kernel kills our work before Etho's.
   c. Kill rule: if MemAvailable < 2.5G, or the summed RSS of targeted processes is over 6G, SIGKILL the whole tree of the largest targeted job (every descendant, not only the top pid). Append a line to the job's log and to ops/logs/memguard.log, and send yourself a router mail.
   d. Tests (under bin/job): a synthetic job whose grandchild allocates memory in steps must be killed with no survivors, while a dummy non-target process at the same RSS survives. Keep the test allocations ≤ 3G.
   e. Run it as `bin/job start memguard -- bin/memguard`. Each cycle's re-grounding checks that memguard is running and restarts it if it isn't; put that line in the STATE template. Don't start any heavy job unless memguard is running.
2. bin/job is owner-protected. Do NOT edit it or work around the protection. Instead, write `ops/patches/bin-job-hardening.diff` with: (a) start each job with `setsid` and record its pgid; `kill` signals the whole process group (and stops the scope when there is one), then reports survivors; (b) set `echo 1000 > /proc/self/oom_score_adj` in the wrapper before exec; (c) refuse to start when MemAvailable < 5G, unless the job name ends in `-light`. Get it through codex-review. I'll pass it to Aniket to apply.
3. Until both of those are in place, run at most ONE heavy job at a time on this VM. Waiters and memguard are light and exempt.
4. Dec 020 item 6 still stands for the runner: per-task process group, kill the whole group on timeout, assert no survivors, log peak RSS. Without a user manager, `systemd-run` per task isn't available here. Use setsid + killpg + RSS polling (the item-1 logic as a library), and use `prlimit --as` only as a backstop.
5. Report it all in STATE: memguard status, any kills, and the patch path. No separate report is needed unless memguard fires.

Reasoning: the committed cap only works with a user systemd manager, and since the cron-started reboot there isn't one. A watchdog that targets our processes only, plus oom_score_adj, protects Etho whatever the systemd state, also catches the uncapped case and runaway total memory across jobs, and needs no sudo and no edits to bin/job. Enabling linger would turn on the scope cap, but it could also start user units for other projects. That's Aniket's call, so I've put it to him directly and haven't decided it here.
