"""Security signals cannot publish an outcome without independent disposition."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'.agents/skills/ultra-delegation/scripts'))
import pilot
import pilot_core as core
import pilot_security as security
import pilot_learning


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.p = pilot.init_project(self.root, {'mode':'active','share_summaries':True,'share_artifacts':True})
        self.packet = pilot.fixture()
        self.d = pilot.route_packet(self.packet, self.p)
        pilot.write_new(self.root/'decisions'/(self.d['id']+'.json'), self.d)
        self.raw = pilot.outcome_fixture(self.d, self.d['selected_configuration_id'])
        boundaries = self.packet['task']['boundaries']
        self.input = {'boundaries':boundaries,'requirements':boundaries['security_requirements']['items'],
                      'excerpts':['def harmless(): return 1'], 'validation_summary':'Focused test passed.'}
        self.calls = 0

    def call(self, probability=.95, sufficient=.99):
        def invoke(payload, key):
            self.calls += 1
            result, usage = pilot.synthetic_response(payload, key)
            result['answers']['violation_0']['noul'] = probability
            result['answers']['sufficient_0']['noul'] = sufficient
            return result, usage
        return invoke

    def assess(self, **kwargs):
        return security.prepare(self.root,self.raw,self.d,self.p,self.input,enabled=True,live=True,key='fake-key',**kwargs)

    def findings(self, assessment, disposition='dismissed', severity='low', coordinator=None, scope='delivered'):
        return {'assessment_id':assessment['assessment_id'],'artifact_hash':self.raw['artifact_hash'],
                'reviewer_id':'independent-security-reviewer','reviewer_kind':'frontier',
                'reviewed_requirements':[self.input['requirements'][0]['id']],
                'findings':[{'id':'finding-1','requirement_id':self.input['requirements'][0]['id'],
                            'disposition':disposition,'severity':severity,'scope':scope,'coordinator_disposition':coordinator,
                            'location':'example.py:1','evidence':'Local review evidence sentinel.',
                            'consequence':'No external effects in the delivered function.', 'correction':'No correction needed after independent review.'}]}

    def test_probability_boundaries_and_independent_insufficiency(self):
        for probability,sufficiency,signal in [(0,.99,'no-concern'),(.20,.80,'no-concern'),(.20001,.99,'investigate'),
             (.79999,.99,'investigate'),(.80,.99,'strong-concern'),(.99,.7999,'insufficient-evidence'),(.05,.85,'no-concern')]:
            with self.subTest(probability=probability,sufficiency=sufficiency):
                result=security.evaluate(self.input,self.p,True,live=True,call=self.call(probability,sufficiency),key='fake')
                self.assertEqual(result['requirements'][0]['signal'],signal)

    def test_followup_persists_but_does_not_publish_or_pay_twice(self):
        with self.assertRaisesRegex(core.PilotError,'security-follow-up-required'):
            pilot.observe(self.root,self.raw,security_input=self.input,security_check=True,live=True,call=self.call(),key='fake')
        self.assertFalse(list((self.root/'outcomes').glob('*.json')))
        assessment=self.assess(call=self.call())
        result=pilot.observe(self.root,self.raw,security_findings=self.findings(assessment),live=True,call=self.call(),key='fake')
        self.assertEqual(self.calls,1)
        self.assertTrue(result['accepted']); self.assertTrue(result['security']['reviewed'])
        self.assertNotIn('Local review evidence sentinel',json.dumps(result))
        exported=pilot_learning.export(self.root)
        self.assertNotIn('violation_probability',json.dumps(exported))
        self.assertNotIn('security_review',json.dumps(exported))
        self.assertTrue((self.root/result['security']['details_ref']).exists())

    def test_confirmed_mandatory_violation_rejects_and_export_preserves_failure(self):
        assessment=self.assess(call=self.call(.01))
        result=pilot.observe(self.root,self.raw,security_findings=self.findings(assessment,'confirmed'))
        self.assertFalse(result['accepted']); self.assertEqual(result['scores'],self.raw['scores'])
        self.assertFalse(next(g for g in result['gates'] if g['id']=='security-review')['passed'])
        exported=pilot_learning.export(self.root)
        other=self.root/'imported';pilot.init_project(other)
        pilot_learning.import_bundle(other,exported)
        self.assertFalse(pilot.load_records(other,'outcomes')[0]['accepted'])

    def test_ordinary_review_confirmed_critical_rejects_with_screening_off(self):
        assessment=security.prepare(self.root,self.raw,self.d,self.p)
        findings=self.findings(assessment,'confirmed','critical')
        findings['findings'][0]['requirement_id']=None
        result=pilot.observe(self.root,self.raw,security_findings=findings)
        self.assertFalse(result['accepted']);self.assertEqual(result['security']['mode'],'off')
        self.assertEqual(self.calls,0)

    def test_unresolved_requires_explicit_disposition(self):
        assessment=self.assess(call=self.call())
        with self.assertRaisesRegex(core.PilotError,'unresolved-security-finding'):
            pilot.observe(self.root,self.raw,security_findings=self.findings(assessment,'unresolved'))
        result=pilot.observe(self.root,self.raw,security_findings=self.findings(assessment,'unresolved',coordinator='accept-with-limitation'))
        self.assertTrue(result['accepted']);self.assertEqual(result['security']['findings'][0]['disposition'],'unresolved')

    def test_unrelated_preexisting_does_not_fail_but_cannot_hide_task_obligation(self):
        assessment=self.assess(call=self.call(.01))
        findings=self.findings(assessment,'confirmed','critical',scope='pre-existing')
        with self.assertRaisesRegex(core.PilotError,'task-obligation-not-unrelated'):
            pilot.observe(self.root,self.raw,security_findings=findings)
        findings['findings'][0]['requirement_id']=None
        self.assertTrue(pilot.observe(self.root,self.raw,security_findings=findings)['accepted'])

    def test_changed_artifact_gets_fresh_assessment_changed_input_same_artifact_rejected(self):
        first=self.assess(call=self.call(.01))
        self.input['excerpts']=['changed code']
        with self.assertRaisesRegex(core.PilotError,'security-inputs-changed'):self.assess(call=self.call(.01))
        self.raw['artifact_hash']=core.digest('fixed artifact')
        second=self.assess(call=self.call(.01))
        self.assertNotEqual(first['assessment_id'],second['assessment_id']);self.assertEqual(self.calls,2)

    def test_dry_run_no_files_no_credentials_and_bindings_checked(self):
        before=set(self.root.rglob('*'))
        with patch.object(core.transport,'credential',side_effect=AssertionError):
            preview=security.prepare(self.root,self.raw,self.d,self.p,self.input,enabled=True,dry_run=True)
        self.assertEqual(before,set(self.root.rglob('*')));self.assertIn('payload',preview)
        bad=copy.deepcopy(self.input);bad['boundaries']['allowed_actions']['items']=['Changed scope']
        with self.assertRaisesRegex(core.PilotError,'security-boundaries-changed'):
            security.prepare(self.root,self.raw,self.d,self.p,bad,enabled=True,dry_run=True)

    def test_sharing_separate_and_technical_failure_does_not_reject(self):
        self.p['share_artifacts']=False
        (self.root/'policy.json').write_text(json.dumps(self.p))
        with patch.object(core.transport,'credential',side_effect=AssertionError):
            result=pilot.observe(self.root,self.raw,security_check=True,security_input=self.input,live=True)
        self.assertTrue(result['accepted']);self.assertEqual(result['security']['reason_codes'],['artifact-sharing-disabled'])

    def test_sensitive_task_requires_native_review_even_when_screening_off(self):
        self.d['security_sensitive']=True
        with self.assertRaisesRegex(core.PilotError,'security-follow-up-required'):
            security.complete(self.root,self.raw,self.d,self.p)

    def test_interrupted_call_not_repeated(self):
        def interrupt(payload,key):
            self.calls+=1
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.assess(call=interrupt)
        result=self.assess(call=self.call())
        self.assertEqual(result['reason_codes'],['interrupted-evaluation-not-repeated']);self.assertEqual(self.calls,1)

    def test_disabled_assessment_does_not_poison_later_enabled_run(self):
        off=security.prepare(self.root,self.raw,self.d,self.p)
        self.assertEqual(off['mode'],'off')
        self.assertEqual(self.assess(call=self.call(.01))['status'],'pass');self.assertEqual(self.calls,1)

    def test_invalid_responses_are_unavailable_and_redacted(self):
        def bad(payload,key):return {'secret-provider':'SECRET'}, {'attempts':1,'latency_ms':1}
        result=security.evaluate(self.input,self.p,True,live=True,call=bad,key='SECRET')
        self.assertEqual(result['status'],'unavailable');self.assertNotIn('SECRET',json.dumps(result))

    def test_changing_policy_does_not_erase_pending_concern(self):
        self.assess(call=self.call())
        changed=core.policy({**self.p,'security_thresholds':{'investigate':.3,'strong':.8,'sufficient':.8}})
        with self.assertRaisesRegex(core.PilotError,'security-settings-changed-review-required'):
            security.complete(self.root,self.raw,self.d,changed)
        fresh=security.prepare(self.root,self.raw,self.d,changed,self.input,enabled=True,live=True,call=self.call(.01),key='fake')
        self.assertTrue(fresh['follow_up_required'])
        self.assertIn('prior-artifact-concern-requires-review',fresh['reason_codes'])

    def test_unavailable_reassessment_cannot_drop_prior_finding_disposition(self):
        self.assess(call=self.call())
        changed=core.policy({**self.p,'security_thresholds':{'investigate':.3,'strong':.8,'sufficient':.8}})
        def unavailable(payload,key):return {},{'attempts':1,'latency_ms':1}
        fresh=security.prepare(self.root,self.raw,self.d,changed,self.input,enabled=True,live=True,call=unavailable,key='fake')
        self.assertEqual(fresh['status'],'unavailable')
        self.assertEqual(fresh['required_finding_ids'],[self.input['requirements'][0]['id']])
        document=self.findings(fresh);document['findings']=[]
        with self.assertRaisesRegex(core.PilotError,'security-follow-up-incomplete'):
            security.complete(self.root,self.raw,self.d,changed,findings=document)
        valid=self.findings(fresh)
        result,_=security.complete(self.root,self.raw,self.d,changed,findings=valid)
        self.assertTrue(result['reviewed'])

    def test_configure_thresholds_preserves_separate_sharing_permission(self):
        import contextlib,io
        with contextlib.redirect_stdout(io.StringIO()):
            code=pilot.main(['--root',str(self.root),'configure','--security-sufficient','0.8'])
        self.assertEqual(code,0)
        p=pilot.load_policy(self.root)
        self.assertEqual(p['security_thresholds']['sufficient'],.8)
        self.assertFalse(p['security_check'])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(pilot.main(['--root',str(self.root),'configure','--security-sufficient','2']),2)
        self.assertEqual(pilot.load_policy(self.root),p)

    def test_default_is_point_eight_and_explicit_project_cutoff_is_preserved(self):
        self.assertEqual(core.policy()['security_thresholds']['sufficient'], .80)
        custom = {'investigate': .20, 'strong': .80, 'sufficient': .90}
        self.assertEqual(core.policy({'security_thresholds': custom})['security_thresholds'], custom)

    def test_policy_bands_are_bounded(self):
        for bands in ({'investigate':.9,'strong':.8,'sufficient':.9},{'investigate':0,'strong':1,'sufficient':2}):
            with self.assertRaises(core.PilotError):core.policy({'security_thresholds':bands})

if __name__=='__main__':unittest.main()
