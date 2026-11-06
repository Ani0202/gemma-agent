Implemented B3: `earliest_candidate_index()` now scans raw non-root submit responses independently of pairing. Added regressions for pytest before and after the response, both response types, and missing authors. Paired candidates, exit-4 guard, and CLI behavior remain unchanged.

Validation: **1492 passed, 7 skipped, 4 subtests passed**. Base totals **17/12/23/7** and all 33 rows match committed results. No task text emitted.

Open issues: none. Sandbox prevented nothing; base verification used existing artifacts in the main checkout. No commit created.
