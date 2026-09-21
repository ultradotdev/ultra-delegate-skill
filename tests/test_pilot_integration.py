"""Black-box CLI contract tests in isolated directories without optional packages."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / '.agents/skills/ultra-delegation/scripts/pilot.py'


class PilotCLIIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.root = self.directory / 'state'
        self.env = dict(os.environ)
        self.env.pop('TYPESAFE_API_KEY', None)
        self.env.pop('PYTHONPATH', None)
        self.env['PYTHON_KEYRING_BACKEND'] = 'keyring.backends.null.Keyring'
        self.cli('init', '--mode', 'shadow', '--share-summaries', '--share-artifacts', '--baseline-id', 'candidate-2')
        self.packet_path = self.directory / 'packet.json'
        self.cli('example', '--output', str(self.packet_path))

    def cli(self, *args, ok=True):
        run = subprocess.run([sys.executable, '-I', '-S', str(SCRIPT), '--root', str(self.root), *args],
                             cwd=self.directory, env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(run.returncode, 0 if ok else 2, run.stderr)
        return json.loads(run.stdout if ok else run.stderr)

    def test_preview_route_review_observe_and_report(self):
        packet = json.loads(self.packet_path.read_text())
        packet['task']['summary'] = 'PRIVATE-TASK-CONTENT: review one supplied Python report function.'
        self.packet_path.write_text(json.dumps(packet))
        preview = self.cli('route', '--input', str(self.packet_path), '--dry-run')
        self.assertIn('PRIVATE-TASK-CONTENT', json.dumps(preview))
        self.assertEqual(list((self.root/'decisions').iterdir()), [])
        decision = self.cli('route', '--input', str(self.packet_path))
        self.assertEqual(decision['reason_codes'], ['live-not-requested'])
        self.assertFalse(decision['dispatch_authorized'])
        error = self.cli('recheck', '--decision', decision['id'], '--input', str(self.packet_path), ok=False)
        self.assertEqual(error['error'], 'synthetic-decision-not-executable')
        outcome_path = self.directory/'outcome.json'
        self.cli('outcome-template', '--decision', decision['id'], '--candidate', 'candidate-2', '--output', str(outcome_path))
        self.cli('observe', '--input', str(outcome_path), ok=False)
        self.assertEqual(list((self.root/'outcomes').iterdir()), [])
        raw = json.loads(outcome_path.read_text())
        raw.update(artifact_hash='a'*64, reviewer_id='synthetic-reviewer', reviewer_kind='synthetic', review_accepted=True,
                   scores={key:90 for key in raw['scores']})
        for gate in raw['gates']: gate['passed'] = True
        raw['gates'][0]['passed'] = False  # A mandatory failure cannot be offset by favorable scores.
        outcome_path.write_text(json.dumps(raw))
        outcome = self.cli('observe', '--input', str(outcome_path), '--security-check')
        self.assertFalse(outcome['accepted'])
        self.assertEqual(outcome['security']['reason_codes'], ['live-not-requested'])
        self.cli('observe', '--input', str(outcome_path), ok=False)
        self.assertEqual(len(list((self.root/'outcomes').iterdir())), 1)
        paths = self.cli('report')
        report = json.loads(Path(paths['json']).read_text())
        self.assertEqual(report['summary']['acceptance'], {'passed':0, 'total':1})
        self.assertIsNone(report['summary']['whole_workload_cost']['usd'])
        for path in paths.values():
            self.assertNotIn('PRIVATE-TASK-CONTENT', Path(path).read_text())

    def test_live_flag_cannot_bypass_unknown_capacity_or_context_stop(self):
        packet = json.loads(self.packet_path.read_text())
        packet['user_choice_id'] = 'candidate-0'
        for candidate in packet['candidates']:
            candidate['context_window'] = None
        packet['context']['delegation_allowed'] = False
        self.packet_path.write_text(json.dumps(packet))
        decision = self.cli('route', '--input', str(self.packet_path), '--live')
        self.assertEqual(decision['action'], 'coordinator')
        self.assertIsNone(decision['selected_configuration_id'])
        self.assertEqual(decision['reason_codes'], ['explicit-choice-unavailable'])
        self.assertEqual(decision['router']['attempts'], 0)
        for c in decision['candidates']:
            self.assertIn('unknown-capacity', c['reasons'])
            self.assertIn('context-stop', c['reasons'])

    def test_native_output_opt_in_survives_cli_recheck_and_report(self):
        self.root = self.directory / 'native-state'
        self.cli('init', '--mode', 'off', '--baseline-id', 'candidate-2', '--allow-host-managed-output')
        packet = json.loads(self.packet_path.read_text())
        packet['synthetic'] = False  # A local subprocess contract fixture, never a worker-quality claim.
        packet['task']['acceptance_gates'].append('complete-output')
        for c in packet['candidates']:
            c.update(max_output_tokens=None, output_limit_source='native-host')
        self.packet_path.write_text(json.dumps(packet))
        d = self.cli('route', '--input', str(self.packet_path))
        self.assertEqual(d['action'], 'route')
        self.assertEqual(self.cli('recheck','--decision',d['id'],'--input',str(self.packet_path))['recheck'], 'passed')
        paths = self.cli('report')
        report = json.loads(Path(paths['json']).read_text())
        row = report['decisions'][0]['candidates'][0]
        self.assertEqual(row['output_limit_source'], 'native-host')
        self.assertIsNone(row['max_output_tokens'])
        self.assertIn('limit unreported',Path(paths['html']).read_text())
        p = json.loads((self.root/'policy.json').read_text()); p['allow_host_managed_output'] = False
        (self.root/'policy.json').write_text(json.dumps(p))
        self.assertEqual(self.cli('recheck','--decision',d['id'],'--input',str(self.packet_path),ok=False)['error'], 'decision-inputs-changed')


if __name__ == '__main__': unittest.main()
