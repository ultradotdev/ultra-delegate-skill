import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

S = importlib.util.spec_from_file_location('pilot_smoke', Path(__file__).resolve().parents[1]/'scripts/pilot_smoke.py')
smoke = importlib.util.module_from_spec(S)
S.loader.exec_module(smoke)


class PilotSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'fresh'

    def test_offline_never_reads_credentials_or_opens_network(self):
        with patch.object(smoke.transport, 'credential', side_effect=AssertionError), patch.object(smoke.transport, 'request', side_effect=AssertionError):
            report = smoke.run(self.root)
        self.assertEqual(report['passed'], 3)
        self.assertEqual(report['http_attempts'], 0)
        self.assertEqual(report['transport'], 'mock')
        self.assertEqual(report['worker_executions'], 0)

    def test_output_is_reserved_before_live_lookup(self):
        self.root.mkdir()
        with patch.object(smoke.transport, 'credential', side_effect=AssertionError), self.assertRaises(FileExistsError):
            smoke.run(self.root, live=True)

    def test_missing_key_stays_pending_without_network(self):
        with patch.object(smoke.transport, 'credential', side_effect=smoke.transport.ServiceError('missing-credential')), patch.object(smoke.transport, 'request', side_effect=AssertionError):
            report = smoke.run(self.root, live=True)
        self.assertEqual(report['status'], 'pending')
        self.assertEqual(report['http_attempts'], 0)

    def test_auth_failure_stops_remaining_cases_and_disables_retries(self):
        with patch.object(smoke.transport, 'credential', return_value=('SECRET-SENTINEL','environment')), patch.object(smoke.transport, 'request', side_effect=smoke.transport.ServiceError('authentication-failed',1)) as request:
            report = smoke.run(self.root, live=True)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.kwargs, {'max_attempts':1})
        self.assertEqual(report['status'], 'incomplete')
        self.assertEqual(report['pending_cases'], 2)
        self.assertEqual(report['http_attempts'], 1)
        for path in self.root.rglob('*.json'):
            self.assertNotIn('SECRET-SENTINEL', path.read_text())


if __name__ == '__main__': unittest.main()
