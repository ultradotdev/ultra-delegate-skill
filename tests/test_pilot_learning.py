from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'.agents/skills/ultra-delegation/scripts'))
import pilot
import pilot_core as core
import pilot_learning as learning


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.p = pilot.init_project(self.root)
        packet = pilot.fixture()
        self.d = pilot.route_packet(packet, self.p)
        pilot.write_new(self.root/'decisions'/(self.d['id']+'.json'), self.d)
        self.o = pilot.observe(self.root, pilot.outcome_fixture(self.d, self.d['selected_configuration_id']))

    def test_retraction_preserves_original_and_invalidates_dispatch_evidence(self):
        learning.retract(self.root, self.o['id'], 'incorrect-review')
        self.assertEqual(pilot.load_records(self.root, 'outcomes'), [])
        self.assertEqual(len(pilot.load_records(self.root, 'outcomes', include_retracted=True)), 1)
        self.assertTrue((self.root/'outcomes'/(self.o['id']+'.json')).exists())
        with self.assertRaises(FileExistsError): learning.retract(self.root, self.o['id'], 'duplicate')

    def test_import_is_labeled_idempotent_and_rechecks_quality(self):
        bundle = learning.export(self.root)
        target = self.root/'imported'; pilot.init_project(target, {'dimension_floor':95})
        result = learning.import_bundle(target, bundle)
        self.assertEqual(result['imported'], 1)
        imported = pilot.load_records(target, 'outcomes')[0]
        self.assertEqual(imported['provenance'], 'imported-unverified')
        self.assertFalse(imported['accepted'])
        self.assertEqual(learning.import_bundle(target, bundle)['already_present'], 1)
        self.assertNotIn('reviewer_id', bundle['outcomes'][0])

    def test_export_import_export_import_keeps_one_source_observation_and_cost(self):
        bundle = learning.export(self.root)
        target = self.root/'imported'; pilot.init_project(target, {'dimension_floor':95})
        self.assertEqual(learning.import_bundle(target, bundle)['imported'], 1)
        first = learning.export(target)
        self.assertEqual(first['outcomes'][0]['provenance'], 'imported-unverified')
        self.assertEqual(first['outcomes'][0]['observation_origin'], bundle['outcomes'][0]['observation_origin'])
        self.assertEqual(first['outcomes'][0]['observation_hash'], bundle['outcomes'][0]['observation_hash'])
        cost = first['outcomes'][0]['costs']
        result = learning.import_bundle(target, first)
        self.assertEqual(result, {'imported': 0, 'already_present': 1, 'provenance': 'imported-unverified'})
        final = learning.export(target)
        self.assertEqual(len(final['outcomes']), 1)
        self.assertEqual(final['outcomes'][0]['costs'], cost)

    def test_import_preserves_failures_as_unverified_observations(self):
        failed_configuration = next(row['configuration_id'] for row in self.d['candidates']
                                    if row['configuration_id'] != self.o['configuration_id'])
        failed = pilot.outcome_fixture(self.d, failed_configuration, accepted=False)
        failed['reviewer_id'] = 'independent-reviewer'
        pilot.observe(self.root, failed)
        bundle = learning.export(self.root)
        target = self.root/'imported'; pilot.init_project(target)
        self.assertEqual(learning.import_bundle(target, bundle)['imported'], 2)
        imported = pilot.load_records(target, 'outcomes')
        failures = [row for row in imported if not row['accepted']]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]['provenance'], 'imported-unverified')
        self.assertEqual(learning.import_bundle(target, learning.export(target))['already_present'], 2)

    def test_tampered_and_extra_field_bundles_rejected(self):
        bundle = learning.export(self.root); bundle['outcomes'][0]['source'] = 'PRIVATE_CONTENT'
        target = self.root/'imported'; pilot.init_project(target)
        with self.assertRaises(core.PilotError): learning.import_bundle(target, bundle)
        bundle['content_hash'] = core.digest({k: bundle[k] for k in ('schema','outcomes')})
        with self.assertRaises(core.PilotError): learning.import_bundle(target, bundle)

    def test_origin_cannot_be_duplicated_by_changing_supplied_fingerprint(self):
        import copy
        bundle = learning.export(self.root)
        changed = copy.deepcopy(bundle['outcomes'][0])
        changed['observation_hash'] = '0' * 64
        bundle['outcomes'].append(changed)
        bundle['content_hash'] = core.digest({k: bundle[k] for k in ('schema', 'outcomes')})
        target = self.root/'conflicting'; pilot.init_project(target)
        with self.assertRaisesRegex(core.PilotError, 'learning-origin-conflict'):
            learning.import_bundle(target, bundle)
        self.assertEqual(pilot.load_records(target, 'outcomes'), [])
        bundle['outcomes'] = [changed]
        bundle['content_hash'] = core.digest({k: bundle[k] for k in ('schema', 'outcomes')})
        with self.assertRaisesRegex(core.PilotError, 'learning-origin-conflict'):
            learning.import_bundle(self.root, bundle)
        self.assertEqual(len(pilot.load_records(self.root, 'outcomes')), 1)


if __name__ == '__main__': unittest.main()
