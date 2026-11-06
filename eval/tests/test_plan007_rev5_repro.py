"""Review 20261106T071306 exact reproducers must all be OK (rev-5 freeze d4cdf0f0)."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_rev5_review_reproducers_all_ok():
    cp = subprocess.run([sys.executable, '-I', str(ROOT / 'eval' / 'plan007_rev5_repro.py')],
                        cwd=ROOT, capture_output=True, text=True)
    lines = cp.stdout.splitlines()
    assert cp.returncode == 0 and len(lines) == 32
    assert all(ln.startswith('OK  ') for ln in lines), [ln for ln in lines if not ln.startswith('OK')]
