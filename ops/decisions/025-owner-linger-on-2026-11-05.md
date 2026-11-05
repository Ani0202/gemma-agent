DECISION: approve
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: Owner enabled linger: job memory caps now hold across logouts and reboots.
---
Owner action (Aniket, 2026-11-05 ~18:05Z, in the Director session): linger is ON. The Director verified `loginctl show-user ubuntu`: Linger=yes, State=active. The user manager now survives SSH logout and starts at boot, so bin/job's MemoryMax=5G scope path is the normal path, including after a cron-started reboot.

1. The dec 023 item 4 reminder (enable linger on Nov 9) is DONE. Remove it from STATE and don't send it.
2. Dec 023 item 1b (relaunching jobs lost on logout) is no longer needed while Linger=yes. Keep one check in the re-grounding: if `loginctl show-user "$(id -un)" -p Linger --value` isn't `yes`, tell me.
3. The owner patch still goes ahead, at lower urgency: linger-gated scope, `ulimit -d` fallback, and the two kill-path fixes (dec 023 item 1a + dec 024 item 3), as one reviewed diff. The fallback still matters if linger is ever turned off.
4. After the next reboot, check once that no user units auto-started besides ours: `systemctl --user list-units --type=service --state=running`, names only. Report any unit that isn't ours to me without inspecting it. Don't touch it, since it may be Etho's.
5. memguard stays (it covers totals across jobs and uncapped Bash calls), renamed `memguard-light` at the memguard-fix deploy per dec 024.
