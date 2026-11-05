Implemented the fidelity toggle, full pip subprocess logging, setup-only CPU mode, staging scripts, summarizer, and fallback package sources. Removed the pip prefix and its test.

Validation: **444 passed, 4 skipped**, excluding the known memguard artifact. Both CPU dry-run modes passed. No commit made; protected paths untouched.

Acceptance remains blocked: bubblewrap reports `Failed to create NETLINK_ROUTE socket: Operation not permitted`. No task timings or pip failure evidence could be collected. Recorded in [acceptance results](results/plan003_kernel_setup_acceptance.json).

Builder command outside the sandbox, running both modes:

```bash
/home/ubuntu/gemma-local/venv/bin/python eval/repro/plan003_kernel_setup.py
```
