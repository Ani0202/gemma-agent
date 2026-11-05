"""Stage a CPU-only Kaggle kernel that writes a byte-identical bundle zip to /kaggle/working/submission.zip.
Usage: python3 eval/kaggle/submit_kernel/stage.py <zip> <owner/slug> <stage_dir>
Code-competition submissions are notebook outputs (CreateSubmission with -f returns 400). The zip is embedded
base64 (bundles are KB-sized); the kernel re-checks the sha256 and fails loudly on mismatch."""
import base64, hashlib, json, sys
from pathlib import Path
zp, kid, stage = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
data = zp.read_bytes()
if len(data) > 5_000_000:
    sys.exit('zip too large to embed; use a dataset source instead')
sha = hashlib.sha256(data).hexdigest()
stage.mkdir(parents=True, exist_ok=True)
(stage / 'make_submission.py').write_text(f'''import base64, hashlib, pathlib
EXPECTED = "{sha}"
data = base64.b64decode("{base64.b64encode(data).decode()}")
got = hashlib.sha256(data).hexdigest()
assert got == EXPECTED, ("sha256 mismatch", got, EXPECTED)
out = pathlib.Path("/kaggle/working/submission.zip")
out.write_bytes(data)
print("wrote", out, len(data), "bytes sha256", got)
''')
(stage / 'kernel-metadata.json').write_text(json.dumps(dict(
    id=kid, title=kid.split('/')[1], code_file='make_submission.py', language='python', kernel_type='script',
    is_private=True, enable_gpu=False, enable_tpu=False, enable_internet=False, dataset_sources=[],
    competition_sources=['gemma-4-developer-agent'], kernel_sources=[], model_sources=[]), indent=2) + '\n')
print(sha, stage)
