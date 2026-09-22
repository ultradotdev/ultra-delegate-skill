import copy
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_pilot_native_capacity as native_tests
import capability_index as research
import pilot_codex
import pilot_core as core


class CapabilityIndexTests(unittest.TestCase):
    def setUp(self):
        self.index = research.load()
        self.today = self.index['reviewed_on']

    def test_shipped_claims_are_distinct_and_not_benchmark_results(self):
        data = research.report(self.index, self.today)
        self.assertEqual(data['counts']['provider_claims'], 5)
        self.assertEqual(data['counts']['benchmark_results'], 0)
        providers = [r for r in data['claims'] if r['kind'] == 'provider-claim']
        self.assertEqual(len({r['summary'] for r in providers}), 5)
        self.assertEqual(data['counts']['capability_priors'], 266)
        self.assertEqual(data['counts']['native_mapped_priors'], 5)
        self.assertTrue(all(r['evaluation_age_days'] is None for r in data['claims']))
        self.assertTrue(all(r['flags'] == ['provider-claim-not-evaluation'] for r in providers))
        self.assertNotIn('artificialanalysis', json.dumps(self.index).lower())

    def benchmark(self):
        source = next(s for s in self.index['sources'] if s['id'] == 'swe-bench')
        source.update(use='curated-summary', published_on=None)
        row = {'id': 'synthetic-benchmark', 'source_id': source['id'], 'provider': 'openai',
               'model': 'test-model', 'effort': 'medium', 'kind': 'benchmark-result',
               'summary': 'Synthetic test observation, not a real score.',
               'evaluated_on': '2025-01-01', 'benchmark': 'synthetic-board-v1', 'harness': 'test-agent-v1'}
        self.index['claims'].append(row)
        return row

    def test_recent_retrieval_does_not_refresh_old_evaluation(self):
        self.benchmark()
        row = research.report(self.index, self.today)['claims'][-1]
        self.assertEqual(row['source_check_age_days'], 0)
        self.assertGreater(row['evaluation_age_days'], 180)
        self.assertIn('old-evaluation', row['flags'])
        description = research.describe(self.index, 'openai', 'test-model', 'medium', as_of=self.today)
        self.assertIn('old-evaluation', description)
        self.assertIn('synthetic-board-v1', description)

    def test_unknown_dates_and_effort_are_not_invented(self):
        row = self.benchmark()
        row.update(evaluated_on=None, effort=None)
        result = research.report(self.index, self.today)['claims'][-1]
        self.assertIsNone(result['evaluation_age_days'])
        self.assertIn('evaluation-date-unknown', result['flags'])
        self.assertIn('evaluated-effort-unknown', result['flags'])
        self.assertIn('No matching research', research.describe(self.index, 'openai', 'test-model', 'medium', as_of=self.today))

    def test_model_provider_and_evaluated_effort_match_exactly(self):
        self.benchmark()
        for provider, model, effort in [('other', 'test-model', 'medium'), ('openai', 'test', 'medium'),
                                        ('openai', 'test-model', 'low'), ('openai', 'test-model-v2', 'medium')]:
            with self.subTest(provider=provider, model=model, effort=effort):
                self.assertIn('No matching research', research.describe(self.index, provider, model, effort, as_of=self.today))

    def test_review_due_labels_without_hiding_candidates_or_claims(self):
        future = (dt.date.fromisoformat(self.today) + dt.timedelta(days=31)).isoformat()
        result = research.report(self.index, future)
        self.assertEqual(result['counts']['sources_review_due'], len(self.index['sources']))
        self.assertEqual(len(result['claims']), len(self.index['claims']))

    def test_invalid_provenance_and_unknown_fields_fail(self):
        mutations = [lambda x: x['sources'][0].update(url='javascript:alert(1)'),
                     lambda x: x['sources'][0].update(url='https://example.test/a b'),
                     lambda x: x['sources'][0].update(url='https://example.test:bad/'),
                     lambda x: x['sources'][0].update(checked_on='2027-01-01'),
                     lambda x: x['claims'][0].update(source_id='unknown'),
                     lambda x: x['sources'][0].update(use='reference-only'),
                     lambda x: x['claims'][0].update(accepted=True),
                     lambda x: x['claims'].append(copy.deepcopy(x['claims'][0]))]
        for mutation in mutations:
            index = copy.deepcopy(self.index)
            mutation(index)
            with self.assertRaises(core.PilotError): research.validate(index)
        with self.assertRaises(core.PilotError): research.report(self.index, '2025-01-01')

    def test_report_escapes_embedded_html(self):
        self.index['claims'][0]['summary'] = '<script>alert("not an instruction")</script>'
        rendered = research.render_html(research.report(self.index, self.today))
        self.assertNotIn('<script>alert', rendered)
        self.assertIn('&lt;script&gt;', rendered)

    def test_research_only_changes_description_and_packet_hash(self):
        task, catalog, host = native_tests.PilotCodexPacketTests().inputs()
        host['observed_at'] = self.today+'T12:00:00+00:00'
        self.index['claims'][0]['model'] = 'model-a'
        args = (task, catalog, host, ['model-a:medium'], 'Bounded patch.', 'One module.')
        baseline = pilot_codex.build_packet(*args)
        enriched = pilot_codex.build_packet(*args, capability_index=self.index)
        original, modified = baseline['candidates'][0], enriched['candidates'][0]
        self.assertNotEqual(core.digest(baseline), core.digest(enriched))
        self.assertEqual(core.configuration_id(original), core.configuration_id(modified))
        self.assertIn(core.digest(self.index), modified['capability_description'])
        for key in original:
            if key != 'capability_description': self.assertEqual(original[key], modified[key], key)
        policy = core.policy({'excluded_models': ['model-a']})
        before = core.prepare(baseline, policy, clock=core.timestamp(host['observed_at']))
        after = core.prepare(enriched, policy, clock=core.timestamp(host['observed_at']))
        self.assertFalse(after['rows'][0]['eligible'])
        self.assertEqual(before['rows'][0]['reasons'], after['rows'][0]['reasons'])

    def test_description_overflow_is_rejected_not_truncated(self):
        for i in range(12):
            claim = copy.deepcopy(self.index['claims'][0])
            claim.update(id='long-'+str(i), summary='x'*700)
            self.index['claims'].append(claim)
        with self.assertRaises(core.PilotError):
            research.describe(self.index, 'openai', 'gpt-6-astra', 'low', as_of=self.today)

    def test_bounded_file_read_and_cli_offline_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            bad = directory/'large.json'
            bad.write_bytes(b' '* (research.MAX_BYTES+1))
            with self.assertRaises(core.PilotError): research.load(bad)
            output = directory/'reports'
            command = [sys.executable, '-I', '-S', research.__file__, '--output-dir', str(output), '--as-of', self.today]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((output/'report.json').read_text())
            self.assertEqual(data['index_hash'], core.digest(self.index))
            self.assertTrue((output/'report.html').is_file())
            repeated = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(repeated.returncode, 2)
            self.assertNotIn('Traceback', repeated.stderr)

    def test_generated_reference_matches_json(self):
        self.assertEqual(research.DEFAULT_DOC.read_text(), research.render_markdown(research.report(self.index, self.today)))


if __name__ == '__main__':
    unittest.main()
