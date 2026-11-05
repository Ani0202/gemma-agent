"""Offline local swegemma 0.2.11 evaluation; raw artifacts stay under runs/."""
import argparse
import asyncio
from collections import Counter
from contextvars import ContextVar
import dataclasses
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from eval.kaggle.gold_calibration import patch_subprocess_deps, verify_gold

FIELDS = dict(instance_id='Task ID', repo='Repository', resolved='Harness verdict (bool)',
              exit_code='Verification exit code, or null if not run',
              error='Sanitized failure category; details only in runs/',
              wall_seconds='agent (includes Container A setup), verification, total seconds',
              llm_turns='Harness LLM call count',
              tool_calls='total and per_tool requested (trace); harness total if no trace',
              tool_seconds='Per tool: n, total, max wall seconds call->response (trace timestamps)',
              prompt_tokens='Recorded trace prompt usage, or null',
              completion_tokens='Recorded trace completion usage, or null',
              patch_bytes='UTF-8 size before harness stripping',
              patch_files='All agent diff paths before stripping, including deletions',
              test_files_edited='Harness protected paths and verification test targets',
              stray_files='New files outside package Python source', empty_patch='Blank diff',
              timed_out='Session or verification timeout observed', trace_path='Raw trace path')
BINDINGS = ('swegemma.harness.container_setup', 'swegemma.harness.verification',
            'swegemma.harness.sample_verification', 'swegemma.evaluate',
            'swegemma.harness.agent_runner')


def guard_python(allow=False):
    root = Path('/home/ubuntu/gemma-local/pyimg').resolve()
    if not allow and not all(Path(p).resolve().is_relative_to(root) for p in
                             (sys._base_executable, sys.base_prefix)):
        raise ValueError('Run with /home/ubuntu/gemma-local/venv/bin/python (pyimg base required)')


def assert_dependency_bindings(patched):
    names = set(BINDINGS) | {n for n, m in sys.modules.items()
                            if (n == 'swegemma' or n.startswith('swegemma.'))
                            and hasattr(m, 'install_test_dependencies')}
    bad = [n for n in sorted(names)
           if getattr(sys.modules.get(n), 'install_test_dependencies', None) is not patched]
    if bad:
        raise RuntimeError('Unpatched dependency bindings: ' + ', '.join(bad))


def isolate_host_packages():
    """Keep pyimg system packages; remove swegemma's extra harness-venv .pth leak."""
    from swegemma.sandbox import SubprocessManager
    original = SubprocessManager.start
    if getattr(original, '_image_only', False):
        return

    def start(self):
        sid = original(self)
        for pth in self.sandboxes[sid]['venv'].glob('lib/python*/site-packages/_host_env.pth'):
            pth.unlink()
        return sid
    start._image_only = True
    SubprocessManager.start = start


def sha_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_sha(bundle):
    digest = hashlib.sha256()
    for path in sorted(bundle.rglob('*')):
        if path.is_symlink():
            raise ValueError('Bundle symlinks are unsupported')
        if path.is_file():
            digest.update(path.relative_to(bundle).as_posix().encode() + b'\0')
            digest.update(bytes.fromhex(sha_file(path)))
    return digest.hexdigest()


class Journal:
    """Single writer lock, durable appends, and repair of an interrupted final write."""
    def __init__(self, path, header, force=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = path.open('a+b')
        fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.stream.seek(0)
        lines = self.stream.read().splitlines(keepends=True)
        self.finished = set()
        try:
            if lines and not force:
                old = json.loads(lines[0])
                identity = ('_schema', 'bundle', 'bundle_sha256', 'caps', 'split',
                            'concurrency', 'endpoint', 'models_yaml', 'data_dir')
                if any(old.get(k) != header.get(k) for k in identity):
                    raise ValueError('Results header mismatch; use a new run name or --force-new')
                valid_bytes = len(lines[0])
                for i, line in enumerate(lines[1:], 1):
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        if i == len(lines) - 1 and not line.endswith(b'\n'):
                            self.stream.truncate(valid_bytes)
                            break
                        raise ValueError('Corrupt results record') from None
                    if (not isinstance(row.get('instance_id'), str)
                            or type(row.get('resolved')) is not bool or '_schema' in row):
                        raise ValueError('Invalid task record')
                    self.finished.add(row['instance_id'])
                    valid_bytes += len(line)
                else:
                    if not lines[-1].endswith(b'\n'):
                        self.stream.write(b'\n')
            else:
                self.stream.truncate(0)
                self.append(header)
        except BaseException:
            self.close()
            raise

    def append(self, row):
        self.stream.write((json.dumps(row, allow_nan=False) + '\n').encode())
        self.stream.flush()
        os.fsync(self.stream.fileno())
        if 'instance_id' in row:
            self.finished.add(row['instance_id'])

    def close(self):
        self.stream.close()


def classify_patch(patch, repo, protected=None, test_targets=()):
    """Parse file headers outside hunks, including quoted paths and renames."""
    files, new = set(), set()
    current, added, in_hunk = set(), False, False

    def path_value(raw):
        raw = raw.split('\t', 1)[0]
        value = json.loads(raw) if raw.startswith('"') else raw
        return value[2:] if value.startswith(('a/', 'b/')) else value

    for line in patch.splitlines() + ['diff --git ']:
        if line.startswith('diff --git '):
            files.update(current)
            if added:
                new.update(current)
            current, added, in_hunk = set(), False, False
            match = re.match(r'^diff --git ("a/.*?"|a/.*?) ("b/.*?"|b/.*)$', line)
            if match:
                current.update(path_value(p) for p in match.groups())
        elif line.startswith('@@'):
            in_hunk = True
        elif not in_hunk:
            if line.startswith(('--- ', '+++ ')):
                p = path_value(line[4:])
                if p != '/dev/null':
                    current.add(p)
                elif line.startswith('--- '):
                    added = True
            elif line.startswith('new file mode '):
                added = True
            elif line.startswith(('rename from ', 'rename to ')):
                current.add(path_value(line.split(' ', 2)[2]))
    if protected is None:
        protected = lambda p: bool(re.search(r'(^|/)(tests?/|test_[^/]*\.py$|conftest\.py$)|_test\.py$', p))
    tests = sorted(p for p in files if protected(p) or p in test_targets)
    package = repo.split('/')[-1].replace('-', '_').lower()
    source_roots = (package + '/', 'src/' + package + '/')
    stray = sorted(p for p in new if not (p.endswith('.py') and p.lower().startswith(source_roots)
                                         and p not in tests))
    return dict(patch_bytes=len(patch.encode()), patch_files=sorted(files),
                test_files_edited=tests, stray_files=stray, empty_patch=not patch.strip())


def trace_counts(trace):
    entries = trace.entries if trace else []
    counts = Counter(e.tool_name for e in entries if e.event_type == 'tool_call')
    tokens = {}
    for key in ('prompt_tokens', 'completion_tokens'):
        values = [e.usage[key] for e in entries if e.usage and key in e.usage]
        tokens[key] = sum(values) if values else None
    return dict(counts), tokens, tool_seconds(entries)


def tool_seconds(entries):
    """Per tool name: wall seconds from each tool_call to its tool_response (FIFO per name)."""
    pending, out = {}, {}
    for e in entries:
        if e.event_type == 'tool_call':
            pending.setdefault(e.tool_name, []).append(e.timestamp)
        elif e.event_type == 'tool_response' and pending.get(e.tool_name):
            stat = out.setdefault(e.tool_name, dict(n=0, total=0.0, max=0.0))
            dt = max(0.0, e.timestamp - pending[e.tool_name].pop(0))
            stat['n'] += 1
            stat['total'] = round(stat['total'] + dt, 3)
            stat['max'] = round(max(stat['max'], dt), 3)
    return out


def observe_patch_strip(original, state):
    """Retain the agent's diff before the harness removes protected edits."""
    def strip(patch, *pos, **kw):
        current = state.get(None)
        filtered = original(patch, *pos, **kw)
        if current is not None and current.get('agent_active'):
            if patch != current.get('filtered_patch'):
                current['raw_patch'] = patch
            current['filtered_patch'] = filtered
        return filtered
    return strip


def read_ids(path):
    return {line.strip() for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')}


async def run(args):
    from swegemma.cli import _build_cli_model_registry
    from swegemma.config import EvalConfig
    from swegemma.evaluate import Evaluator
    from swegemma.context import SwegemmaContext
    from swegemma.models import load_tasks
    from swegemma.harness.verification import _is_protected_test_or_config_path
    import yaml

    isolate_host_packages()
    patched = patch_subprocess_deps(args.data_dir)
    assert_dependency_bindings(patched)
    split_ids = read_ids(args.split)
    if not split_ids <= read_ids(ROOT / 'eval/splits/dev.txt'):
        raise ValueError('Only frozen dev IDs are authorized; split contains non-dev IDs')
    selected = split_ids & set(args.ids.split(',')) if args.ids else split_ids
    if not selected:
        raise ValueError('No selected tasks')
    inventory = load_tasks(args.data_dir / 'tasks.jsonl')
    tasks = {t.instance_id: t for t in inventory}
    if len(tasks) != len(inventory):
        raise ValueError('Duplicate inventory IDs')
    if not split_ids <= tasks.keys():
        raise ValueError('Split IDs missing from inventory')
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+', i) for i in split_ids):
        raise ValueError('Unsafe task ID')
    settings = args.bundle / 'eval_config.yaml'
    defaults = (yaml.safe_load(settings.read_text()) or {}).get('evaluation', {}) if settings.exists() else {}
    caps = {key: value if value is not None else defaults.get(key, fallback) for key, value, fallback in
            [('max_tool_calls', args.max_tool_calls, None), ('max_turns', args.max_turns, None),
             ('max_time_minutes', args.session_minutes, 5), ('timeout_seconds', args.command_timeout, 60)]}
    if any(v is not None and (not math.isfinite(v) or v <= 0) for v in caps.values()):
        raise ValueError('Caps must be positive finite numbers')
    if args.models_yaml and not args.models_yaml.is_file():
        raise ValueError('models.yaml missing')
    models = _build_cli_model_registry(args.bundle, args.models_yaml)
    # Force every alias to the one recorded endpoint (including models.yaml aliases).
    for name in models.list_available():
        model = models.get(name)
        model._additional_args['api_base'] = args.endpoint
    header = dict(_schema='agent_eval_v1', fields=FIELDS, bundle=str(args.bundle),
                  bundle_sha256=bundle_sha(args.bundle), git_sha=subprocess.check_output(
                      ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  split=dict(path=str(args.split), sha256=sha_file(args.split)), caps=caps,
                  concurrency=args.concurrency, endpoint=args.endpoint,
                  models_yaml=sha_file(args.models_yaml) if args.models_yaml else None,
                  data_dir=str(args.data_dir), created_utc=datetime.now(timezone.utc).isoformat())
    journal = Journal(ROOT / 'results' / f'{args.run_name}.jsonl', header, args.force_new)
    if not journal.finished <= split_ids:
        journal.close()
        raise ValueError('Resume records contain IDs outside the split')
    raw_dir = ROOT / 'runs' / args.run_name
    raw_dir.mkdir(parents=True, exist_ok=True)
    logging.getLogger().addHandler(logging.FileHandler(raw_dir / 'harness.log'))
    config = EvalConfig(tasks_path=args.data_dir / 'tasks.jsonl', snapshots_dir=args.data_dir / 'snapshots',
                        wheels_dir=args.data_dir / 'wheels', results_dir=raw_dir,
                        submission_dir=args.bundle, models=models, sandbox='subprocess',
                        concurrency=args.concurrency, display_mode='quiet', **caps)
    import swegemma.evaluate as evaluate_module
    original_verify = evaluate_module.verify_task
    phase_times = ContextVar('phase_times')
    import swegemma.harness.verification as verification_module
    original_strip = verification_module.strip_protected_files_from_patch
    verification_module.strip_protected_files_from_patch = observe_patch_strip(original_strip, phase_times)

    async def timed_verify(*pos, **kw):
        start = time.perf_counter()
        try:
            return await original_verify(*pos, **kw)
        finally:
            phase_times.get()['verification'] = time.perf_counter() - start
    evaluate_module.verify_task = timed_verify

    class LocalEvaluator(Evaluator):
        agent_seconds = 0.0
        patch = ''
        trace = None

        def _hydrate_task_from_secret(self, task):
            return task  # Explicit inventory only; no implicit sibling secret discovery.

        def _get_secret_bundle_data(self):
            return {}, {}, None

        async def _run_agent_sandbox(self, task, *pos, **kw):
            safe = dataclasses.replace(task, patch='', test_patch='', FAIL_TO_PASS=(), PASS_TO_PASS=())
            kw['context'].task = safe
            start = time.perf_counter()
            phase_times.get()['agent_active'] = True
            try:
                self.patch, error, self.trace = await super()._run_agent_sandbox(safe, *pos, **kw)
                self.agent_error = error or ''
                return self.patch, error, self.trace
            finally:
                self.agent_seconds = time.perf_counter() - start
                phase_times.get()['agent_active'] = False

    async def one(iid):
        times = dict(verification=0.0)
        phase_times.set(times)
        evaluator = LocalEvaluator(config)
        task = dataclasses.replace(tasks[iid], patch='')
        context = SwegemmaContext(docker_manager=evaluator.docker, container_id='',
                                 problem_statement=task.problem_statement, repo=task.repo,
                                 task=dataclasses.replace(task, test_patch='', FAIL_TO_PASS=(), PASS_TO_PASS=()),
                                 budget=config.budget, harness=config.harness)
        start = time.perf_counter()
        result, error, code, resolved = None, None, None, False
        try:
            assert_dependency_bindings(patched)
            result = await evaluator.evaluate_task(task, context=context)
            resolved, code = result.resolved, result.test_exit_code
            error = 'Harness task failure (see raw artifacts)' if result.error else None
        except Exception as exc:
            logging.exception('Task failed: %s', iid)
            error = f'Evaluation exception ({type(exc).__name__})'
        finally:
            evaluator.docker.cleanup_all()
        total = time.perf_counter() - start
        patch = times.get('raw_patch', result.agent_patch if result else evaluator.patch)
        task_dir = raw_dir / iid
        task_dir.mkdir(exist_ok=True)
        (task_dir / 'agent.patch').write_text(patch)
        (task_dir / 'output.json').write_text(json.dumps(result.model_dump(exclude={'trace'}) if result
                                                       else dict(error=error), default=str))
        trace = evaluator.trace
        trace_path = task_dir / 'trace.json'
        trace_path.write_text(json.dumps(trace.to_dict(format='legacy') if trace else {}, default=str))
        per_tool, tokens, per_tool_seconds = trace_counts(trace)
        raw_error = result.error or '' if result else error or ''
        row = dict(instance_id=iid, repo=task.repo, resolved=resolved, exit_code=code, error=error,
                   wall_seconds=dict(agent=evaluator.agent_seconds,
                                     verification=times['verification'],
                                     total=total), llm_turns=context.llm_calls_used,
                   tool_calls=dict(total=sum(per_tool.values()) if trace else context.tool_calls_used,
                                   per_tool=per_tool), tool_seconds=per_tool_seconds, **tokens,
                   **classify_patch(patch, task.repo, _is_protected_test_or_config_path, task.test_files),
                   timed_out=bool(re.search(r'timeout|timed out', raw_error + ' ' +
                                           getattr(evaluator, 'agent_error', ''), re.I)) or code == 124,
                   trace_path=str(trace_path.relative_to(ROOT)))
        journal.append(row)
        print(f'{iid}: resolved={resolved}', flush=True)

    try:
        if not args.skip_selfcheck:
            clean = split_ids & read_ids(ROOT / 'eval/splits/clean.txt')
            check = args.selfcheck_ids.split(',') if args.selfcheck_ids else sorted(clean)[:2]
            if len(check) != 2 or len(set(check)) != 2 or not set(check) <= clean:
                raise ValueError('Self-check requires two distinct clean IDs from the split')
            for iid in check:
                if not tasks[iid].patch.strip():
                    raise ValueError('Self-check gold patch missing')
                result = await verify_gold(tasks[iid], tasks[iid].patch, args.data_dir, 'subprocess')
                (raw_dir / f'selfcheck-{iid}.json').write_text(json.dumps(result.model_dump(exclude={'trace'}), default=str))
                if result.resolved is not True:
                    raise RuntimeError('Gold self-check unresolved; see runs artifacts')
        queue = asyncio.Queue()
        for iid in sorted(selected - journal.finished):
            queue.put_nowait(iid)
        async def worker():
            while not queue.empty():
                await one(queue.get_nowait())
        await asyncio.gather(*(worker() for _ in range(args.concurrency)))
    finally:
        evaluate_module.verify_task = original_verify
        verification_module.strip_protected_files_from_patch = original_strip
        journal.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'data-dir', 'split'):
        parser.add_argument('--' + name, type=Path, required=name != 'data-dir', default=Path('data/raw'))
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--concurrency', type=int, required=True)
    for name in ('ids', 'selfcheck-ids'):
        parser.add_argument('--' + name)
    for name in ('max-tool-calls', 'max-turns', 'command-timeout'):
        parser.add_argument('--' + name, type=int)
    parser.add_argument('--session-minutes', type=float)
    parser.add_argument('--endpoint', default=os.environ.get('LOCAL_INFERENCE_URL') or
                        os.environ.get('OPENAI_BASE_URL') or 'http://localhost:8000/v1')
    parser.add_argument('--models-yaml', type=Path)
    for name in ('skip-selfcheck', 'force-new', 'allow-foreign-python'):
        parser.add_argument('--' + name, action='store_true')
    args = parser.parse_args(argv)
    guard_python(args.allow_foreign_python)
    if urlparse(args.endpoint).hostname not in {'localhost', '127.0.0.1', '::1'}:
        parser.error('Only localhost inference endpoints are permitted')
    if args.concurrency < 1 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', args.run_name):
        parser.error('Positive concurrency and a safe run name required')
    for name in ('bundle', 'data_dir', 'split'):
        setattr(args, name, getattr(args, name).resolve())
    if not (args.bundle / 'agent.yaml').is_file():
        parser.error('Bundle must contain agent.yaml')
    os.environ.update(LOCAL_INFERENCE_URL=args.endpoint, OPENAI_BASE_URL=args.endpoint,
                      MODEL_PROXY_URL=args.endpoint, LITELLM_API_BASE=args.endpoint,
                      PIP_NO_INDEX='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      LITELLM_LOCAL_MODEL_COST_MAP='True', OTEL_SDK_DISABLED='true',
                      LITELLM_TELEMETRY='False', TMPDIR='/tmp')
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
