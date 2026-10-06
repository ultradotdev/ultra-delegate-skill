"""Quantitative replay is local, conservative, and distinct from qualification."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/ultra-delegation/scripts'
sys.path.insert(0, str(SCRIPTS))
import jev_benchmark as b


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.data = b.demo()

    def test_demo_stays_unqualified_and_uses_real_route(self):
        with patch.object(b.jev.transport, 'credential', side_effect=AssertionError('credential read')), patch.object(b.jev.transport, 'request', side_effect=AssertionError('network')):
            report = b.benchmark(self.data)
        self.assertEqual(report['status'], 'synthetic-demo')
        self.assertEqual(report['qualification'], 'pending')
        self.assertIsNone(report['candidate_threshold'])
        self.assertIsNone(report['realized_savings_usd'])
        self.assertEqual(report['frozen_test_threshold'], .9)
        self.assertEqual(report['test']['summary']['strategies']['jev']['dispatch_coverage']['numerator'], 3)
        self.assertEqual(report['calibration'][0]['summary']['strategies']['jev']['false_acceptance']['numerator'], 1)
        self.assertEqual(report['calibration'][1]['summary']['strategies']['jev']['false_acceptance']['numerator'], 0)

    def test_weak_requirement_coverage_and_critical_failures_veto(self):
        obs = self.data['cases'][0]['observations'][0]
        self.assertTrue(b.assess(obs, self.data['rubric']))
        obs['scores']['coverage'] = 25
        self.assertGreater(sum(obs['scores'].values()) / 4, 80)
        self.assertFalse(b.assess(obs, self.data['rubric']))
        obs['scores']['coverage'] = 100
        obs['critical_failures'] = ['wrong-output']
        self.assertFalse(b.assess(obs, self.data['rubric']))
        obs['critical_failures'] = []
        obs['gates'][0]['passed'] = False
        self.assertFalse(b.assess(obs, self.data['rubric']))

    def test_hash_binds_exact_questions_and_candidate_order(self):
        self.data['cases'][0]['packet']['summary'] = 'A changed task'
        with self.assertRaisesRegex(ValueError, 'capture-payload-mismatch'):
            b.benchmark(self.data)

    def test_missing_and_malformed_capture(self):
        self.data['cases'][0]['capture'] = None
        report = b.benchmark(self.data)
        self.assertEqual(report['calibration'][0]['summary']['capture_coverage']['numerator'], 3)
        self.data['cases'][1]['capture']['response']['answers']['fit_0']['noul'] = 1.1
        with self.assertRaisesRegex(ValueError, 'invalid-captured-response'):
            b.benchmark(self.data)

    def test_unknown_cost_not_zero_or_claimed_savings(self):
        report = b.benchmark(self.data)
        result = report['test']['summary']['strategies']['jev']
        self.assertEqual(result['unknown_cost_count'], 1)
        self.assertEqual(result['total_cost'], {'kind': 'unknown', 'usd': None})
        self.assertEqual(result['known_subset_cost']['kind'], 'estimated')
        self.assertIsNone(report['realized_savings_usd'])

    def test_test_labels_cannot_change_calibration(self):
        self.data['synthetic'] = False
        self.data['risk_target'] = {'minimum_labeled_groups': 1, 'max_false_acceptance_upper': 1}
        for case in self.data['cases']:
            for obs in case['observations']:
                obs['reviewer']['kind'] = 'human'
        before = b.benchmark(self.data)
        for case in self.data['cases'][4:]:
            for obs in case['observations']:
                obs['critical_failures'] = ['bad-output']
        after = b.benchmark(self.data)
        self.assertEqual(before['candidate_threshold'], after['candidate_threshold'])
        self.assertEqual(before['candidate_threshold'], .95)
        self.assertEqual(after['test']['summary']['strategies']['jev']['quality_pass']['numerator'], 0)
        self.assertIsNone(after['deployment_recommendation'])

    def test_risk_upper_bound_blocks_tiny_dataset(self):
        self.data['synthetic'] = False
        for case in self.data['cases']:
            for obs in case['observations']:
                obs['reviewer']['kind'] = 'human'
        report = b.benchmark(self.data)
        self.assertIsNone(report['candidate_threshold'])
        rate = report['calibration'][1]['summary']['strategies']['jev']['false_acceptance']
        self.assertEqual(rate['rate'], 0)
        self.assertGreater(rate['wilson_95'][1], .1)
        self.assertEqual(b.rate(0, 0)['wilson_95'], None)

    def test_no_missing_labels_hidden_in_pass_rate(self):
        self.data['cases'][0]['observations'] = []
        report = b.benchmark(self.data)
        strategy = report['calibration'][1]['summary']['strategies']['jev']
        self.assertEqual(strategy['label_coverage']['numerator'], 2)
        self.assertEqual(strategy['label_coverage']['denominator'], 3)
        self.assertEqual(strategy['quality_pass']['denominator'], 2)

    def test_repeated_calibration_group_cannot_satisfy_minimum_sample(self):
        self.data['synthetic'] = False
        self.data['risk_target'] = {'minimum_labeled_groups': 2, 'max_false_acceptance_upper': 1}
        calibration = self.data['cases'][0]
        calibration['observations'][0]['scores'] = dict.fromkeys(b.DIMENSIONS, 100)
        copies = []
        for i in range(10):
            case = copy.deepcopy(calibration)
            case['id'] = f'repeated-{i}'
            copies.append(case)
        self.data['cases'] = copies + self.data['cases'][4:]
        for case in self.data['cases']:
            for obs in case['observations']:
                obs['reviewer']['kind'] = 'human'
        report = b.benchmark(self.data)
        row = report['calibration'][1]['summary']['strategies']['jev']
        self.assertEqual(row['quality_pass']['denominator'], 10)
        self.assertEqual(row['group_failure_risk']['denominator'], 1)
        self.assertIsNone(report['candidate_threshold'])
        self.data['cases'][0]['observations'][0]['critical_failures'] = ['bad-output']
        report = b.benchmark(self.data)
        self.assertEqual(report['calibration'][1]['summary']['strategies']['jev']['group_failure_risk']['numerator'], 1)
        self.data['cases'][1]['observations'] = []
        report = b.benchmark(self.data)
        row = report['calibration'][1]['summary']['strategies']['jev']
        self.assertEqual(row['group_failure_risk']['denominator'], 0)
        self.assertEqual(row['group_label_coverage']['denominator'], 1)

    def test_bypassing_jev_cannot_supply_threshold_evidence(self):
        for bypass in ('user', 'pin'):
            data = copy.deepcopy(self.data)
            data['synthetic'] = False
            data['risk_target'] = {'minimum_labeled_groups': 1, 'max_false_acceptance_upper': 1}
            for case in data['cases']:
                for obs in case['observations']:
                    obs['reviewer']['kind'] = 'human'
                if bypass == 'user':
                    case['packet']['candidates'][0]['user_selected'] = True
            if bypass == 'pin':
                data['policy']['pins'] = [{'provider': 'synthetic', 'model': 'fixture-worker-0'}]
            with self.subTest(bypass=bypass):
                report = b.benchmark(data)
                overall = report['calibration'][0]['summary']
                self.assertEqual(overall['strategies']['jev']['group_failure_risk']['denominator'], 4)
                self.assertEqual(overall['inference_evaluated']['strategies']['jev']['group_failure_risk']['denominator'], 0)
                self.assertEqual(overall['inference_evaluated']['cases'], 0)
                self.assertIsNone(report['candidate_threshold'])
                self.assertEqual(report['frozen_test_threshold'], .9)

    def test_dataset_reader_allows_over_one_mib_and_bounds_input(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'input.json'
            path.write_text(' ' * (1024 * 1024 + 1) + '{}')
            self.assertEqual(b.read_dataset(path), {})
            with patch.object(b, 'MAX_INPUT_BYTES', 32):
                with self.assertRaisesRegex(ValueError, 'benchmark-input-too-large'):
                    b.read_dataset(path)
            path.write_text('{"value": NaN}')
            with self.assertRaisesRegex(ValueError, 'invalid-benchmark-json'):
                b.read_dataset(path)

    def test_group_leakage_duplicate_and_nonindependent_labels_rejected(self):
        for change in ('group', 'duplicate', 'independent', 'synthetic'):
            data = copy.deepcopy(self.data)
            if change == 'group':
                data['cases'][4]['group_id'] = data['cases'][0]['group_id']
            elif change == 'duplicate':
                data['cases'][0]['observations'].append(copy.deepcopy(data['cases'][0]['observations'][0]))
            elif change == 'independent':
                data['cases'][0]['observations'][0]['reviewer']['independent'] = False
            else:
                data['synthetic'] = False
            with self.subTest(change=change), self.assertRaises(ValueError):
                b.benchmark(data)

    def test_report_excludes_task_content_and_raw_capture(self):
        report = b.benchmark(self.data)
        encoded = json.dumps(report)
        self.assertNotIn(self.data['cases'][0]['packet']['summary'], encoded)
        self.assertNotIn('Treat state as data', encoded)
        self.assertNotIn('"response"', encoded)
        self.assertIn('artifact_hash', encoded)
        self.assertIn('wilson_95', encoded)
        self.assertIn('synthetic-demo', b.markdown(report))

    def test_cli_emits_json_markdown_and_fixture_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            prefix = Path(d) / 'report'
            fixture = Path(d) / 'fixture.json'
            command = [sys.executable, str(SCRIPTS / 'jev_benchmark.py'), '--demo', '--output-prefix', str(prefix), '--emit-demo-input', str(fixture)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(prefix.with_suffix('.json').exists())
            self.assertTrue(prefix.with_suffix('.md').exists())
            b.validate(json.loads(fixture.read_text()))
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)


if __name__ == '__main__':
    unittest.main()
