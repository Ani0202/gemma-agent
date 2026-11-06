"""Plan 007 arm-1 report helpers (stdlib only).

Pre-registered 2026-11-06 (dec 068 item 1) BEFORE the plan-007 main outputs were downloaded.
This module does NOT change the governing classifier (eval/plan007_pinned/classify_rows_d4cdf0f0.py,
sha256 d4cdf0f0...); it only defines a reporting sub-case over its output, used for sensitivity line 2.

H-VERIFY(empty-patch): a row whose d4cdf0f0 classification is h == 'H-VERIFY' with
reasons == ['verify:contradictory_failure_evidence'] exactly, AND in the raw timing row:
  verified_patch_bytes == 0, exit_code is an int not in (0, -1), resolved is False,
  result_error and agent_error_text are null or empty, and no patch-apply or verify-failure message
  (any VERIFY_AGENT_PREFIXES prefix) appears in result_error / agent_error_text.
Any H row that does not match exactly stays under plan 007's existing H-row rule.
"""

# Copied verbatim from classify_rows_d4cdf0f0.py (kept local so the pinned classifier stays untouched).
VERIFY_AGENT_PREFIXES = (
    'Failed to apply agent patch:',
    'Missing or empty JUnit XML report', 'Malformed JUnit XML report:',
    'No <testsuite> elements found in JUnit XML',
    'No passing tests recorded in JUnit XML', 'Test failures/errors recorded in JUnit XML',
    'Required test node did not pass:',
    'Pytest stdout summary indicates zero or no passing tests',
    'Missing JUnit XML report (possible premature os._exit(0))',
)
EMPTY_PATCH_REASONS = ['verify:contradictory_failure_evidence']


def _blank(value):
    return value is None or (isinstance(value, str) and value.strip() == '')


def is_h_verify_empty_patch(cls_row, timing_row):
    """True iff the row is the pre-registered H-VERIFY(empty-patch) sub-case (pure; no I/O)."""
    if cls_row.get('h') != 'H-VERIFY' or cls_row.get('reasons') != EMPTY_PATCH_REASONS:
        return False
    if cls_row.get('instance_id') != timing_row.get('instance_id'):
        return False
    pb = timing_row.get('verified_patch_bytes')
    if type(pb) is not int or pb != 0:
        return False
    code = timing_row.get('exit_code')
    if type(code) is not int or code in (0, -1):
        return False
    if timing_row.get('resolved') is not False:
        return False
    messages = (timing_row.get('result_error'), timing_row.get('agent_error_text'))
    if not all(_blank(m) for m in messages):
        return False
    if any(isinstance(m, str) and m.strip().startswith(VERIFY_AGENT_PREFIXES) for m in messages):
        return False
    return True
