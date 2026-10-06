from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
import calibrate  # noqa: E402
import fx  # noqa: E402
import replay  # noqa: E402

RUNGS = [{'id': 'cheap'}, {'id': 'top'}]
PROXY = {'id': 'coord'}


def cell(fixture, rung, public, hidden, cost, sec=10.0):
    return {'fixture': fixture, 'rung': rung, 'public_pass': public, 'hidden_pass': hidden,
            'cost_usd': cost, 'seconds': sec, 'status': 'completed'}


class Replay(unittest.TestCase):
    def test_expected_cost_escalates_on_public_failure(self):
        cells = [cell('a', 'cheap', False, False, 1.0), cell('a', 'cheap', True, True, 1.0),
                 cell('a', 'top', True, True, 10.0), cell('b', 'coord', True, True, 100.0)]
        row = replay.stats(cells, RUNGS, PROXY)['a']
        sim = replay.simulate(row, 0)
        self.assertAlmostEqual(sim['cost'], 1.0 + 0.5 * 10.0)  # cheap always runs; top runs half the time
        self.assertAlmostEqual(sim['quality'], 1.0)
        self.assertAlmostEqual(sim['handoff'], 0.0)

    def test_public_pass_with_hidden_fail_is_a_slip_not_quality(self):
        cells = [cell('a', 'cheap', True, False, 1.0), cell('a', 'top', True, True, 10.0)]
        row = replay.stats(cells, RUNGS, PROXY)['a']
        self.assertEqual((replay.simulate(row, 0)['quality'], replay.simulate(row, 0)['slip']), (0.0, 1.0))
        self.assertEqual(replay.simulate(row, 1)['quality'], 1.0)

    def test_all_workers_failing_hands_off_to_coordinator(self):
        cells = [cell('a', 'cheap', False, False, 1.0), cell('a', 'top', False, False, 10.0),
                 cell('z', 'coord', True, True, 40.0)]
        sim = replay.simulate(replay.stats(cells, RUNGS, PROXY)['a'], 0)
        self.assertAlmostEqual((sim['handoff'], sim['cost']), (1.0, 51.0))

    def test_auc(self):
        self.assertEqual(replay.auc([(0.9, True), (0.1, False)]), 1.0)
        self.assertEqual(replay.auc([(0.5, True), (0.5, False)]), 0.5)


class Scrub(unittest.TestCase):
    def test_committed_results_carry_no_machine_paths(self):
        import tempfile
        text = f'{calibrate.RAW}/codex/x {tempfile.gettempdir()}/eval {Path.home()}/notes'
        cleaned = calibrate.scrub(text)
        self.assertNotIn(str(Path.home()), cleaned)
        self.assertNotIn(tempfile.gettempdir(), cleaned)


class Fixtures(unittest.TestCase):
    def test_template_fixture_validates(self):
        result = fx.validate('python-ranges')
        self.assertTrue(result['ok'], result['problems'])


if __name__ == '__main__':
    unittest.main()
