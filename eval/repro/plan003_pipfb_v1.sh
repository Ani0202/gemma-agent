#!/usr/bin/env bash
# Plan 003 repro. Usage: pipfb.sh <outdir>
set -u
O=$1; mkdir -p $O; cd $O
PY=/home/ubuntu/gemma-local/pyimg/cpython-3.13.18-linux-x86_64-gnu/bin/python3.13
[ -x $PY ] || PY=$(ls /home/ubuntu/gemma-local/pyimg/cpython-3.13*/bin/python3.13 | head -1)
W=/home/ubuntu/work/gemma/data/raw/wheels
t(){ local s=$(date +%s.%N); "$@" >/dev/null 2>&1; local rc=$?; echo "$(python3 -c "print(round($(date +%s.%N)-$s,1))") rc=$rc"; }
for be in poetry pdm; do
  rm -rf venv-$be proj-$be; $PY -m venv venv-$be; mkdir -p proj-$be/pkg$be; touch proj-$be/pkg$be/__init__.py
  if [ $be = poetry ]; then printf '[tool.poetry]\nname="pkgpoetry"\nversion="0.1"\ndescription=""\nauthors=[]\n[build-system]\nrequires=["poetry-core>=1.0.0"]\nbuild-backend="poetry.core.masonry.api"\n' > proj-$be/pyproject.toml
  else printf '[project]\nname="pkgpdm"\nversion="0.1"\n[build-system]\nrequires=["pdm-backend"]\nbuild-backend="pdm.backend"\n' > proj-$be/pyproject.toml; fi
  P=venv-$be/bin/python
  echo "$be offline: $(t env -u PIP_INDEX_URL $P -m pip install --no-index --find-links=$W --no-build-isolation --no-deps -e proj-$be)"
  echo "$be fallback-hang: $(t env PIP_INDEX_URL=http://10.255.255.1/simple $P -m pip install --no-deps -e proj-$be)"
  echo "$be fallback-dns: $(t env PIP_INDEX_URL=http://pypi.invalid/simple $P -m pip install --no-deps -e proj-$be)"
  $P -m pip install -q --no-index --find-links=$W poetry-core pdm-backend editables >/dev/null 2>&1
  echo "$be offline-after-backend: $(t $P -m pip install --no-index --find-links=$W --no-build-isolation --no-deps -e proj-$be)"
done
