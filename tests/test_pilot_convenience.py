import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'.agents/skills/ultra-delegation/scripts'))
import pilot
import pilot_codex
import pilot_core as core
import pilot_convenience as easy
import pilot_workflow as workflow


class ConvenienceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name); self.root = self.directory/'state'
        self.policy = pilot.init_project(self.root, {'mode':'active', 'share_summaries':True, 'bakeoff':'off'})
        self.packet = pilot.fixture(); self.packet['synthetic'] = False
        self.decision = pilot.route_packet(self.packet, self.policy, live=True, call=pilot.synthetic_response, key='fixture')
        pilot.write_new(self.root/'decisions'/(self.decision['id']+'.json'), self.decision)
        self.request = workflow.start(self.root, self.decision, self.packet, self.policy, 'off')

    def event(self, kind, **kw):
        return easy.event(self.root, self.request['id'], 'attempt-1', kind, packet=self.packet, **kw)

    def completed(self):
        self.event('launching')
        self.event('dispatched', run_id='native-run', configuration_id=self.request['attempts'][0]['configuration_id'],
                   checkout_hash='a'*64, base_revision='base')
        self.event('completed', artifact_hash='b'*64)

    def raw(self):
        raw = easy.review_template(self.root, self.request['id'], 'attempt-1')
        raw.update(reviewer_id='independent', reviewer_kind='frontier', review_accepted=True,
                   scores={k:90 for k in core.DIMENSIONS})
        for gate in raw['gates']: gate['passed']=True
        return raw

    def test_reinitialization_preserves_policy_and_records(self):
        before=(self.root/'policy.json').read_bytes()
        policy=pilot.init_project(self.root, {'mode':'off', 'share_artifacts':True})
        self.assertEqual(before,(self.root/'policy.json').read_bytes())
        self.assertEqual(policy,self.policy)
        self.assertEqual(len(pilot.load_records(self.root,'decisions')),1)

    def test_new_success_stops_automatic_comparison_without_erasing_failure(self):
        cfg=self.decision['selected_configuration_id']
        candidate=next(c['id'] for c in self.decision['candidates'] if c['configuration_id']==cfg)
        raw=pilot.outcome_fixture(self.decision,cfg,False)
        raw.update(reviewer_id='independent',reviewer_kind='frontier',worker_id='native-old')
        pilot.observe(self.root,raw)
        second=copy.deepcopy(self.packet);second.update(task_id='second',group_id='second',user_choice_id=candidate)
        d=pilot.route_packet(second,self.policy,pilot.load_records(self.root,'outcomes'),live=True,call=pilot.synthetic_response,key='fixture')
        pilot.write_new(self.root/'decisions'/(d['id']+'.json'),d)
        raw=pilot.outcome_fixture(d,cfg,True)
        raw.update(reviewer_id='independent',reviewer_kind='frontier',worker_id='native-new')
        pilot.observe(self.root,raw)
        third=copy.deepcopy(self.packet);third.update(task_id='third',group_id='third')
        d=pilot.route_packet(third,self.policy,pilot.load_records(self.root,'outcomes'),live=True,call=pilot.synthetic_response,key='fixture')
        pilot.write_new(self.root/'decisions'/(d['id']+'.json'),d)
        r=workflow.start(self.root,d,third,self.policy,'auto')
        self.assertEqual(len(r['attempts']),1)
        evidence=next(c['evidence'] for c in d['candidate_assessments'] if c['configuration_id']==cfg)
        self.assertEqual(evidence['failed_groups'],1)
        self.assertEqual(evidence['passed_groups'],1)
        self.assertFalse(evidence['recent_failure'])

    def test_status_does_not_reserve_or_duplicate_dispatch(self):
        before=workflow._path(self.root,self.request['id']).read_bytes()
        self.assertEqual(easy.status(self.root,self.request['id'])['attempts'][0]['state'],'planned')
        self.assertEqual(before,workflow._path(self.root,self.request['id']).read_bytes())
        first=self.event('launching'); second=self.event('launching')
        self.assertEqual(first,second)
        self.assertEqual(easy.status(self.root,self.request['id'])['actions'],[])
        self.event('launch-not-started',reason_code='host-confirmed-absent')
        new=self.event('launching')
        self.assertEqual(len(new['events']),3)
        self.assertEqual(new['attempts'][0]['state'],'launching')

    def test_observed_configuration_is_required_not_copied(self):
        self.event('launching')
        with self.assertRaisesRegex(core.PilotError,'observed-configuration-mismatch'):
            self.event('dispatched',run_id='native-run',checkout_hash='a'*64,base_revision='base')

    def test_review_resume_after_publication_does_not_repeat_evaluation(self):
        self.completed(); raw=self.raw()
        pilot.observe(self.root,raw)
        with patch.object(pilot,'observe',side_effect=AssertionError('must not repeat')):
            result=easy.review(self.root,self.request['id'],'attempt-1',raw)
            self.assertEqual(result['state'],'accepted')
            self.assertEqual(result,easy.review(self.root,self.request['id'],'attempt-1',raw))
        self.assertEqual(len(pilot.load_records(self.root,'outcomes')),1)
        changed=copy.deepcopy(raw); changed['scores']['correctness']=80
        with self.assertRaisesRegex(core.PilotError,'outcome-changed'):
            easy.review(self.root,self.request['id'],'attempt-1',changed)

    def test_concurrent_identical_reviews_advance_once(self):
        self.completed(); raw=self.raw()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:easy.review(self.root,self.request['id'],'attempt-1',raw),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(len(pilot.load_records(self.root,'outcomes')),1)

    def test_failed_review_can_request_one_targeted_repair(self):
        self.completed(); raw=self.raw(); raw['gates'][0]['passed']=False
        result=easy.review(self.root,self.request['id'],'attempt-1',raw,repairable=True,findings_hash='c'*64)
        self.assertEqual(result['attempts'][0]['state'],'rejected')
        self.assertEqual(result['attempts'][1]['kind'],'repair')
        self.assertIsNone(result['accepted_attempt_id'])

    def test_artifact_file_correction_preserves_history_and_binds_review(self):
        self.completed()
        artifact=self.directory/'actual.patch'; artifact.write_bytes(b'actual delivered patch\n')
        command=[sys.executable,'-I','-S',str(Path(pilot.__file__)), '--root',str(self.root),
                 'workflow-event','--request',self.request['id'],'--attempt','attempt-1',
                 '--type','artifact-corrected','--artifact-file',str(artifact),'--reason-code','recording-error']
        first=subprocess.run(command,capture_output=True,text=True,check=True)
        second=subprocess.run(command,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(first.stdout),json.loads(second.stdout))
        attempt=json.loads(first.stdout)['attempts'][0]
        self.assertEqual(attempt['artifact_hash'],easy.file_hash(artifact))
        self.assertEqual(attempt['artifact_correction']['previous_artifact_hash'],'b'*64)
        self.assertEqual(json.loads(first.stdout)['events'][-1]['previous_artifact_hash'],'b'*64)
        with self.assertRaisesRegex(core.PilotError,'artifact-correction-exhausted'):
            self.event('artifact-corrected',artifact_hash='c'*64,reason_code='recording-error')
        raw=self.raw()
        self.assertEqual(raw['artifact_hash'],easy.file_hash(artifact))
        self.assertEqual(easy.review(self.root,self.request['id'],'attempt-1',raw)['state'],'accepted')
        files=pilot.report(self.root,self.directory/'correction-report')
        self.assertIn('Artifact-record corrections before review: 1',Path(files['html']).read_text())
        report=pilot.read_json(files['json'])
        self.assertIsNone(report['overview'][0]['reported_worker_time_ms'])

    def test_artifact_correction_cannot_change_published_or_completed_review(self):
        self.completed(); raw=self.raw()
        pilot.observe(self.root,raw)  # Publication succeeded before workflow advancement.
        with self.assertRaisesRegex(core.PilotError,'artifact-review-already-published'):
            self.event('artifact-corrected',artifact_hash='c'*64,reason_code='recording-error')
        easy.review(self.root,self.request['id'],'attempt-1',raw)
        with self.assertRaisesRegex(core.PilotError,'artifact-already-reviewed'):
            self.event('artifact-corrected',artifact_hash='c'*64,reason_code='recording-error')

    def test_artifact_correction_cannot_rebind_interrupted_paid_review(self):
        self.completed(); raw=self.raw()
        assessed=core.assess_outcome(raw,self.decision,self.policy)
        (self.root/'outcomes'/(assessed['id']+'.pending')).write_text('')
        with self.assertRaisesRegex(core.PilotError,'artifact-review-already-started'):
            self.event('artifact-corrected',artifact_hash='c'*64,reason_code='recording-error')

    def test_report_creates_custom_parent_and_legacy_config_cannot_damage_policy(self):
        files=pilot.report(self.root,self.directory/'new'/'reports'/'trial')
        self.assertTrue(Path(files['html']).exists())
        before=(self.root/'policy.json').read_bytes()
        run=subprocess.run([sys.executable,'-I','-S',str(Path(pilot.__file__).with_name('jev.py')),
                            '--root',str(self.root),'configure'],capture_output=True,text=True)
        self.assertEqual(run.returncode,1)
        self.assertEqual(json.loads(run.stderr)['error'],'pilot-policy-use-pilot-cli')
        self.assertEqual(before,(self.root/'policy.json').read_bytes())

    def test_configure_preserves_locators_and_invalidates_decisions(self):
        command=[sys.executable,'-I','-S',str(Path(pilot.__file__)), '--root',str(self.root),
                 'configure','--selection-preference','strongest_fit','--bakeoff','on']
        result=subprocess.run(command,capture_output=True,text=True,check=True)
        self.assertTrue(json.loads(result.stdout)['reevaluate_existing_decisions'])
        current=pilot.load_policy(self.root)
        self.assertEqual(current['credential_service'],self.policy['credential_service'])
        self.assertEqual(current['selection_preference'],'strongest_fit')
        self.assertEqual(current['bakeoff'],'on')
        with self.assertRaisesRegex(core.PilotError,'decision-policy-changed'):
            workflow.recheck(self.root,self.request['id'],'attempt-1',self.packet)

    def test_cli_flags_persist_without_event_json(self):
        packet=self.directory/'packet.json'; pilot.write_new(packet,self.packet)
        command=[sys.executable,'-I','-S',str(Path(pilot.__file__)), '--root',str(self.root),
                 'workflow-event','--request',self.request['id'],'--attempt','attempt-1','--type','launching','--packet',str(packet)]
        first=subprocess.run(command,capture_output=True,text=True,check=True)
        second=subprocess.run(command,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(first.stdout),json.loads(second.stdout))

    def test_prepare_binds_preview_and_preserves_unknown_cost(self):
        task={k:copy.deepcopy(self.packet[k]) for k in ('task_id','group_id','task')}
        host={'observed_at':core.now(),'models':{'gpt-5.6-luna':['low','medium']},'tools':['read-files'],'delegation_allowed':True}
        catalog={'models':[{'slug':'gpt-5.6-luna','supported_reasoning_levels':[{'effort':'medium'}],
                          'context_window':32000,'max_output_tokens':8000,'input_modalities':['text']}]}
        (self.directory/'prepared').mkdir()
        result=pilot_codex.prepare_project(self.root,task,catalog,host,self.directory/'prepared')
        packet=pilot.read_json(result['files']['packet.json']); preview=pilot.read_json(result['files']['sharing-preview.json'])
        self.assertEqual(core.digest(packet),preview['input_hash'])
        self.assertEqual(packet['candidates'][0]['effort'],'medium')
        self.assertEqual(packet['candidates'][0]['efficiency_hint']['rank'],1)
        self.assertIsNone(packet['candidates'][0]['estimate_usd'])
        self.assertEqual(result['eligible_candidates'],1)
        self.assertFalse(result['dispatch_authorized'])
        self.assertEqual(len(pilot.load_records(self.root,'decisions')),1)
        before=(self.directory/'prepared'/'packet.json').read_bytes()
        with self.assertRaisesRegex(core.PilotError,'preparation-directory-not-empty'):
            pilot_codex.prepare_project(self.root,task,catalog,host,self.directory/'prepared')
        self.assertEqual(before,(self.directory/'prepared'/'packet.json').read_bytes())
        target=self.directory/'empty'; target.mkdir()
        alias=self.directory/'alias'
        try:
            alias.symlink_to(target, target_is_directory=True)
        except OSError:
            return  # Windows environments may lack symlink privilege.
        with self.assertRaisesRegex(core.PilotError,'preparation-directory-symlink'):
            pilot_codex.prepare_project(self.root,task,catalog,host,alias)
        self.assertEqual(list(target.iterdir()),[])

    def test_native_pool_preparation_fits_wire_budget_and_accepts_global_root(self):
        task={k:copy.deepcopy(self.packet[k]) for k in ('task_id','group_id','task')}
        names=['gpt-6-astra','gpt-5.6-sol','gpt-5.6-terra','gpt-5.6-luna','gpt-5.5']
        host={'observed_at':core.now(),'models':{name:['medium'] for name in names},
              'tools':['read-files','edit-files','run-tests'],'delegation_allowed':True}
        catalog={'models':[{'slug':name,'supported_reasoning_levels':[{'effort':'medium'}],
                  'context_window':32000,'max_output_tokens':8000,'input_modalities':['text']} for name in names]}
        for name,value in [('task',task),('host',host),('catalog',catalog)]:
            pilot.write_new(self.directory/(name+'.json'),value)
        result=subprocess.run([sys.executable,'-I','-S',str(Path(pilot_codex.__file__)),
            '--root',str(self.root),'prepare','--task',str(self.directory/'task.json'),
            '--catalog',str(self.directory/'catalog.json'),'--host-observation',str(self.directory/'host.json'),
            '--output-dir',str(self.directory/'five')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['eligible_candidates'],5)


if __name__=='__main__': unittest.main()
