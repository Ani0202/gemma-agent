#!/usr/bin/env bash
# Full eval/tests on branch codex/sandbox-env-docker-order (host; memguard oom_score_adj test needs host env).
cd /home/ubuntu/work/gemma-wt/codex-sandbox-env-docker-order || exit 1
SP=$(ls -d /home/ubuntu/gemma-local/pyimg/cpython-3.13*/lib/python3.13/site-packages | head -1)
/home/ubuntu/gemma-local/venv/bin/python3 -c "import sys; sys.path.append('$SP'); import pytest; sys.exit(pytest.main(['-q','-p','no:cacheprovider','eval/tests','--tb=short']))"
