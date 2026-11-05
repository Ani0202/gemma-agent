"""Offline local swegemma 0.2.11 evaluation; raw artifacts stay under runs/."""
import argparse
import ast
import importlib.metadata
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
from eval.kaggle.gold_calibration import verify_gold
from eval.sandbox_env import (isolate_host_packages, patch_subprocess_deps,
                              setup_scorer_env, setup_script_identity, command_metrics)
from eval.tool_timing import ToolTiming, current_timing, install_harness_timing

FIELDS = dict(instance_id='Task ID', repo='Repository', resolved='Harness verdict (bool)',
              exit_code='Verification exit code, or null if not run',
              error='Sanitized failure category; details only in runs/',
              wall_seconds='agent (includes Container A setup), verification, total seconds',
              llm_turns='Harness LLM call count',
              tool_calls='total and per_tool requested (trace); harness total if no trace',
              tool_seconds='Per tool: n, total, max monotonic execution seconds',
              tool_calls_timed='Calls measured at ADK execution callbacks',
              tool_seconds_unmatched='Calls missing a timing boundary',
              cmd_timeouts='Command timeouts, including recovered timeouts',
              sandbox='bwrap or explicitly allowed none',
              leak_suspect='Sensitive tokens appeared in tool arguments',
              leak_hits='Matched sensitive tokens only', diag_error='Diagnostic exception category',
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
                identity = (old.keys() | header.keys()) - {'created_utc', 'provenance'}
                diff = {k: {'old': old.get(k), 'new': header.get(k)}
                        for k in sorted(identity) if old.get(k) != header.get(k)}
                if diff:
                    raise ValueError('Results header mismatch; use --force-new-out or a new run name: '
                                     + json.dumps(diff, default=str, sort_keys=True))
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
        value = decode_git_path(raw) if raw.startswith('"') else raw
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
    return dict(counts), tokens, {}


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


def decode_git_path(raw):
    # Git C-quotes UTF-8 bytes using octal escapes, which JSON doesn't accept.
    # literal_eval on bytes understands both octal and ordinary C escapes.
    escaped = ''.join(c if ord(c) < 128 else ''.join(f'\\{b:03o}' for b in c.encode())
                      for c in raw)
    return ast.literal_eval('b' + escaped).decode('utf-8', errors='surrogateescape')


def validate_inventory_ids(path):
    seen = set()
    with path.open() as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            iid = json.loads(line)['instance_id']
            if iid in seen:
                raise ValueError(f'Duplicate inventory IDs at line {number}')
            seen.add(iid)


RUNNER_SOURCE_DIR = 'eval'


def runner_source_sha():
    """Content hash of the runner implementation as it is on disk (tracked or untracked,
    committed or not). Generated artifacts (results, runs, caches) live outside eval/ or are
    not .py, so writing the journal never changes the identity; tests are excluded."""
    listing = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others',
                                       '--exclude-standard', '--', RUNNER_SOURCE_DIR], cwd=ROOT)
    files = sorted({f for f in listing.decode('utf-8', 'surrogateescape').split('\0')
                    if f.endswith('.py') and not f.startswith(f'{RUNNER_SOURCE_DIR}/tests/')})
    digest = hashlib.sha256()
    for rel in files:
        path = ROOT / rel
        if path.is_file():  # a deleted tracked file drops out of the hash
            digest.update(rel.encode('utf-8', 'surrogateescape') + b'\0'
                          + hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def runner_revision():
    # Identity is the source content hash. The commit SHA/dirty flag are provenance only:
    # HEAD moves on every ops commit, and the default journal itself dirties the tree.
    return dict(runner_source_sha256=runner_source_sha(),
                provenance=dict(git_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                                                cwd=ROOT, text=True).strip(),
                                git_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'],
                                                                       cwd=ROOT))))


def wheels_listing_sha(path):
    listing = []
    if path:
        for p in sorted(Path(path).rglob('*')):
            listing.append((p.relative_to(path).as_posix(), p.stat().st_size,
                            str(p.resolve()) if p.is_symlink() else None))
    return hashlib.sha256(json.dumps(listing, sort_keys=True).encode()).hexdigest()


def config_snapshot(value):
    if dataclasses.is_dataclass(value):
        return {f.name: config_snapshot(getattr(value, f.name)) for f in dataclasses.fields(value)
                if f.name != 'models'}
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    if isinstance(value, dict):
        return {k: config_snapshot(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        values = [config_snapshot(v) for v in value]
        return sorted(values) if isinstance(value, (set, frozenset)) else values
    if isinstance(value, Path):
        return str(value)
    return value


def resolve_caps(defaults, args):
    """Precedence: CLI flag > flat bundle key > nested bundle key (left to swegemma) > runner fallback."""
    def nested(section, key):
        value = defaults.get(section)
        return value.get(key) if isinstance(value, dict) else None

    caps = {}
    for key, value, fallback, nested_value in [
            ('max_tool_calls', args.max_tool_calls, None, None),
            ('max_turns', args.max_turns, None, None),
            ('max_time_minutes', args.session_minutes, 5, nested('budget', 'time_minutes')),
            ('timeout_seconds', args.command_timeout, 60, nested('harness', 'command_timeout_seconds'))]:
        if value is None:
            value = defaults.get(key)
        if value is None and nested_value is None:
            value = fallback
        caps[key] = value
    return caps


def validate_caps(values):
    for v in values:
        if v is None:
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError(f'Caps must be positive finite numbers (got {v!r})')


def validate_effective_caps(config):
    """Nested bundle caps bypass resolve_caps (None there), so validate the merged values."""
    budget, harness = getattr(config, 'budget', None), getattr(config, 'harness', None)
    validate_caps([getattr(config, 'max_time_minutes', None), getattr(config, 'timeout_seconds', None),
                   getattr(budget, 'time_minutes', None), getattr(budget, 'cost_usd', None),
                   getattr(harness, 'command_timeout_seconds', None)])
    counts = [getattr(config, k, None) for k in ('max_tool_calls', 'max_turns', 'max_llm_calls')]
    counts += [getattr(budget, k, None) for k in ('tool_calls', 'turns', 'total_tokens')]
    validate_caps(counts)
    for v in counts:
        if v is not None and not isinstance(v, int):
            raise ValueError(f'Count caps must be positive integers (got {v!r})')


def build_config(defaults, args, models, raw_dir, caps):
    from swegemma import config as sc
    from swegemma.budget import EvaluationBudget, HarnessLimits
    names = {f.name for f in dataclasses.fields(sc.EvalConfig)}
    for key in defaults.keys() - names:
        logging.warning('Unknown EvalConfig key: %s', key)
    options = {k: v for k, v in defaults.items() if k in names}
    types = dict(budget=EvaluationBudget, harness=HarnessLimits,
                 limits=sc.SubmissionLimits, generation_constraints=sc.GenerationConstraints,
                 context_cache_config=sc.ContextCacheConfig,
                 events_compaction_config=sc.EventsCompactionConfig,
                 adapter_manifest=sc.AdapterManifest)
    for key, cls in types.items():
        if isinstance(options.get(key), dict):
            options[key] = cls(**options[key])
    paths = dict(tasks_path=args.data_dir / 'tasks.jsonl', snapshots_dir=args.data_dir / 'snapshots',
                 wheels_dir=args.data_dir / 'wheels', results_dir=raw_dir, submission_dir=args.bundle)
    # Explicit CLI runtime settings own these fields. Other bundle fields pass through.
    options.update(paths, models=models, sandbox='subprocess', concurrency=args.concurrency,
                   display_mode='quiet', **caps)
    for key, fallback in [('graph_dir', 'graphs'), ('embeddings_dir', 'embeddings')]:
        path = Path(options.get(key, fallback))
        options[key] = str((path if path.is_absolute() else args.data_dir / path).resolve())
    return sc.EvalConfig(**options)


def task_diagnostics(trace, patch, repo, protected, test_files, data_dir):
    out = dict(per_tool={}, prompt_tokens=None, completion_tokens=None,
               patch_bytes=len(patch.encode()), patch_files=[], test_files_edited=[],
               stray_files=[], empty_patch=not patch.strip(), leak_suspect=False, leak_hits=[],
               diag_error=None)
    errors = []
    try:
        out['per_tool'], tokens, _ = trace_counts(trace)
        out.update(tokens)
    except Exception as exc:
        errors.append(type(exc).__name__)
    try:
        out.update(classify_patch(patch, repo, protected, test_files))
    except Exception as exc:
        errors.append(type(exc).__name__)
    try:
        tokens = (str(ROOT), str(data_dir), 'tasks.jsonl', 'test_patch', 'FAIL_TO_PASS')
        arguments = [json.dumps(e.tool_args, ensure_ascii=False) for e in trace.entries
                     if e.event_type == 'tool_call'] if trace else []
        out['leak_hits'] = [t for t in dict.fromkeys(tokens) if any(t in a for a in arguments)]
        out['leak_suspect'] = bool(out['leak_hits'])
    except Exception as exc:
        errors.append(type(exc).__name__)
    out['diag_error'] = ','.join(errors) or None
    return out


async def run(args):
    from swegemma.cli import _build_cli_model_registry
    from swegemma.config import EvalConfig
    from swegemma.evaluate import Evaluator
    from swegemma.context import SwegemmaContext
    from swegemma.models import load_tasks
    from swegemma.harness.verification import _is_protected_test_or_config_path
    import yaml

    split_ids = read_ids(args.split)
    if not split_ids <= read_ids(ROOT / 'eval/splits/dev.txt'):
        raise ValueError('Only frozen dev IDs are authorized; split contains non-dev IDs')
    selected = split_ids & set(args.ids.split(',')) if args.ids else split_ids
    if not selected:
        raise ValueError('No selected tasks')
    validate_inventory_ids(args.data_dir / 'tasks.jsonl')
    inventory = load_tasks(args.data_dir / 'tasks.jsonl')
    tasks = {t.instance_id: t for t in inventory}
    if not split_ids <= tasks.keys():
        raise ValueError('Split IDs missing from inventory')
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+', i) for i in split_ids):
        raise ValueError('Unsafe task ID')
    settings = args.bundle / 'eval_config.yaml'
    defaults = (yaml.safe_load(settings.read_text()) or {}).get('evaluation', {}) if settings.exists() else {}
    caps = resolve_caps(defaults, args)
    validate_caps(caps.values())
    if args.models_yaml and not args.models_yaml.is_file():
        raise ValueError('models.yaml missing')
    models = _build_cli_model_registry(args.bundle, args.models_yaml)
    # Force every alias to the one recorded endpoint (including models.yaml aliases).
    for name in models.list_available():
        model = models.get(name)
        model._additional_args['api_base'] = args.endpoint
    raw_dir = args.out / args.run_name
    raw_dir.mkdir(parents=True, exist_ok=True)
    config = build_config(defaults, args, models, raw_dir, caps)
    validate_effective_caps(config)
    environment = setup_scorer_env(args.data_dir, out_dir=args.out, repo_root=ROOT,
                                   allow_unsandboxed=args.allow_unsandboxed)
    patched = environment['patched']
    assert_dependency_bindings(patched)
    header = dict(_schema='agent_eval_v2', fields=FIELDS, bundle=str(args.bundle),
                  bundle_sha256=bundle_sha(args.bundle), **runner_revision(),
                  setup_script=setup_script_identity(args.data_dir),
                  tasks_sha256=sha_file(args.data_dir / 'tasks.jsonl'),
                  split=dict(path=str(args.split), sha256=sha_file(args.split)), caps=caps,
                  versions={name: importlib.metadata.version(name) for name in
                            ('swegemma', 'adk_submission', 'google-adk', 'litellm')},
                  python_version=sys.version, wheels_listing_sha256=wheels_listing_sha(environment['wheels_dir']),
                  sandbox=environment['sandbox'], bwrap_argv_template=environment['bwrap_argv_template'],
                  effective_config=config_snapshot(config),
                  concurrency=args.concurrency, endpoint=args.endpoint,
                  models_yaml=sha_file(args.models_yaml) if args.models_yaml else None,
                  data_dir=str(args.data_dir), created_utc=datetime.now(timezone.utc).isoformat())
    journal_path = (args.out / f'{args.run_name}.jsonl' if args.out_explicit else
                    ROOT / 'results' / f'{args.run_name}.jsonl')
    if args.force_new_out and journal_path.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        journal_path.rename(journal_path.with_name(journal_path.stem + '-' + stamp + '.jsonl'))
        raw_dir.rename(raw_dir.with_name(raw_dir.name + '-' + stamp))
        raw_dir.mkdir()
    journal = Journal(journal_path, header, args.force_new)
    if not journal.finished <= split_ids:
        journal.close()
        raise ValueError('Resume records contain IDs outside the split')
    file_handler = logging.FileHandler(raw_dir / 'harness.log')
    logging.getLogger().addHandler(file_handler)
    restore_timing = install_harness_timing()
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
        command_metrics.set(times)
        timing = ToolTiming()
        current_timing.set(timing)
        evaluator = LocalEvaluator(config)
        task = dataclasses.replace(tasks[iid], patch='')
        context = SwegemmaContext(docker_manager=evaluator.docker, container_id='',
                                 problem_statement=task.problem_statement, repo=task.repo,
                                 task=dataclasses.replace(task, test_patch='', FAIL_TO_PASS=(), PASS_TO_PASS=()),
                                 budget=config.budget, harness=config.harness,
                                 graph_dir=config.graph_dir, embeddings_dir=config.embeddings_dir)
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
        trace = evaluator.trace
        trace_path = task_dir / 'trace.json'
        artifact_error = None
        try:
            task_dir.mkdir(exist_ok=True)
            (task_dir / 'agent.patch').write_text(patch)
            (task_dir / 'output.json').write_text(json.dumps(result.model_dump(exclude={'trace'}) if result
                                                           else dict(error=error), default=str))
            trace_path.write_text(json.dumps(trace.to_dict(format='legacy') if trace else {}, default=str))
        except Exception as exc:
            logging.exception('Artifact diagnostics failed: %s', iid)
            artifact_error = type(exc).__name__
        diagnostics = task_diagnostics(trace, patch, task.repo,
                                       _is_protected_test_or_config_path, task.test_files,
                                       args.data_dir)
        if artifact_error:
            diagnostics['diag_error'] = ','.join(filter(None, [diagnostics['diag_error'], artifact_error]))
        per_tool = diagnostics.pop('per_tool')
        raw_error = result.error or '' if result else error or ''
        row = dict(instance_id=iid, repo=task.repo, resolved=resolved, exit_code=code, error=error,
                   wall_seconds=dict(agent=evaluator.agent_seconds,
                                     verification=times['verification'],
                                     total=total), llm_turns=context.llm_calls_used,
                   tool_calls=dict(total=sum(per_tool.values()) if trace else context.tool_calls_used,
                                   per_tool=per_tool), **timing.metrics(), **diagnostics,
                   sandbox=environment['sandbox'], cmd_timeouts=times.get('cmd_timeouts', 0),
                   timed_out=bool(re.search(r'timeout|timed out', raw_error + ' ' +
                                           getattr(evaluator, 'agent_error', ''), re.I)) or code == 124,
                   trace_path=os.path.relpath(trace_path, ROOT))
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
                result = await verify_gold(tasks[iid], tasks[iid].patch, args.data_dir, 'subprocess', out_dir=raw_dir)
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
        restore_timing()
        journal.close()
        logging.getLogger().removeHandler(file_handler)
        file_handler.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'data-dir', 'split'):
        parser.add_argument('--' + name, type=Path, required=name != 'data-dir', default=Path('data/raw'))
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--out', type=Path, help='Artifact and journal directory (default: runs/)')
    parser.add_argument('--concurrency', type=int, required=True)
    for name in ('ids', 'selfcheck-ids'):
        parser.add_argument('--' + name)
    for name in ('max-tool-calls', 'max-turns', 'command-timeout'):
        parser.add_argument('--' + name, type=int)
    parser.add_argument('--session-minutes', type=float)
    parser.add_argument('--endpoint', default=os.environ.get('LOCAL_INFERENCE_URL') or
                        os.environ.get('OPENAI_BASE_URL') or 'http://localhost:8000/v1')
    parser.add_argument('--models-yaml', type=Path)
    for name in ('skip-selfcheck', 'force-new', 'force-new-out', 'allow-foreign-python', 'allow-unsandboxed'):
        parser.add_argument('--' + name, action='store_true')
    args = parser.parse_args(argv)
    args.out_explicit = args.out is not None
    args.out = (args.out or ROOT / 'runs').resolve()
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
