# gemma-kit: autonomous entry for Kaggle "Gemma 4 Developer Agent"

```
 Claude app (Remote Control) ──▶  gemma-builder   ┐   Oracle VM, tmux session "gemma"
 Claude app (Remote Control) ──▶  gemma-director  ┤   (interactive Claude Code sessions)
 ntfy phone app  ◀──────────────▶ bin/router ─────┘   delivers mail when a session is idle
                                     │
        ops/mail/{builder,director}  │  bin/send, bin/decide   ──▶ GCP VMs via bin/gpu ($150 cap)
        ops/STATE, journal, reports, decisions, budget        ──▶ Kaggle (guarded bin/kaggle-submit)
```

## The loop
1. The Builder works, writes a report, and runs `bin/send director "Decision needed: …"`.
2. The router delivers the message when the Director is idle. The Director decides and records the
   decision with `bin/decide`, which validates it, applies the GPU allowance, escalates or adds
   digest lines, and mails the Builder.
3. Long jobs run detached through `bin/job`. The router wakes the Builder when they finish.
4. Aniket can message either session through Remote Control. Sessions push notifications to him
   through Remote Control (PushNotification) and ntfy.
5. Hooks (`Stop` / `UserPromptSubmit`) tell the router when a session is idle and when Aniket typed.
   The router clears context before new work unless Aniket was active in the last 30 minutes.

## Guardrails
- **Submissions** need a Director authorization matching the zip's sha256, and are limited to one
  per day.
- **GPU spend** needs a Director-granted allowance and is hard-capped at $150. Every VM is created
  with a cloud-side max-run-duration.
- **Secrets and decision files** are denied to the Builder in `.claude/settings.json`.
- **Competition data** is gitignored.

Start with **SETUP.md**. The Builder's first cycles follow `docs/KICKOFF.md`.
