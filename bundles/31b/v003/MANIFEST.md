# 31b-v003-p5t4 (SCREEN bundle ONLY for plan 005 addendum, cap 4.0; dec 055 item 6). NOT a submission candidate.
- Name: 31b-v003-p5t4 (directory bundles/31b/v003, file dist/31b-v003.zip).
- parent: 31b-v001-t4 (dist/31b-v001.zip sha256=3c3a264652ab1d72ff6b9c5609c482c34a2ab7af37eb600689e5cfa0bf810f6a), arm A of the screen
  (its plan-006 run runs/31b-v001-t4-timing is the paired baseline).
- built from repo git SHA: see the commit that adds this file (parent commit 4eeb441).
- changes (EXACTLY one file): prompts/system.md := bundles/drafts/plan005-system.md (item-4 draft + plan-005 addendum fixes:
  write_file is workspace-only so /tmp scratch goes through a quoted heredoc; edit_file anchors avoid backticks/quotes/backslashes with a
  two-strike change-approach rule; grep-exit-1 and sitecustomize-noise notes; first edit by ~call 12). Cap 4.0, sampling, analyzer unchanged.
  `diff -r bundles/31b/v001 bundles/31b/v003` shows only prompts/system.md (+ this MANIFEST).
- If the screen passes, the submission candidate is a SEPARATE 31b-v004 = 31b-v002 (cap 3.5) + this prompts/system.md.
- status: UNVALIDATED.
- packed 2026-11-06T00:59Z with bin/pack (PASS). zip sha256: 3fa08f768ab7052b9c225c8ec92dcd62743d760cdf32c5dd14e8ab139b18081a (SUPERSEDED, never run)
- re-packed 2026-11-06T01:04Z with bin/pack (PASS, 9094 unpacked bytes, zip 5352 bytes) after review-20261106T005952 BLOCKING 2 + NB4/NB5:
  prompt-text-only edits (generic example-code line replaces the FastAPI/docs_src line; `set -o pipefail;` in the pytest example;
  final checks allowed after an environment-only test failure; config-only rule exception). See eval/plans/005.md Addendum A correction.
zip sha256: e9e603ab7decd589f5ea040579a5facf9c88858986039690ae8053df3e1f4d2f
