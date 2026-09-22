import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_capability_index  # Establish standalone script imports.
import capability_index as research
import epoch_import as epoch
import pilot_codex
import pilot_core as core
import pilot_questions
import test_pilot_native_capacity as native_tests


def export(rows=None):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['Model', 'Organization', 'eci', 'eci_ci_low', 'eci_ci_high', 'date'])
    writer.writerows(rows if rows is not None else [
        ['GPT-6 Astra', 'OpenAI', '160', '158', '162', '2026-09-03'],
        ['GPT-5.6 Luna', 'OpenAI', '150', '149', '151', '2026-07-09'],
        ['GPT-5.5 Pro', 'OpenAI', '180', '175', '190', '2026-04-23'],
    ])
    return stream.getvalue().encode()


class EpochImportTests(unittest.TestCase):
    def setUp(self):
        self.index = research.load()
        self.day = self.index['reviewed_on']

    def imported(self, raw=None):
        return epoch.import_scores(self.index, export() if raw is None else raw, self.day, 'test-update')

    def test_exact_mapping_replaces_snapshot_and_preserves_other_sources(self):
        result = self.imported()
        rows = [r for r in result['claims'] if r['kind'] == 'capability-prior']
        self.assertEqual({r['model'] for r in rows if r['metric']['native_identity']}, {'gpt-6-astra', 'gpt-5.6-luna'})
        self.assertEqual({r['metric']['source_model'] for r in rows}, {'GPT-6 Astra', 'GPT-5.6 Luna', 'GPT-5.5 Pro'})
        self.assertEqual(result['claims'][:5], self.index['claims'][:5])
        self.assertEqual(len([s for s in result['sources'] if s['id'] == epoch.SOURCE_ID]), 1)
        source = result['sources'][-1]
        self.assertEqual(source['revision'], 'sha256:'+hashlib.sha256(export()).hexdigest())
        self.assertEqual(source['license'], 'CC-BY-4.0')
        self.assertIn('Scored rows normalized', source['attribution'])
        self.assertEqual(self.index, research.load())

    def test_release_date_is_never_evaluation_date(self):
        result = self.imported()
        row = next(r for r in result['claims'] if r['kind'] == 'capability-prior' and r['model'] == 'gpt-6-astra')
        self.assertEqual(row['metric']['model_release_on'], '2026-09-03')
        self.assertIsNone(row['evaluated_on'])
        self.assertIsNone(row['effort'])
        self.assertIsNone(row['harness'])
        reported = next(r for r in research.report(result, self.day)['claims'] if r['id'] == row['id'])
        self.assertIsNone(reported['evaluation_age_days'])
        self.assertIn('model-level-prior', reported['flags'])

    def test_prior_applies_across_efforts_but_not_model_variants(self):
        result = self.imported()
        for effort in ('low', 'medium', 'high'):
            description = research.describe(result, 'openai', 'gpt-6-astra', effort, as_of=self.day)
            self.assertIn('Epoch general ECI 160', description)
            self.assertIn('not an effort-specific score', description)
            self.assertIn('Epoch AI CC-BY-4.0', description)
        for provider, model in [('other', 'gpt-6-astra'), ('openai', 'gpt-6'), ('openai', 'gpt-5.5-pro')]:
            self.assertNotIn('Epoch general ECI 160', research.describe(result, provider, model, 'low', as_of=self.day))

    def test_bad_numeric_intervals_duplicates_and_dates_fail(self):
        for values in [('NaN', '158', '162'), ('160', '170', '180'), ('160', '158', 'Infinity'),
                       ('not-a-score', '158', '162')]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.imported(export([['GPT-6 Astra', 'OpenAI', *values, '2026-09-03']]))
        for rows in [
            [['GPT-6 Astra', 'Other', '160', '158', '162', '2026-09-03']],
            [['GPT-6 Astra', 'OpenAI', '160', '158', '162', '2099-01-01']],
            [['GPT-6 Astra', 'OpenAI', '160', '158', '162', '2026-09-03']]*2,
        ]:
            with self.assertRaises(ValueError): self.imported(export(rows))
        for raw in (b'x,y\n1,2\n', b'\xff', b'x'*(research.MAX_BYTES+1)):
            with self.assertRaises(ValueError): self.imported(raw)

    def test_missing_score_removes_old_prior_without_filling_zero(self):
        result = self.imported(export([
            ['GPT-6 Astra', 'OpenAI', '', '', '', '2026-09-03'],
            ['GPT-5.6 Luna', 'OpenAI', '150', '149', '151', '2026-07-09'],
        ]))
        self.assertEqual([r['model'] for r in result['claims'] if r['kind'] == 'capability-prior'], ['gpt-5.6-luna'])

    def test_metric_text_and_structured_value_cannot_disagree(self):
        for field, value in [('value', 900), ('ci_level', .95), ('value', True)]:
            result = self.imported()
            result['claims'][-1]['metric'][field] = value
            with self.assertRaises(ValueError): research.validate(result)
        result = self.imported()
        result['sources'][-1].pop('attribution')
        with self.assertRaises(ValueError): research.validate(result)

    def test_cli_offline_and_no_overwrite_or_raw_error_echo(self):
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp)/'source.csv', Path(temp)/'index.json'
            source.write_bytes(export())
            command = [sys.executable, '-I', '-S', epoch.__file__, '--scores', str(source),
                       '--retrieved-on', self.day, '--version', 'test-cli', '--output', str(target)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['network_requests'], 0)
            before = target.read_bytes()
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertEqual(before, target.read_bytes())
            source.write_bytes(export([['GPT-6 Astra', 'OpenAI', 'PRIVATE-SENTINEL', '0', '200', '2026-09-03']]))
            failed = subprocess.run(command, capture_output=True, text=True)
            self.assertNotIn('PRIVATE-SENTINEL', failed.stderr+failed.stdout)

    def test_native_packet_receives_scores_but_keeps_identity_and_gates(self):
        task, catalog, host = native_tests.PilotCodexPacketTests().inputs()
        catalog['models'][0]['slug'] = 'gpt-6-astra'
        host['models'] = {'gpt-6-astra': ['medium']}
        host['observed_at'] = self.day+'T12:00:00+00:00'
        args = (task, catalog, host, ['gpt-6-astra:medium'], 'Bounded code repair.', 'One module.')
        bare = pilot_codex.build_packet(*args)
        enriched = pilot_codex.build_packet(*args, capability_index=self.imported())
        first, second = bare['candidates'][0], enriched['candidates'][0]
        self.assertEqual(core.configuration_id(first), core.configuration_id(second))
        self.assertIsNone(second['estimate_usd'])
        self.assertIn('Epoch general ECI 160', second['capability_description'])
        for field in first:
            if field != 'capability_description': self.assertEqual(first[field], second[field])
        self.assertNotEqual(core.digest(bare), core.digest(enriched))

    def test_broad_catalog_keeps_organizations_versions_and_unknown_mappings(self):
        result = self.imported(export([
            ['Claude Fable 5.1', 'Anthropic', '165', '160', '170', '2026-08-01'],
            ['Gemini 3.1 Pro', 'Google DeepMind', '155', '152', '157', '2026-01-01'],
            ['GPT-4 (Mar 2023)', 'OpenAI', '120', '118', '122', '2023-03-14'],
            ['Mystery model', '', '100', '95', '105', '2024-01-01'],
        ]))
        rows = [r for r in result['claims'] if r['kind'] == 'capability-prior']
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r['provider'] == 'research' and r['metric']['native_identity'] is None for r in rows))
        self.assertIn(None, [r['metric']['source_organization'] for r in rows])
        for row in rows:
            self.assertIn('No matching research', research.describe(result, 'research', row['model'], 'medium', as_of=self.day))

    def test_explicit_extra_mapping_can_attach_another_provider_without_executing_it(self):
        raw = export([['Test Claude', 'Anthropic', '160', '155', '165', '2026-01-01']])
        mappings = [{'source_model': 'Test Claude', 'source_organization': 'Anthropic',
                     'provider': 'anthropic', 'model': 'test-claude-id'}]
        result = epoch.import_scores(self.index, raw, self.day, 'new-map', mappings)
        self.assertIn('Epoch general ECI 160', research.describe(result, 'anthropic', 'test-claude-id', 'low', as_of=self.day))
        self.assertIn('No matching research', research.describe(result, 'openai', 'test-claude-id', 'low', as_of=self.day))
        with self.assertRaises(ValueError): epoch.import_scores(self.index, raw, self.day, 'bad-map', mappings*2)

    def test_missing_interval_is_kept_unknown_instead_of_dropping_model(self):
        result = self.imported(export([['GPT-5', 'OpenAI', '150', '', '', '2025-08-07']]))
        row = next(r for r in result['claims'] if r['kind'] == 'capability-prior')
        self.assertEqual(row['metric']['value'], 150)
        self.assertIsNone(row['metric']['ci_level'])
        self.assertIn('confidence interval not reported', row['summary'])
        self.assertIn('Not reported', research.render_html(research.report(result, self.day)))
        with self.assertRaises(ValueError):
            self.imported(export([['GPT-5', 'OpenAI', '150', '140', '', '2025-08-07']]))

    def test_five_model_packet_fits_wire_limit_with_research_in_each_card(self):
        task, catalog, host = native_tests.PilotCodexPacketTests().inputs()
        template = catalog['models'][0]
        models = list(epoch.MODEL_MAP.values())
        catalog['models'] = [{**copy.deepcopy(template), 'slug': model} for model in models]
        host.update(models={model: ['medium'] for model in models}, observed_at=self.day+'T12:00:00+00:00')
        packet = pilot_codex.build_packet(task, catalog, host, [m+':medium' for m in models],
                                         'Bounded code repair.', 'One module.', capability_index=self.index)
        policy = core.policy()
        prepared = core.prepare(packet, policy, clock=core.timestamp(host['observed_at']))
        self.assertEqual(len(prepared['cards']), 5)
        self.assertTrue(all(not card['evidence_cohorts'] for card in prepared['cards']))
        payload = pilot_questions.route_payload(packet['task'], prepared['cards'], policy['model'])
        encoded = core.transport.encoded_payload(payload)
        self.assertLessEqual(len(encoded), core.transport.REQUEST_LIMIT)
        for card in payload['state']['candidates']:
            self.assertIn('Epoch general ECI', card['capability_description'])


if __name__ == '__main__':
    unittest.main()
