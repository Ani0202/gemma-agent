# 31B prompt backlog (dec 084 item 2). Apply ONLY in the next 31B prompt revision; never edit v009 (sha d38c55c7 frozen).
- (a) system.md:35 (v009) protected-config exception is misleading: edits to protected files (e.g. pyproject.toml) are stripped even when
  config is the task's subject (HARNESS_README l.591). Fix: say protected/config/test files are reset; put the fix in source. Src: ops/codex/review-20261107T063339.md
- (b) system.md:11 (v009) recommends error-message keywords for search; the harness recommends symbol names (keywords get only lexical
  fallback, HARNESS_README l.506). Fix: lead with symbol names, keywords as fallback. Src: same review.
- (c) dec 081 item 5: tool-level empty-patch lever (tolerant edit_file error + exploration budget signal). SHELVED for the v012
  lineage by dec 090 item 1: report 023 (ops/reports/023-item5-lever-premise-v012.md) found rule target 1/33 < 3 (18/18 empties =
  timeout, 0 edits). Revived only if eval/plans/010.md Addendum B re-check on arm 4 gives rule_target >= 3/33.
