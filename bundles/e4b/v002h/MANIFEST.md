# e4b-v002h (dec 083 item 2): FINALS-ELIGIBLE E4B FALLBACK = e4b-v002 minus the FastAPI/docs_src hint line. Submission candidate (pending authorization).
- Name: e4b-v002h (directory bundles/e4b/v002h, file dist/e4b-v002h.zip). Not e4b-v003 (generic fixes stay a separate, later candidate).
- parent: e4b-v002 (dist/e4b-v002.zip sha256=60c0074684ef4f9aa9cd8744d08fa29a37f3b94fc893541a8b96ceed54944dad), SCORED public 0.05 at T=5.007 h (ref 58039259).
- built from repo git SHA: parent commit 921ce90 (see the commit that adds this file).
- change (EXACTLY one deleted line): prompts/system.md l.16 "- For documentation code tasks (e.g. FastAPI), edit executable code under `docs_src/`." (dec 057 no-repo-hint rule).
  `diff -r bundles/e4b/v002 bundles/e4b/v002h` shows only that deleted line (+ this MANIFEST). grep -ri 'fastapi|docs_src' bundle = 0.
- unchanged: agent.yaml, configs/, sub_agents/, eval_config.yaml (cap 1.0, incl. its v002 header comment), so the timing bound is identical to v002 (619.4 min <= 660; scored T=5.007 h).
- prompt-only: no Gate-5 smoke needed (dec 083 item 2).
- status: UNVALIDATED locally; codex review pending.
zip sha256: 938d618ceaeb7602d86e49a9cf7d2b7ce7191e8936d9520bb7d005a6c5f04836
