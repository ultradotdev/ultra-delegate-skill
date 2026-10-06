import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.agents/skills/ultra-delegation/scripts'))
import jev  # noqa: E402
import ladder  # noqa: E402
import ud  # noqa: E402
import workers  # noqa: E402

DATA = Path(__file__).parent / 'data'
RUNGS = [{'id': f'r{i}', 'description': f'rung {i}', 'price': {'input': 1.0, 'output': 2.0}} for i in range(3)]


class Rules(unittest.TestCase):
    def test_noul_takes_cheapest_rung_over_cutoff(self):
        self.assertEqual(ladder.jev_noul([0.3, 0.6, 0.9], 0.5), 1)
        self.assertEqual(ladder.jev_noul([0.7, 0.6, 0.9], 0.5), 0)

    def test_noul_without_a_qualifying_rung_starts_where_jev_is_most_confident(self):
        self.assertEqual(ladder.jev_noul([0.2, 0.45, 0.3], 0.5), 1)

    def test_expected_cost_and_ev_rule(self):
        self.assertAlmostEqual(ladder.expected_cost([0.5, 1.0], [1, 10], 100, 0), 1 + 0.5 * 10)
        self.assertEqual(ladder.jev_ev([0.1, 0.95], [1, 2], 50), 1)
        self.assertEqual(ladder.jev_ev([0.9, 0.95], [1, 20], 50), 0)

    def test_jev_failure_degrades_to_cheapest_first(self):
        self.assertEqual(ladder.pick('jev_noul', {'route': 'default'}), 0)
        self.assertEqual(ladder.pick('jev_choice', {'route': 'jev', 'start': 2, 'passes': [0, 0, 1]}), 2)


class JevBatch(unittest.TestCase):
    task = {'goal': 'Fix add', 'acceptance': ['tests pass'], 'files': ['solution.py']}

    def answers(self, payload, **override):
        a = {'difficulty': {'type': 'score', 'score': 1.2, 'probabilities': {'0': .1, '1': .6, '2': .3, '3': 0}},
             'start': {'type': 'choice', 'choice': 'r1', 'probabilities': {'r0': .2, 'r1': .7, 'r2': .1}}}
        a.update({f'pass_{i}': {'type': 'noul', 'noul': p} for i, p in enumerate([.2, .6, .9])})
        a.update(override)
        return {'model': payload['model'], 'answers': a, 'usage': {'input_tokens': 1500, 'output_tokens': 40}}

    def test_one_request_asks_every_rung_and_a_start(self):
        payload = jev.build(self.task, RUNGS, {'r0': 'difficulty 1: 2/3 first-attempt passes'}, [])
        self.assertEqual(set(payload['questions']), {'difficulty', 'pass_0', 'pass_1', 'pass_2', 'start'})
        self.assertEqual(set(payload['questions']['start']['criteria']), {'r0', 'r1', 'r2'})
        self.assertEqual(payload['state']['rungs'][0]['track_record'], 'difficulty 1: 2/3 first-attempt passes')

    def test_parse_reduces_answers_for_the_ladder(self):
        payload = jev.build(self.task, RUNGS, {}, [])
        r = jev.parse(payload, self.answers(payload), RUNGS)
        self.assertEqual((r['route'], r['passes'], r['start'], r['difficulty']), ('jev', [.2, .6, .9], 1, 1.2))
        self.assertAlmostEqual(r['cost_usd'], 1500 * 0.042 / 1e6)

    def test_malformed_answers_raise(self):
        payload = jev.build(self.task, RUNGS, {}, [])
        for bad in ({'pass_1': {'type': 'noul', 'noul': 1.5}}, {'start': {'type': 'choice', 'choice': 'other'}}):
            with self.assertRaises(jev.JevError):
                jev.parse(payload, self.answers(payload, **bad), RUNGS)

    def test_route_never_raises(self):
        with mock.patch.object(jev, 'credential', side_effect=jev.JevError('no key')):
            self.assertEqual(jev.route(self.task, RUNGS, {}, '.')['route'], 'default')

    def test_file_contents_truncate_to_budget(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'big.py').write_text('x = 1\n' * 5000)
            files = jev.read_files(d, ['big.py', 'gone.py'], 1000)
        self.assertLess(len(files[0]['content']), 1100)
        self.assertTrue(files[1]['missing'])


class Parsers(unittest.TestCase):
    def test_codex_usage_from_real_exec_output(self):
        events = [json.loads(line) for line in (DATA / 'codex-exec-events.jsonl').read_text().splitlines()]
        with tempfile.TemporaryDirectory() as d:
            ok, usage, reported, _, _ = workers.parse_codex(events, Path(d))
        self.assertTrue(ok)
        self.assertEqual((usage['input'], usage['cached_input'], usage['output']), (112918, 95744, 1117))
        rung = {'price': {'input': 0.1, 'cached_input': 0.01, 'output': 0.5}}
        self.assertAlmostEqual(workers.price(rung, usage, reported), (17174 * .1 + 95744 * .01 + 1117 * .5) / 1e6, 6)

    def test_claude_usage_and_reported_cost_from_real_output(self):
        events = [json.loads(line) for line in (DATA / 'claude-stream-result.jsonl').read_text().splitlines()]
        ok, usage, reported, _, _ = workers.parse_claude(events)
        self.assertTrue(ok)
        self.assertEqual(usage['input'], 42 + 134732 + 37739)
        self.assertEqual(workers.price({}, usage, reported), 0.125348)


class Delegate(unittest.TestCase):
    """End to end through ud.py with a fake codex CLI; no network or model calls."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = self.tmp / 'repo'
        self.repo.mkdir()
        (self.repo / 'solution.py').write_text('def add(a, b):\n    return 0\n')
        (self.repo / 'check.py').write_text('from solution import add\nassert add(2, 3) == 5\nprint("ok")\n')
        for cmd in (['init', '-q'], ['add', '-A'], ['-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'base']):
            subprocess.run(['git', *cmd], cwd=self.repo, check=True)
        bin_dir = self.tmp / 'bin'
        bin_dir.mkdir()
        (bin_dir / 'codex').write_text(f'#!/bin/sh\nexec {sys.executable} {Path(__file__).parent / "fake_codex.py"} "$@"\n')
        (bin_dir / 'codex').chmod(0o755)
        env = {'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}', 'UD_STATE': str(self.tmp / 'state')}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.tmp / 'task.json').write_text(json.dumps({'goal': 'Make add return the sum', 'acceptance': ['check passes'],
                                                        'files': ['solution.py'], 'check': 'python3 check.py',
                                                        'check_files': ['check.py']}))

    def run_ud(self, models, routing=None, *extra):
        cfg = json.loads((ROOT / '.agents/skills/ultra-delegation/assets/tiers.json').read_text())
        cfg['ladders']['codex'] = [{'id': m, 'launcher': 'codex', 'model': m, 'effort': None, 'description': m,
                                    'price': {'input': 1.0, 'cached_input': 0.1, 'output': 2.0}} for m in models]
        (self.tmp / 'tiers.json').write_text(json.dumps(cfg))
        routing = routing or {'route': 'default', 'error': 'test'}
        out = io.StringIO()
        with mock.patch.object(jev, 'route', return_value=routing), contextlib.redirect_stdout(out):
            code = ud.main(['--tiers', str(self.tmp / 'tiers.json'), 'delegate', str(self.tmp / 'task.json'),
                            '--host', 'codex', '--repo', str(self.repo), *extra])
        return code, json.loads(out.getvalue())

    def test_failed_check_escalates_with_findings_and_patch_applies(self):
        code, result = self.run_ud(['fake-bad', 'fake-good'])
        self.assertEqual((code, result['status'], result['rung']), (0, 'passed', 'fake-good'))
        self.assertEqual([a['passed'] for a in result['attempts']], [False, True])
        subprocess.run(['git', 'apply', '--3way', result['patch']], cwd=self.repo, check=True)
        self.assertIn('a + b', (self.repo / 'solution.py').read_text())

    def test_jev_start_rung_is_used(self):
        code, result = self.run_ud(['fake-bad', 'fake-good'], {'route': 'jev', 'passes': [0.1, 0.9], 'start': 1})
        self.assertEqual([a['rung'] for a in result['attempts']], ['fake-good'])

    def test_worker_cannot_pass_by_editing_the_check(self):
        code, result = self.run_ud(['fake-cheat'])
        self.assertEqual((code, result['status']), (3, 'escalate_to_coordinator'))
        self.assertIn('AssertionError', result['findings'])

    def test_new_files_are_in_the_patch(self):
        _, result = self.run_ud(['fake-newfile'])
        self.assertEqual(result['status'], 'passed')
        self.assertIn('helper.py', Path(result['patch']).read_text())

    def test_infrastructure_errors_retry_and_never_count_as_quality(self):
        _, result = self.run_ud(['fake-capacity', 'fake-good'])
        self.assertEqual(result['attempts'][0]['status'], 'infra_error')
        rows = [json.loads(line) for line in next((self.tmp / 'state').glob('*/outcomes.jsonl')).read_text().splitlines()]
        self.assertIsNone(rows[0]['verified_by'])
        self.assertEqual(ud.track_records(rows), {})

    def test_uncommitted_work_is_in_the_base(self):
        (self.repo / 'notes.txt').write_text('coordinator draft\n')
        base = workers.base_commit(self.repo)
        self.assertIn('notes.txt', workers.git(self.repo, 'ls-tree', '--name-only', base))
        self.assertEqual(workers.git(self.repo, 'stash', 'list'), '')


if __name__ == '__main__':
    unittest.main()
