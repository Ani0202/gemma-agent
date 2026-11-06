Implemented Plan 007 rev 2 in four files: added the three journal fields to normal and defensive fallback rows, plus the classifier, CLI, and offline synthetic tests. Agent and stock verification paths remain unchanged.

Tests: **782 passed, 5 skipped, 4 subtests passed**. `git diff --check` passed.

Open issues: none. Sandbox prevented nothing; testing required adding the existing local pytest installation to the interpreter’s path. No commit created.
