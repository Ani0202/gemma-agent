#!/usr/bin/env bash
# Host test of codex/sandbox-limits round 3 (full eval/tests suite, offline).
cd /home/ubuntu/work/gemma-wt/codex-sandbox-limits || exit 1
SP=$(ls -d /home/ubuntu/gemma-local/pyimg/cpython-3.13*/lib/python3.13/site-packages | head -1)
/home/ubuntu/gemma-local/venv/bin/python3 -c "import sys; sys.path.append('$SP'); import pytest; sys.exit(pytest.main(['-q','-p','no:cacheprovider','eval/tests','--tb=line','--maxfail=20']))" 2>&1 | tail -30
