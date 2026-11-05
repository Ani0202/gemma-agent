#!/usr/bin/env bash
# Full eval/tests on main (host).
cd /home/ubuntu/work/gemma || exit 1
SP=$(ls -d /home/ubuntu/gemma-local/pyimg/cpython-3.13*/lib/python3.13/site-packages | head -1)
/home/ubuntu/gemma-local/venv/bin/python3 -c "import sys; sys.path.append('$SP'); import pytest; sys.exit(pytest.main(['-q','-p','no:cacheprovider','eval/tests','--tb=short']))"
