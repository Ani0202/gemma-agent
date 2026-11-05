#!/usr/bin/env bash
# Live memguard test on branch codex/memguard-fix (needs bin/job's GEMMA_JOB_CAP env; allocates <=2.4 GiB).
cd /home/ubuntu/work/gemma-wt/codex-memguard-fix || exit 1
SP=$(ls -d /home/ubuntu/gemma-local/pyimg/cpython-3.13*/lib/python3.13/site-packages | head -1)
MEMGUARD_LIVE=1 /home/ubuntu/gemma-local/venv/bin/python3 -c "import sys; sys.path.append('$SP'); import pytest; sys.exit(pytest.main(['-q','-p','no:cacheprovider','eval/tests/test_memguard.py','--tb=short']))"
