"""Offline tests: stdlib unittest, no competition data or harness imports."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'kaggle/gold_calibration.py'
spec = importlib.util.spec_from_file_location('gold_calibration', SCRIPT)
gold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gold)


def result(task_id='a', repo='org/repo', resolved=True, error=None):
    return dict(instance_id=task_id, repo=repo, resolved=resolved,
                exit_code=0 if resolved else 1, duration_seconds=1.5, error=error)


class ResumeTests(unittest.TestCase):
    def test_success_and_failure_are_finished(self):
        rows = [result(), result('b', resolved=False, error='setup failed')]
        results = gold.finished_results(''.join(json.dumps(row) + '\n' for row in rows))
        tasks = [dict(instance_id=x, repo='org/repo') for x in 'abc']
        self.assertEqual([t['instance_id'] for t in gold.pending_tasks(tasks, results)], ['c'])

    def test_last_completed_duplicate_wins(self):
        rows = [result(resolved=False), result()]
        results = gold.finished_results('\n'.join(map(json.dumps, rows)) + '\n')
        self.assertTrue(results['a']['resolved'])
        self.assertEqual(len(results), 1)

    def test_partial_tail_repaired_and_append_survives_second_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'results.jsonl'
            complete = json.dumps(result()) + '\n'
            path.write_text(complete + '{"instance_id": "unfinished')
            self.assertEqual(set(gold.resume_journal(path)), {'a'})
            self.assertEqual(path.read_text(), complete)
            with path.open('a') as stream:
                stream.write(json.dumps(result('b')) + '\n')
            self.assertEqual(set(gold.resume_journal(path)), {'a', 'b'})

    def test_complete_last_record_without_newline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'results.jsonl'
            path.write_text(json.dumps(result()))
            self.assertEqual(set(gold.resume_journal(path)), {'a'})
            self.assertTrue(path.read_text().endswith('\n'))

    def test_missing_file_and_empty_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(gold.resume_journal(Path(directory) / 'absent'), {})
        self.assertEqual(gold.finished_results(''), {})

    def test_corruption_is_not_silently_dropped(self):
        for text in ('bad\n', 'bad\n' + json.dumps(result()), '{}\n',
                     json.dumps(dict(result(), duration_seconds=float('nan'))) + '\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                gold.finished_results(text)

    def test_inventory_mismatch_and_duplicate_ids(self):
        tasks = [dict(instance_id='a', repo='org/repo')]
        for inventory, results in ((tasks * 2, {}), (tasks, {'b': result('b')}),
                                   (tasks, {'a': result(repo='wrong/repo')})):
            with self.assertRaises(ValueError):
                gold.pending_tasks(inventory, results)


class SummaryTests(unittest.TestCase):
    def test_all_tasks_counted_by_repo(self):
        tasks = [dict(instance_id=x, repo=repo) for x, repo in
                 [('a', 'org/one'), ('b', 'org/one'), ('c', 'org/two'), ('d', 'org/two')]]
        results = {'a': result('a', 'org/one'),
                   'b': result('b', 'org/one', False, 'setup failed'),
                   'c': result('c', 'org/two', False)}
        summary = gold.summarize(tasks, results)
        self.assertEqual([summary[k] for k in ('total', 'finished', 'passed', 'failed', 'pending')],
                         [4, 3, 1, 2, 1])
        self.assertEqual(summary['passing_ids'], ['a'])
        self.assertEqual(summary['pending_ids'], ['d'])
        self.assertEqual(summary['failing_ids'], [
            dict(instance_id='b', reason='setup failed'),
            dict(instance_id='c', reason='verification unresolved (exit_code=1)')])
        self.assertEqual(summary['per_repo']['org/one'],
                         dict(total=2, finished=2, passed=1, failed=1, pending=0))
        self.assertEqual(summary['per_repo']['org/two'],
                         dict(total=2, finished=1, passed=0, failed=1, pending=1))

    def test_empty_summary_and_short_reasons(self):
        self.assertEqual(gold.summarize([], {})['total'], 0)
        summary = gold.summarize([dict(instance_id='a', repo='org/repo')],
                                {'a': result(resolved=False, error='x' * 500)})
        self.assertEqual(len(summary['failing_ids'][0]['reason']), 200)

    def test_main_fully_resumed_needs_no_harness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tasks.jsonl').write_text(json.dumps(dict(instance_id='a', repo='org/repo')) + '\n')
            (root / 'gold_results.jsonl').write_text(json.dumps(result()) + '\n')
            with patch('sys.argv', [str(SCRIPT), '--data-dir', str(root), '--working-dir', str(root)]), \
                    patch.object(gold, 'install_harness', side_effect=AssertionError('must not import harness')), \
                    patch('builtins.print'):
                gold.main()
            self.assertEqual(json.loads((root / 'gold_summary.json').read_text())['passing_ids'], ['a'])

    def test_gold_ids_file_selects_inventory_before_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'tasks.jsonl').write_text(''.join(json.dumps(dict(instance_id=i, repo='org/repo')) + '\n'
                                                     for i in ('a', 'b')))
            (root / 'gold_results.jsonl').write_text(json.dumps(result()) + '\n')
            (root / 'ids.txt').write_text('a\n')
            with patch('sys.argv', [str(SCRIPT), '--data-dir', str(root), '--working-dir', str(root)]), \
                    patch.dict('os.environ', GOLD_IDS_FILE=str(root / 'ids.txt')), \
                    patch.object(gold, 'install_harness', side_effect=AssertionError('fully resumed')), \
                    patch('builtins.print'):
                gold.main()
            self.assertEqual(json.loads((root / 'gold_summary.json').read_text())['total'], 1)


class WorkerTests(unittest.TestCase):
    def run_worker(self, verifier):
        raw = dict(instance_id='a', repo='org/repo', patch='GOLD_PATCH_SECRET',
                   test_patch='TEST_PATCH_SECRET', problem_statement='TASK_TEXT_SECRET')
        task = types.SimpleNamespace(instance_id='a')
        models = types.ModuleType('swegemma.models')
        models.load_tasks = lambda path: [task]
        with tempfile.TemporaryDirectory() as directory:
            args = argparse.Namespace(data_dir=Path(directory), worker='a',
                                      sandbox='subprocess', result=Path(directory) / 'result.json')
            with patch.object(gold, 'patch_subprocess_deps'), \
                    patch.object(gold, 'load_inventory', return_value=[raw]), \
                    patch.dict('sys.modules', {'swegemma.models': models}), \
                    patch.object(gold, 'setup_scorer_env', return_value={'sandbox': 'bwrap'}), \
                    patch.object(gold, 'verify_gold', side_effect=verifier):
                gold.worker(args)
            return json.loads(args.result.read_text())

    def test_gold_patch_only_and_harness_verdict_preserved(self):
        async def verify(task, patch_text, data_dir, sandbox, **kwargs):
            self.assertEqual(patch_text, 'GOLD_PATCH_SECRET')
            self.assertEqual(sandbox, 'subprocess')
            # Exit 0 can still fail the harness's required-test/JUnit checks.
            return dict(resolved=False, test_exit_code=0, error='TEST_PATCH_SECRET',
                        error_message='TASK_TEXT_SECRET', test_output='ERROR TASK_TEXT_SECRET')
        row = self.run_worker(verify)
        self.assertFalse(row['resolved'])
        self.assertEqual(row['exit_code'], 0)
        self.assertNotIn('SECRET', json.dumps(row))
        self.assertGreaterEqual(row['duration_seconds'], 0)

    def test_exception_text_never_copied_into_result(self):
        async def verify(*args, **kwargs):
            raise RuntimeError('GOLD_PATCH_SECRET TASK_TEXT_SECRET')
        row = self.run_worker(verify)
        self.assertFalse(row['resolved'])
        self.assertIsNone(row['exit_code'])
        self.assertEqual(row['error'], 'Verification/setup exception (RuntimeError)')
        self.assertNotIn('SECRET', json.dumps(row))

    def test_null_patch_control_still_reaches_verifier(self):
        async def verify(task, patch_text, data_dir, sandbox, **kwargs):
            self.assertIn('NULL_CONTROL.txt', patch_text)
            self.assertNotIn('GOLD_PATCH_SECRET', patch_text)
            self.assertIn('out_dir', kwargs)
            return dict(resolved=False, test_exit_code=1)
        with patch.dict('os.environ', GOLD_NULL_PATCH='1'):
            row = self.run_worker(verify)
        self.assertFalse(row['resolved'])
        self.assertEqual(row['sandbox'], 'bwrap')

    def test_docker_unavailable_falls_back_without_network_pull(self):
        with patch.object(gold.subprocess, 'run', side_effect=FileNotFoundError):
            self.assertEqual(gold.choose_sandbox(), 'subprocess')
        with patch.object(gold.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0)) as run:
            self.assertEqual(gold.choose_sandbox(), 'docker')
            self.assertIn('--pull=never', run.call_args_list[0].args[0])
            self.assertIn('--network=none', run.call_args_list[0].args[0])


if __name__ == '__main__':
    unittest.main()
