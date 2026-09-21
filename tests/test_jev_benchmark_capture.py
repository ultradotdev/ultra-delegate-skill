"""Capture is explicit, bounded, credential-read-only and independently replayable."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/ultra-delegation/scripts'
sys.path.insert(0, str(SCRIPTS))
import jev_benchmark as b
import jev_benchmark_capture as c


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.data = b.demo()
        self.responses = {row['capture']['payload_hash']: row['capture']['response'] for row in self.data['cases']}
        for row in self.data['cases']:
            row['capture'] = None
        self.policy = copy.deepcopy(self.data['policy'])
        self.credential = Mock(return_value=('synthetic-private-value', 'environment'))
        self.call = Mock(side_effect=self.response)

    def response(self, payload, key):
        value = copy.deepcopy(self.responses[c.jev.hash_value(payload)])
        value['provider_debug'] = 'synthetic-private-value'
        for answer in value['answers'].values():
            answer['reasoning'] = 'untrusted-provider-prose'
        return value, {'attempts': 1, 'latency_ms': 25}

    def test_preview_never_looks_up_credentials_or_calls_api(self):
        result, summary = c.collect(self.data, self.policy, call=self.call, get_credential=self.credential)
        self.assertEqual(summary['status'], 'pending')
        self.call.assert_not_called(); self.credential.assert_not_called()
        self.assertTrue(all(row['capture'] is None for row in result['cases']))

    def test_live_bounded_capture_is_sanitized_and_replays(self):
        result, summary = c.collect(self.data, self.policy, live=True, max_calls=2, call=self.call, get_credential=self.credential)
        self.assertEqual(summary['captured'], 2)
        self.assertEqual(summary['status'], 'pending')
        self.assertEqual(self.call.call_count, 2)
        self.credential.assert_called_once_with(self.policy['jev']['credential_ref'], service=self.policy['jev']['credential_service'])
        self.assertNotIn('synthetic-private-value', json.dumps(result))
        self.assertNotIn('untrusted-provider-prose', json.dumps(result))
        self.assertEqual(result['cases'][0]['capture']['cost']['kind'], 'estimated')
        b.benchmark(result)

    def test_summary_permission_separate_from_artifacts(self):
        for field, value in [('routing', 'off'), ('share_summaries', False)]:
            policy = copy.deepcopy(self.policy); policy['jev'][field] = value
            _, summary = c.collect(self.data, policy, live=True, call=self.call, get_credential=self.credential)
            self.assertEqual(summary['reason'], 'routing-or-summary-sharing-disabled')
        self.call.assert_not_called(); self.credential.assert_not_called()
        # Artifact permission is not required: no outputs or references are sent.
        self.policy['jev']['share_artifacts'] = False
        self.data['policy']['jev']['share_artifacts'] = False
        _, summary = c.collect(self.data, self.policy, live=True, call=self.call, get_credential=self.credential)
        self.assertEqual(summary['status'], 'collected')
        for args, kwargs in self.call.call_args_list:
            self.assertNotIn('observations', args[0]['state'])
            self.assertNotIn('artifact_hash', json.dumps(args[0]))

    def test_shadow_policy_can_collect_active_recommendations_only(self):
        self.policy['jev']['routing'] = 'shadow'
        _, summary = c.collect(self.data, self.policy, live=True, max_calls=1, call=self.call, get_credential=self.credential)
        self.assertEqual(summary['captured'], 1)
        self.assertEqual(self.policy['jev']['routing'], 'shadow')
        self.policy['exclusions'] = ['synthetic']
        with self.assertRaisesRegex(ValueError, 'dataset-project-policy-mismatch'):
            c.collect(self.data, self.policy, live=True, call=self.call, get_credential=self.credential)

    def test_missing_credentials_stop_without_fanout(self):
        self.credential.side_effect = c.jev.transport.ServiceError('missing-credential')
        _, summary = c.collect(self.data, self.policy, live=True, call=self.call, get_credential=self.credential)
        self.assertEqual(summary['status'], 'pending')
        self.assertEqual(summary['cases'][0]['reason_codes'], ['missing-credential'])
        self.credential.assert_called_once(); self.call.assert_not_called()

    def test_existing_captures_are_reused_but_stale_capture_rejected(self):
        data = b.demo()
        _, summary = c.collect(data, data['policy'], live=True, call=self.call, get_credential=self.credential)
        self.assertEqual(summary['existing'], 8)
        self.call.assert_not_called(); self.credential.assert_not_called()
        data['cases'][0]['packet']['summary'] = 'A different task'
        with self.assertRaisesRegex(ValueError, 'stale-existing-capture'):
            c.collect(data, data['policy'], live=True, call=self.call, get_credential=self.credential)

    def test_output_errors_prevent_live_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'input.json'
            source.write_text(json.dumps(self.data))
            exists = root / 'existing.json'; exists.write_text('keep')
            for output in ([], ['--output', str(exists)], ['--output', str(root / 'missing' / 'result.json')]):
                with patch.object(c.jev.ud, 'load_policy', return_value=self.policy), patch.object(c.jev.transport, 'credential', self.credential), patch.object(c.jev.transport, 'request', self.call), patch('sys.stderr', new_callable=io.StringIO):
                    self.assertEqual(2, c.main(['--root', str(root), '--input', str(source), '--live', *output]))
            self.call.assert_not_called(); self.credential.assert_not_called()
            self.assertEqual(exists.read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
