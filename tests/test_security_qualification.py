import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import security_qualification as q

class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'qualification';q.prepare(self.root)
        self.review={'fixture_hash':q.core.digest(q.pilot.read_json(self.root/'fixtures.json')),
                     'reviewer_id':'independent-test-reviewer','independent':True,'approved':True,'findings':['Verified toy reference findings.']}
        q.pilot.write_new(self.root/'reference-review.json',self.review)

    def test_offline_lifecycle_freezes_before_heldout_and_never_reads_credential(self):
        with patch.object(q.transport,'credential',side_effect=AssertionError):
            with self.assertRaises(OSError):q.run(self.root,'heldout')
            q.run(self.root,'development');frozen=q.freeze(self.root);q.run(self.root,'heldout')
        report=q.pilot.read_json(self.root/'report.json')
        self.assertEqual(report['frozen'],frozen)
        self.assertEqual(report['splits']['development']['available'],6)
        self.assertEqual(report['splits']['heldout']['available'],4)
        self.assertEqual(report['splits']['heldout']['insufficient_context_misses'],0)
        self.assertEqual({r['transport'] for r in report['cases']},{'mock'})
        self.assertTrue((self.root/'report.html').exists())

    def test_references_cannot_change_after_approval(self):
        self.review['fixture_hash']='0'*64
        (self.root/'reference-review.json').write_text(__import__('json').dumps(self.review))
        with self.assertRaisesRegex(ValueError,'references-changed'):q.run(self.root,'development')

    def test_resume_live_calls_once_and_no_holdout_before_freeze(self):
        calls=[]
        def call(payload,key):
            calls.append(payload);return q.pilot.synthetic_response(payload,key)
        q.run(self.root,'development',live=True,call=call,key='fixture')
        q.run(self.root,'development',live=True,call=call,key='fixture')
        self.assertEqual(len(calls),6)
        q.freeze(self.root)
        q.run(self.root,'heldout',live=True,call=call,key='fixture')
        self.assertEqual(len(calls),10)

    def test_development_changes_invalidate_freeze(self):
        q.run(self.root,'development');q.freeze(self.root)
        path=next((self.root/'development').glob('*.json'))
        record=q.pilot.read_json(path);record['assessment']['latency_ms']=999
        path.write_text(__import__('json').dumps(record))
        with self.assertRaisesRegex(ValueError,'qualification-record-changed'):q.run(self.root,'heldout')

    def test_resealed_fixture_metadata_tampering_is_rejected(self):
        q.run(self.root,'development')
        path=next((self.root/'development').glob('*.json'))
        row=q.pilot.read_json(path);row.pop('integrity');row['fixture_hash']='0'*64
        row['integrity']=q.core.digest(row)
        path.write_text(__import__('json').dumps(row))
        with self.assertRaisesRegex(ValueError,'qualification-fixture-changed'):q.freeze(self.root)

    def test_alternate_reference_review_cannot_replace_frozen_reviewer(self):
        q.run(self.root,'development');q.freeze(self.root)
        alternative={**self.review,'reviewer_id':'different-reviewer'}
        path=self.root/'alternate.json';q.pilot.write_new(path,alternative)
        with self.assertRaisesRegex(ValueError,'reference-review-changed'):
            q.run(self.root,'heldout',review_file=path)

    def test_legacy_development_report_preserves_actual_point_nine_cutoff(self):
        q.run(self.root,'development')
        for path in (self.root/'development').glob('*.json'):
            row=q.pilot.read_json(path);row.pop('integrity');row.pop('security_thresholds')
            if path.stem=='access-control-safe':
                row['assessment']['requirements'][0]['evidence_probability']=.85
            row['integrity']=q.core.digest(row)
            path.write_text(__import__('json').dumps(row))
        q.report(self.root)
        report=q.pilot.read_json(self.root/'report.json')
        self.assertEqual(report['shipped_default_bands']['sufficient'],.8)
        self.assertEqual(report['observed_bands']['development']['sufficient'],.9)
        self.assertEqual(report['splits']['development']['false_alarms'],1)
        self.assertIn('original 0.9 evidence cutoff',(self.root/'report.html').read_text())

    def test_resume_preserves_original_development_bands(self):
        with patch.object(q.security, 'BANDS', q.LEGACY_DEVELOPMENT_BANDS):
            q.run(self.root,'development')
        paths=sorted((self.root/'development').glob('*.json'))
        for path in paths[1:]:path.unlink()
        q.run(self.root,'development')
        self.assertEqual({r['security_thresholds']['sufficient'] for r in q.load_rows(self.root,'development')},{.9})

    def test_mixed_development_bands_rejected_before_inference(self):
        q.run(self.root,'development')
        path=next((self.root/'development').glob('*.json'))
        row=q.pilot.read_json(path);row.pop('integrity')
        row['security_thresholds']['sufficient']=.9
        row['integrity']=q.core.digest(row)
        path.write_text(__import__('json').dumps(row))
        with patch.object(q.transport,'credential',side_effect=AssertionError):
            with self.assertRaisesRegex(ValueError,'mixed-security-thresholds'):
                q.run(self.root,'development',live=True)
        with self.assertRaisesRegex(ValueError,'mixed-security-thresholds'):q.report(self.root)

    def test_unavailable_is_not_counted_as_pass_or_miss(self):
        row={'assessment':{'status':'unavailable'},'reference':{'requirements':[]}}
        metrics=q.metrics([row],q.security.BANDS)
        self.assertEqual(metrics['available'],0);self.assertEqual(metrics['unavailable'],1)
        self.assertIsNone(metrics['follow_up_rate']);self.assertFalse(metrics['cost_complete'])

if __name__=='__main__':unittest.main()
