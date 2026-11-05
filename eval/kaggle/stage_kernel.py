"""Embed the shared scorer environment in Kaggle's single-file script artifact."""
from pathlib import Path
import sys


def stage_kernel(destination):
    here = Path(__file__).resolve().parent
    source = (here / 'gold_calibration.py').read_text()
    shared = (here.parent / 'sandbox_env.py').read_text()
    start = source.index('# BEGIN SHARED ENV IMPORT')
    end = source.index('# END SHARED ENV IMPORT') + len('# END SHARED ENV IMPORT')
    embedded = ("import types\n"
                "_shared_env = types.ModuleType('sandbox_env')\n"
                "_shared_env.__file__ = __file__\n"
                f"exec(compile({shared!r}, 'sandbox_env.py', 'exec'), _shared_env.__dict__)\n"
                "patch_subprocess_deps = _shared_env.patch_subprocess_deps\n"
                "setup_scorer_env = _shared_env.setup_scorer_env\n"
                "gold_artifact_dir = _shared_env.gold_artifact_dir\n")
    Path(destination).write_text(source[:start] + embedded + source[end:])


if __name__ == '__main__':
    stage_kernel(sys.argv[1])
