"""Offline plan-010 acceptance tests, with synthetic runs only.

Run with the image interpreter and environment documented in README_AGENT_EVAL.md:
python3 -m pytest eval/tests -q
"""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'eval'))
import plan008_metrics as m


def write_json(path, value):
    Path(path).write_text(json.dumps(value))


class Experiment:
    def __init__(self, tmp_path, monkeypatch):
        self.root = tmp_path
        self.ids = [f'repo__{i:02}' for i in range(33)]
        ids = tmp_path / 'ids.txt'
        ids.write_text('\n'.join(self.ids) + '\n')
        screened = tmp_path / 'screened.txt'
        screened.write_text('')
        monkeypatch.setattr(m.base, 'ARM_IDS', str(ids))
        monkeypatch.setattr(m.base, 'SCREENED_IDS', str(screened))
        bundles = tmp_path / 'bundles'
        for bundle in ('v012', 'v014'):
            directory = bundles / bundle
            directory.mkdir(parents=True)
            (directory / 'MANIFEST.md').write_text('zip sha256: ' + 'd' * 64 + '\n')
        monkeypatch.setattr(m, 'BUNDLES_ROOT', bundles)
        self.classifiers = {}
        self.dirs = {}
        self.options = {}
        for name, bundle, resolved, timeouts, empties in (
                ('arm1', 'v012', 4, 4, 12), ('arm3', 'v012', 10, 21, 18), ('arm4', 'v014', 8, 16, 18)):
            self.dirs[name] = []
            for event, subset in (('smoke', self.ids[:2]), ('main', self.ids[2:])):
                directory = str(tmp_path / (name + '-' + event))
                self.dirs[name].append(directory)
                self.make_run(directory, subset, resolved, timeouts, empties)
            identity = tmp_path / (name + '-identity.json')
            write_json(identity, dict(records=[dict(event=event, bundles={bundle: dict(
                **{'pass': True}, zip_ok=True, content_ok=True, zip_sha256='d' * 64,
                manifest_zip_sha256='d' * 64, agent_yaml_sha256='a' * 64,
                zip_path='dist/31b-' + bundle + '.zip', only_in_zip=[], only_in_dir=[],
                byte_mismatch=[], duplicate_members=[])}) for event in ('smoke', 'main', 'chunk1')]))
            smoke, main = self.dirs[name]
            options = dict(identity_json=str(identity), bundle=bundle,
                           transports={smoke: 'b' * 64, main: 'b' * 64},
                           push_events={smoke: 'smoke', main: 'main'})
            smoke_json = tmp_path / (name + '-smoke.json')
            write_json(smoke_json, m.arm3smoke_metrics(smoke, self.classifiers[smoke][0], **{
                k: {smoke: v[smoke]} if isinstance(v, dict) else v for k, v in options.items()}))
            self.options[name] = dict(options, smoke_json=str(smoke_json))
        monkeypatch.setattr(m.base, 'PARTS', [
            (event, str(Path(d) / 'timing.jsonl'), *self.classifiers[d])
            for event, d in zip(('smoke', 'main'), self.dirs['arm1'])])
        self.base_json = str(tmp_path / 'base.json')
        self.bind_base()

    def make_run(self, directory, ids, resolved=8, timeouts=16, empties=18):
        directory = Path(directory)
        directory.mkdir()
        rows = [dict(instance_id=i, repo='repo', resolved=self.ids.index(i) < resolved,
                     timed_out=self.ids.index(i) < timeouts, agent_timeout_fired=False,
                     verified_patch_bytes=0 if self.ids.index(i) < empties else 1,
                     agent_clock_seconds=200, finalization_seconds=10, patch_submitted=False,
                     test_files_edited=[], stray_files=[], wall_seconds=dict(total=300, verification=20),
                     sandbox_setup_seconds=80) for i in ids]
        header = dict(_schema='synthetic', agent_yaml_sha256='a' * 64, bundle_sha256='b' * 64,
                      kernel_code={'agent_path_sha256': 'c' * 64, 'verification_path_sha256': 'e' * 64})
        timing = directory / 'timing.jsonl'
        timing.write_text('\n'.join(map(json.dumps, [header, *rows, {'_vllm': {'startup_seconds': 1}}])) + '\n')
        paths = []
        for filename, sha in (('d4.json', m.base.D4_SHA), ('a2.json', m.base.A2_SHA)):
            path = directory / filename
            write_json(path, dict(classifier_sha256=sha, input_sha256=m.base.sha(timing),
                                 rows=[dict(instance_id=i, h=None, known_diag=False) for i in ids]))
            paths.append(str(path))
        self.classifiers[str(directory)] = paths
        for iid in ids:
            trace = directory / 'runs' / iid / 'trace.json'
            trace.parent.mkdir(parents=True)
            write_json(trace, dict(summary={'context_overflow': False}, entries=[
                dict(author=m.ROOT, type='thinking', content='synthetic thought')] * 3))

    def bind_base(self):
        result = m.arm3_metrics('arm1', self.dirs['arm3'], [], self.classifiers, **self.options['arm3'])
        assert result['decision'] == 'ON-BETTER-VETOED'
        write_json(self.base_json, result)

    def mutate(self, arm, fn):
        for directory in self.dirs[arm]:
            timing = Path(directory) / 'timing.jsonl'
            documents = [json.loads(line) for line in timing.read_text().splitlines()]
            for doc in documents:
                if 'instance_id' in doc:
                    fn(doc, self.ids.index(doc['instance_id']))
            timing.write_text('\n'.join(map(json.dumps, documents)) + '\n')
            for classifier in self.classifiers[directory]:
                doc = json.loads(Path(classifier).read_text())
                doc['input_sha256'] = m.base.sha(timing)
                doc['rows'] = [row for row in doc['rows'] if any(d.get('instance_id') == row['instance_id'] for d in documents)]
                write_json(classifier, doc)

    def trace(self, arm, index, entries, **extra):
        directory = self.dirs[arm][index >= 2]
        path = Path(directory) / 'runs' / self.ids[index] / 'trace.json'
        write_json(path, dict(entries=entries, **extra))

    def result(self):
        return m.arm4_metrics(self.dirs['arm4'], self.dirs['arm3'], self.dirs['arm1'],
                              self.classifiers, base_json=self.base_json, **self.options['arm4'])

    def argv(self, explicit_classifiers=True):
        options = self.options['arm4']
        out = ['metrics', 'arm4', '--arm4-dirs', ','.join(self.dirs['arm4']), '--base-dirs',
               *self.dirs['arm3'], '--arm1-dirs', ','.join(self.dirs['arm1']), '--base-json', self.base_json,
               '--smoke-json', options['smoke_json'], '--identity-json', options['identity_json'],
               '--bundle', 'v014', '--out', str(self.root / 'out.json')]
        for directory in self.dirs['arm4']:
            out.extend(['--transport', directory + '=' + options['transports'][directory],
                        '--push-event', directory + '=' + options['push_events'][directory]])
        if explicit_classifiers:
            for directory, pair in self.classifiers.items():
                out.extend(['--classifiers', directory + '=' + ','.join(pair)])
        return out


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    return Experiment(tmp_path, monkeypatch)


def test_vetoed_valid_base_and_primary_statistics(experiment):
    result = experiment.result()
    assert result['decision'] == '2048-ADOPT'
    assert result['decision_inputs']['base_valid']
    assert result['primary'] == dict(arm4_only=m._id_count([]), comparator_only=m._id_count(experiment.ids[8:10]),
                                    D=2, p=.5, arm4_resolved=m.base.rate(8, 33), arm3_resolved=m.base.rate(10, 33))
    assert all(arm['n_rows'] == 33 for arm in result['arms'].values())
    assert result['_schema']['script_sha256'] == m.base.sha(m.__file__)
    assert result['_schema']['name'] == 'plan008_metrics/v1'
    assert result['_schema']['mode'] == 'arm4'
    assert result['_schema']['definitions']['limits'].startswith('ABSOLUTE')
    assert result['_schema']['input_shas'][experiment.base_json] == m.base.sha(experiment.base_json)
    for pair in experiment.classifiers.values():
        for classifier in pair:
            assert result['_schema']['input_shas'][classifier] == m.base.sha(classifier)


@pytest.mark.parametrize('resolved,expected', [(8, '2048-ADOPT'), (7, '2048-WORSE'), (12, '2048-ADOPT')])
def test_D_boundaries(experiment, resolved, expected):
    experiment.mutate('arm4', lambda row, i: row.update(resolved=i < resolved))
    # Smoke evidence is tied to its exact timing bytes; keep smoke rows unchanged here.
    result = experiment.result()
    assert result['decision'] == expected
    assert result['primary']['D'] == 10 - resolved


@pytest.mark.parametrize('metric,count,expected', [
    ('timeouts', 16, '2048-ADOPT'), ('timeouts', 17, '2048-NO-GAIN'),
    ('empties', 18, '2048-ADOPT'), ('empties', 19, '2048-NO-GAIN')])
def test_absolute_limits(experiment, metric, count, expected):
    experiment.mutate('arm4', lambda row, i: row.update(
        **({'timed_out': i < count} if metric == 'timeouts' else {'verified_patch_bytes': 0 if i < count else 1})))
    assert experiment.result()['decision'] == expected


def test_limit_before_safety(experiment):
    experiment.mutate('arm4', lambda row, i: row.update(timed_out=i < 17, test_files_edited=['tests/test_x.py'] if i == 3 else []))
    result = experiment.result()
    assert not result['decision_inputs']['safety_checks']['test_files_edited']
    assert result['decision'] == '2048-NO-GAIN'


@pytest.mark.parametrize('branch', ['adopt', 'worse', 'no_gain', 'veto'])
def test_invalid_H_precedes_every_branch(experiment, branch):
    experiment.mutate('arm4', lambda row, i: row.update(
        resolved=i < (7 if branch == 'worse' else 8), timed_out=i < (17 if branch == 'no_gain' else 16),
        agent_clock_seconds=220.0001 if branch == 'veto' and i == 4 else 200))
    path = experiment.classifiers[experiment.dirs['arm4'][1]][0]
    classifier = json.loads(Path(path).read_text())
    for row in classifier['rows'][:5]:
        row['h'] = 'H'
    write_json(path, classifier)
    result = experiment.result()
    assert result['arms']['arm4']['h_rows']['count'] == 5
    assert result['arms']['arm4']['resolved']['n'] == 33
    assert result['decision'] == 'INVALID'


@pytest.mark.parametrize('field,value,expected', [
    ('agent_clock_seconds', 220, '2048-ADOPT'), ('agent_clock_seconds', 220.0001, 'VETOED'),
    ('finalization_seconds', 30, '2048-ADOPT'), ('finalization_seconds', 30.0001, 'VETOED'),
    ('agent_clock_seconds', None, 'VETOED'), ('finalization_seconds', float('nan'), 'VETOED')])
def test_timing_unrounded(experiment, field, value, expected):
    experiment.mutate('arm4', lambda row, i: row.update({field: value}) if i == 2 else None)
    assert experiment.result()['decision'] == expected


@pytest.mark.parametrize('epsilon,expected', [(0, '2048-ADOPT'), (.0001, 'VETOED')])
def test_wall_p90_boundary(experiment, epsilon, expected):
    experiment.mutate('arm4', lambda row, i: row['wall_seconds'].update(total=1.10 * 300 + epsilon) if i >= 2 else None)
    result = experiment.result()
    assert result['arms']['arm4']['safety']['total_wall_p90'] == 330
    assert result['decision'] == expected


@pytest.mark.parametrize('arm', ['arm4', 'arm3'])
@pytest.mark.parametrize('field', ['stray_files', 'test_files_edited', 'wall_seconds', 'verified_patch_bytes', 'resolved', 'timed_out'])
def test_missing_row_evidence_fails(experiment, arm, field):
    experiment.mutate(arm, lambda row, i: row.pop(field) if i == 2 else None)
    assert experiment.result()['decision'] != '2048-ADOPT'


@pytest.mark.parametrize('evidence', ['trace', 'classifier', 'identity', 'smoke', 'base'])
def test_missing_files_fail_cli(experiment, evidence):
    path = (Path(experiment.dirs['arm4'][1]) / 'runs' / experiment.ids[3] / 'trace.json' if evidence == 'trace' else
            Path(experiment.classifiers[experiment.dirs['arm4'][1]][0]) if evidence == 'classifier' else
            Path(experiment.base_json) if evidence == 'base' else
            Path(experiment.options['arm4'][evidence + '_json']))
    path.unlink()
    m.main(experiment.argv())
    result = json.loads((experiment.root / 'out.json').read_text())
    assert result['decision'] == 'INVALID'


@pytest.mark.parametrize('arm', ['arm4', 'arm3', 'arm1'])
def test_incomplete_inventory_no_decision_and_nonzero_exit(experiment, arm):
    timing = Path(experiment.dirs[arm][1]) / 'timing.jsonl'
    documents = [json.loads(line) for line in timing.read_text().splitlines()]
    timing.write_text('\n'.join(json.dumps(d) for d in documents if d.get('instance_id') != experiment.ids[-1]) + '\n')
    assert m.main(experiment.argv()) == 3
    result = json.loads((experiment.root / 'out.json').read_text())
    assert result['status'] == 'NO_DECISION'
    assert result['decision'] is result['verdict'] is None
    assert 'primary' not in result


@pytest.mark.parametrize('count,base_count,expected', [
    (10, 7, '2048-ADOPT'), (11, 7, 'VETOED'), (11, 20, 'VETOED')])
def test_d735_both_arms_and_absolute_swt(experiment, count, base_count, expected):
    # Explicit flag disagrees with trace: no candidate => D73.5 worst case.
    for arm, n in (('arm4', count), ('arm3', base_count)):
        experiment.mutate(arm, lambda row, i: row.update(patch_submitted=2 <= i < n + 2))
    experiment.bind_base()
    result = experiment.result()
    assert result['arms']['arm4']['safety']['submitted_without_test']['count'] == count
    assert result['arms']['arm3']['safety']['submitted_without_test']['count'] == base_count
    assert result['decision'] == expected


@pytest.mark.parametrize('test_first,expected', [(True, 0), (False, 1)])
def test_d735_test_must_precede_earliest_candidate(experiment, test_first, expected):
    for arm in ('arm4', 'arm3'):
        # Successful response conflicts with the explicit false flag, so D73.5 applies.
        submit = [
            dict(author=m.ROOT, type='tool_call', tool='submit_patch', args={}),
            dict(author=m.ROOT, type='tool_response', tool='submit_patch', result={'patch_size': 1})]
        test = [dict(author=m.ROOT, type='tool_call', tool='run_command', args={'command': 'python -m pytest'})]
        experiment.trace(arm, 2, test + submit if test_first else submit + test)
    experiment.bind_base()
    result = experiment.result()
    assert all(result['arms'][arm]['safety']['submitted_without_test']['count'] == expected for arm in ('arm4', 'arm3'))


def test_timeout_OR_counts_and_paired_empty_counts(experiment):
    experiment.mutate('arm4', lambda row, i: row.update(timed_out=False, agent_timeout_fired=i < 16) if i >= 2 else None)
    result = experiment.result()
    assert [result['arms'][a]['timeouts']['count'] for a in ('arm4', 'arm3', 'arm1')] == [16, 21, 4]
    assert [result['arms'][a]['safety']['empty_patch']['count'] for a in ('arm4', 'arm3', 'arm1')] == [18, 18, 12]
    assert result['comparisons']['arm3']['timeouts']['comparator_only']['count'] == 5
    assert result['comparisons']['arm1']['timeouts']['arm4_only']['count'] == 12
    assert result['comparisons']['arm3']['empty_patch']['arm4_only']['count'] == 0
    assert result['comparisons']['arm1']['empty_patch']['arm4_only']['count'] == 6


def test_original_rule_is_descriptive_with_both_limit_vetoes(experiment):
    result = experiment.result()
    secondary = result['secondary_plan009_vs_arm1']
    assert secondary['decision'] == 'ON-BETTER-VETOED'
    assert {'timeouts', 'empty_patch'} <= set(secondary['vetoes'])
    assert result['decision'] == '2048-ADOPT'


def test_context_overflow_and_unknown_from_traces(experiment):
    experiment.trace('arm4', 2, [dict(type='error', author=m.ROOT, content='maximum context length exceeded')])
    experiment.trace('arm4', 3, [dict(type='thinking', author=m.ROOT, content='context length exceeded')])
    experiment.trace('arm4', 4, [], summary={'context_overflow': False})
    result = experiment.result()
    context = result['arms']['arm4']['descriptive']['context_overflow']
    assert context == dict(count=1, instance_ids=[experiment.ids[2]], unknown=m._id_count([experiment.ids[3]]))
    assert result['decision'] == '2048-ADOPT'
    description = result['arms']['arm4']['descriptive']
    assert description['thinking']['tasks_with_blocks'] == 31
    assert len(description['repeat']['rows']) == 33
    assert description['per_repo']['repo']['n'] == 33
    assert len(description['llm_calls_p50_p90']) == len(description['tool_calls_p50_p90']) == 2


def test_aggregate_trace_summary_does_not_establish_no_overflow(experiment):
    experiment.trace('arm4', 2, [], summary={'total_events': 0, 'total_tokens': 0})
    context = experiment.result()['arms']['arm4']['descriptive']['context_overflow']
    assert context == dict(count=0, instance_ids=[], unknown=m._id_count([experiment.ids[2]]))


@pytest.mark.parametrize('governing,expected', [(False, '2048-ADOPT'), (True, 'VETOED')])
def test_s81_governing_and_literal_symmetrically(experiment, monkeypatch, governing, expected):
    monkeypatch.setattr(m, 'gold_created_dirs', lambda iid, tasks_path=None: {'scripts'})
    for arm in ('arm4', 'arm3'):
        experiment.mutate(arm, lambda row, i: row.update(
            stray_files=['scripts/sub/file.py' if governing else 'scripts/file.py']) if i == 2 else None)
    experiment.bind_base()
    result = experiment.result()
    assert result['decision'] == expected
    for arm in ('arm4', 'arm3'):
        safety = result['arms'][arm]['safety']
        assert safety['stray_files_literal']['count'] == 1
        assert safety['stray_files']['count'] == int(governing)


@pytest.mark.parametrize('change', ['duplicate', 'extra', 'missing_timing'])
def test_other_inventory_failures_have_no_decision(experiment, change):
    timing = Path(experiment.dirs['arm4'][1]) / 'timing.jsonl'
    if change == 'missing_timing':
        timing.unlink()
    else:
        documents = [json.loads(line) for line in timing.read_text().splitlines()]
        row = dict(documents[1])
        if change == 'extra':
            row['instance_id'] = 'extra__id'
        documents.append(row)
        timing.write_text('\n'.join(map(json.dumps, documents)) + '\n')
    assert m.main(experiment.argv()) == 3
    result = json.loads((experiment.root / 'out.json').read_text())
    assert result['decision'] is None and result['status'] == 'NO_DECISION'


@pytest.mark.parametrize('change', ['base_timing', 'base_classifier', 'base_report', 'smoke_hash', 'smoke_thinking', 'identity', 'transport', 'kernel'])
def test_bound_evidence_and_pairing(experiment, change):
    if change == 'base_timing':
        experiment.mutate('arm3', lambda row, i: row.update(resolved=False) if i == 4 else None)
    elif change == 'base_classifier':
        path = experiment.classifiers[experiment.dirs['arm3'][1]][1]
        doc = json.loads(Path(path).read_text()); doc['extra'] = True; write_json(path, doc)
    elif change == 'base_report':
        doc = json.loads(Path(experiment.base_json).read_text()); doc['decision'] = 'INVALID'; write_json(experiment.base_json, doc)
    elif change == 'smoke_hash':
        path = experiment.options['arm4']['smoke_json']
        doc = json.loads(Path(path).read_text()); doc['_schema']['input_shas'] = {}; write_json(path, doc)
    elif change == 'smoke_thinking':
        experiment.trace('arm4', 0, [])
        # Updating hashes cannot bypass the recomputed smoke check.
        path = experiment.options['arm4']['smoke_json']
        doc = json.loads(Path(path).read_text())
        trace = Path(experiment.dirs['arm4'][0]) / 'runs' / experiment.ids[0] / 'trace.json'
        doc['_schema']['input_shas'][str(trace)] = m.base.sha(trace); write_json(path, doc)
    elif change == 'identity':
        write_json(experiment.options['arm4']['identity_json'], dict(records=[]))
    elif change == 'transport':
        experiment.options['arm4']['transports'][experiment.dirs['arm4'][1]] = 'f' * 64
    else:
        path = Path(experiment.dirs['arm4'][1]) / 'timing.jsonl'
        docs = [json.loads(line) for line in path.read_text().splitlines()]
        docs[0]['kernel_code']['agent_path_sha256'] = 'f' * 64
        path.write_text('\n'.join(map(json.dumps, docs)) + '\n')
        experiment.mutate('arm4', lambda row, i: None)
    assert experiment.result()['decision'] == 'INVALID'


def test_cli_without_classifier_flags_discovers_bound_evidence(experiment):
    assert m.main(experiment.argv(explicit_classifiers=False)) == 0
    result = json.loads((experiment.root / 'out.json').read_text())
    assert result['decision'] == '2048-ADOPT'
    assert result['mode'] == 'arm4'


def test_duplicate_attempt_first_retained(experiment):
    directory = str(experiment.root / 'retry')
    experiment.make_run(directory, experiment.ids[4:5], resolved=33, timeouts=0, empties=0)
    experiment.dirs['arm4'].append(directory)
    experiment.options['arm4']['transports'][directory] = 'b' * 64
    experiment.options['arm4']['push_events'][directory] = 'chunk1'
    result = experiment.result()
    assert result['n_rows'] == 33
    assert result['arms']['arm4']['timeouts']['count'] == 16
    duplicate = result['inventory']['arm4']['duplicates'][0]
    assert duplicate['instance_id'] == experiment.ids[4]
    assert duplicate['attempts'][0]['timeout'] and duplicate['attempts'][0]['empty_patch']
    assert not duplicate['attempts'][1]['timeout'] and not duplicate['attempts'][1]['empty_patch']
    assert result['decision'] == '2048-ADOPT'
