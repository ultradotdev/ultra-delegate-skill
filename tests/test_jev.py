"""Behavioral qualification for the optional adapter, without paid API calls."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.error

SCRIPTS = Path(__file__).resolve().parents[1] / '.agents/skills/ultra-delegation/scripts'
sys.path.insert(0, str(SCRIPTS))
import jev
import jev_transport as t
from jev_contract import validate_policy, event_record, summarize_events
import jev_qualification as q


def response(payload, fit=None, ambiguous=0, enough=1):
    answers = {}
    for name, question in payload['questions'].items():
        if question['type'] == 'noul':
            n = ambiguous if name == 'ambiguous' else 0 if name == 'retain' else enough if name.startswith('enough_') else (fit or {}).get(name, 1)
            answers[name] = {'type': 'noul', 'noul': n}
        else:
            levels = question['criteria']
            answers[name] = {'type': 'score', 'score': len(levels)-1, 'confidence': 1,
                             'legend': {str(i): s for i,s in enumerate(levels)},
                             'probabilities': {str(i): float(i == len(levels)-1) for i in range(len(levels))}}
    return {'model': payload['model'], 'answers': answers, 'usage': {'input_tokens': 100, 'output_tokens': 10}}


def fake_call(**kwargs):
    def call(payload, key):
        return response(payload, **kwargs), {'attempts': 1, 'latency_ms': 5}
    return call


def stalled_credential_worker(connection, ref, service):
    time.sleep(30)


def successful_credential_worker(connection, ref, service):
    connection.send((True, 'synthetic-process-credential'))
    connection.close()


def failed_credential_worker(connection, ref, service):
    connection.send((False, 'private-error-sentinel'))
    connection.close()


class JevBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.packet = q.route_fixture(); self.policy = q.policy()
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'.ultra-delegation'

    def route(self, **kwargs):
        return jev.route(self.packet, self.policy, key='fixture', call=fake_call(), **kwargs)

    def test_defaults_off_without_dependencies_or_network(self):
        p = validate_policy({})
        self.assertEqual(('off', 'off', False, False), (p['routing'], p['judging'], p['share_summaries'], p['share_artifacts']))
        self.policy['jev'] = p
        with patch.object(t, 'credential', side_effect=AssertionError('credential accessed')):
            self.assertEqual(self.route()['reason_codes'], ['routing-disabled'])

    def test_active_picks_cheapest_proven_suitable_and_does_not_mutate(self):
        before = copy.deepcopy(self.packet)
        result = self.route()
        self.assertEqual(result['action'], 'route')
        self.assertEqual(result['selected_profile_id'], result['baseline_profile_id'])
        self.assertEqual(before, self.packet)
        result = jev.route(self.packet, self.policy, key='fixture', call=fake_call(fit={'fit_0': 0.01}))
        self.assertEqual(result['selected_profile_id'], jev.ud.profile_id(self.packet['candidates'][1]['profile']))
        self.assertEqual(result['cost_kind'], 'estimated')

    def test_shadow_preserves_baseline_on_disagreement(self):
        self.policy['jev']['routing'] = 'shadow'
        result = jev.route(self.packet, self.policy, key='fixture', call=fake_call(fit={'fit_0': 0}))
        self.assertEqual(result['selected_profile_id'], result['baseline_profile_id'])
        self.assertNotEqual(result['recommended_profile_id'], result['selected_profile_id'])
        self.assertTrue(result['disagreement'])

    def test_uncertainty_abstains(self):
        result = jev.route(self.packet, self.policy, key='fixture', call=fake_call(ambiguous=0.5))
        self.assertEqual(result['action'], 'coordinator')
        self.assertEqual(result['status'], 'abstained')

    def test_provisional_never_direct_routes_and_experiment_is_one_variable(self):
        self.packet['records'] = []
        self.assertEqual(self.route()['action'], 'coordinator')
        self.packet['experiment'] = {'variable': 'model', 'isolation': 'patch_proposal'}
        result = self.route()
        self.assertEqual(result['action'], 'experiment')
        self.assertIsNone(result['selected_profile_id'])
        self.assertEqual(len(result['nominated_profile_ids']), 2)
        self.packet['candidates'][1]['profile']['prompt_profile'] = 'different'
        self.assertEqual(self.route()['action'], 'coordinator')

    def test_experiment_effort_limit(self):
        self.packet['records'] = []
        self.packet['experiment'] = {'variable': 'model', 'isolation': 'patch_proposal'}
        for c in self.packet['candidates']:
            c['profile']['thinking'] = {'native':'high', 'normalized':'high'}
        self.packet['context']['thinking_settings'] = {p['model_revision']: ['high'] for p in (c['profile'] for c in self.packet['candidates'])}
        self.assertEqual(self.route()['action'], 'coordinator')

    def test_host_provider_exclusion_and_unknown_location(self):
        for modification in ({'provider':'other'}, {'host':'other'}, {'execution_location':'unknown'}):
            with self.subTest(modification=modification):
                packet = copy.deepcopy(self.packet)
                for c in packet['candidates']: c['profile'].update(modification)
                result = jev.route(packet, self.policy, call=fake_call(), key='fixture')
                self.assertEqual(result['reason_codes'], ['no-eligible-candidates'])
        self.policy['exclusions'] = ['synthetic']
        self.assertEqual(self.route()['reason_codes'], ['no-eligible-candidates'])

    def test_stale_or_quarantined_evidence_cannot_route(self):
        for r in self.packet['records']: r['created_at'] = '2000-01-01T00:00:00+00:00'
        self.assertEqual(self.route()['action'], 'coordinator')
        for r in self.packet['records']: r['status'] = 'quarantined'
        self.assertEqual(self.route()['reason_codes'], ['no-eligible-candidates'])

    def test_user_selection_and_pins_bypass_model_but_not_exclusion(self):
        pid = jev.ud.profile_id(self.packet['candidates'][1]['profile'])
        self.policy['pins'] = [pid]
        with patch.object(t, 'credential', side_effect=AssertionError()):
            self.assertEqual(self.route()['selected_profile_id'], pid)
        self.policy['exclusions'] = [pid]
        self.assertNotEqual(self.route()['selected_profile_id'], pid)
        self.policy['pins'] = []; self.policy['exclusions'] = []
        self.packet['candidates'][1]['user_selected'] = True
        self.assertEqual(self.route()['selected_profile_id'], pid)

    def test_context_and_retention_stop_before_api(self):
        self.packet['snapshot'] = {'observed_at': jev.ud.now(), 'telemetry': {'availability':'measured'}, 'context': {'used_tokens':99, 'window_tokens':100}}
        self.assertEqual(self.route()['reason_codes'], ['context-stop'])
        self.packet['snapshot'] = {'telemetry': {'availability':'unavailable'}}
        self.packet['task']['risk'] = 'high'
        self.assertEqual(self.route()['reason_codes'], ['coordinator-owned'])

    def test_saved_guard_stop_cannot_be_cleared_by_adapter(self):
        path = jev.ud.guard_run_dir(self.root, self.packet['run_id'])/'guard-state.json'
        jev.ud.write_json(path, {'delegation_allowed':False})
        self.assertEqual(self.route(root=self.root)['reason_codes'], ['context-stop'])

    def test_missing_key_and_failure_return_original_ranking(self):
        with patch.object(t, 'credential', side_effect=t.ServiceError('missing-credential')):
            result = jev.route(self.packet, self.policy)
        self.assertEqual(result['status'], 'unavailable'); self.assertEqual(len(result['ranking']), 2)
        self.assertEqual(result['action'], 'coordinator')
        def failure(*args): raise t.ServiceError('deadline-exceeded', 1)
        result = jev.route(self.packet, self.policy, key='fixture', call=failure)
        self.assertEqual(result['reason_codes'], ['deadline-exceeded'])

    def test_independent_sharing_and_explicit_preview(self):
        self.policy['jev']['share_summaries'] = False
        self.assertEqual(self.route()['reason_codes'], ['summary-sharing-disabled'])
        self.policy['jev']['share_summaries'] = True
        with patch.object(t, 'credential', side_effect=AssertionError()):
            result = self.route(dry_run=True)
        self.assertTrue(result['dry_run']); self.assertIn('summary', result['payload']['state'])
        self.policy['jev']['share_artifacts'] = False
        self.assertEqual(jev.judge(q.judge_fixture(), self.policy)['reason_codes'], ['artifact-sharing-disabled'])

    def test_recheck_freshness_changes_and_eligibility(self):
        decision = self.route()
        jev.write_event(self.root, decision)
        self.assertTrue(jev.recheck(self.packet, decision, self.policy, self.root)['dispatch_allowed'])
        changed = copy.deepcopy(self.packet); changed['summary'] += ' new requirement'
        with self.assertRaises(ValueError): jev.recheck(changed, decision, self.policy, self.root)
        decision['created_at'] = '2000-01-01T00:00:00+00:00'
        jev.write_event(self.root, decision)
        with self.assertRaises(ValueError): jev.recheck(self.packet, decision, self.policy, self.root)

    def test_ledger_contains_no_summary_or_artifacts_and_reports_overhead(self):
        result = self.route(); jev.write_event(self.root, result)
        saved = json.loads((self.root/'jev/decisions.jsonl').read_text())
        self.assertNotIn('ranking', saved)
        self.assertNotIn(self.packet['summary'], json.dumps(saved))
        self.assertIn('.ultra-delegation/jev/', (self.root.parent/'.gitignore').read_text())
        stats = summarize_events([saved])
        self.assertEqual(stats['routing']['api_attempts'], 1)
        self.assertEqual(stats['savings_attribution'], 'unavailable')

    def test_judge_shadow_scores_never_quality_evidence(self):
        packet = q.judge_fixture()
        before = copy.deepcopy(packet)
        result = jev.judge(packet, self.policy, key='fixture', call=fake_call())
        self.assertEqual(packet, before)
        self.assertEqual(result['action'], 'coordinator')
        self.assertNotIn('accepted', result); self.assertNotIn('quality_score', result)
        self.assertTrue(result['reference_comparison']['candidate_1']['false_acceptance'])
        self.assertEqual(len(result['shadow_scores']), 2)
        jev.write_event(self.root, result)
        self.assertFalse((self.root/'evidence.jsonl').exists())

    def test_judge_mandatory_failure_and_insufficient_evidence(self):
        packet = q.judge_fixture(); packet['candidates'][0]['gates'][0]['passed'] = False
        result = jev.judge(packet, self.policy, key='fixture', call=fake_call())
        self.assertFalse(result['shadow_scores']['candidate_0']['suggested_acceptable'])
        result = jev.judge(packet, self.policy, key='fixture', call=fake_call(enough=0.4))
        self.assertIsNone(result['shadow_scores']['candidate_0']['score'])
        self.assertTrue(result['reference_comparison']['candidate_0']['abstained'])

    def test_judge_blinds_identity_cost_and_reference(self):
        packet = q.judge_fixture()
        preview = jev.judge(packet, self.policy, dry_run=True)
        self.assertNotIn('reference_', json.dumps(preview['payload']))
        packet['candidates'][0]['model'] = 'secret-worker-identity'
        with self.assertRaises(ValueError): jev.judge(packet, self.policy, dry_run=True)

    def test_judge_model_and_rubric_pinned(self):
        packet = q.judge_fixture(); packet['model'] = 'jev-latest'
        with self.assertRaises(ValueError): jev.judge(packet, self.policy)
        with self.assertRaises(ValueError): validate_policy({'model':'jev-latest'})

    def test_recheck_requires_saved_unmodified_event(self):
        result = self.route()
        with self.assertRaises(ValueError): jev.recheck(self.packet, result, self.policy, self.root)
        jev.write_event(self.root, result)
        result['selected_profile_id'] = jev.ud.profile_id(self.packet['candidates'][1]['profile'])
        with self.assertRaises(ValueError): jev.recheck(self.packet, result, self.policy, self.root)

    def test_imported_prior_keeps_pending_verification(self):
        self.packet['records'] = []
        c = self.packet['candidates'][0]
        c['imported_prior'] = {'profile':c['profile'], 'profile_id':jev.ud.profile_id(c['profile']),
                              'task_signature':self.packet['task'], 'source_passed_gates':True,
                              'promotion':'normal', 'confidence':'high', 'fresh_at':jev.ud.now(),
                              'moving_alias':False,
                              'aggregate':{'evidence_count':3,'pass_count':3,'conservative_quality':90,'mean_cost_usd':0.01}}
        result = self.route()
        self.assertEqual(result['action'], 'route')
        self.assertTrue(result['pending_verification'])
        jev.write_event(self.root, result)
        self.assertTrue(jev.recheck(self.packet, result, self.policy, self.root)['pending_verification'])
        c['imported_prior']['confidence'] = 'low'
        self.assertEqual(self.route()['action'], 'coordinator')

    def test_judge_run_version_cannot_change_after_recording(self):
        packet = q.judge_fixture()
        result = jev.judge(packet, self.policy, key='fixture', call=fake_call(), root=self.root)
        jev.write_event(self.root, result)
        self.policy['jev']['model'] = packet['model'] = 'jev-99.0.0'
        with self.assertRaises(ValueError): jev.judge(packet, self.policy, key='fixture', call=fake_call(), root=self.root)

    def test_report_includes_overhead_without_exporting_decisions(self):
        import argparse
        result = self.route(); jev.write_event(self.root, result)
        report = jev.ud.cmd_report(argparse.Namespace(root=str(self.root), records=None, report_kind='project', run_id=None, write=False))
        self.assertEqual(report['data']['jev']['routing']['api_attempts'], 1)
        self.assertEqual(report['data']['records'], 0)
        self.assertIn('Jev decision overhead', report['markdown'])
        output = self.root/'portable.json'
        jev.ud.cmd_export(argparse.Namespace(root=str(self.root), records=None, output=str(output)))
        self.assertEqual(json.loads(output.read_text())['learnings'], [])

    def test_cli_rejects_credential_arguments_without_echo(self):
        with patch('sys.stderr', new_callable=io.StringIO) as stderr, self.assertRaises(SystemExit):
            jev.main(['auth', 'set', '--api-key', 'synthetic-private-value'])
        self.assertNotIn('synthetic-private-value', stderr.getvalue())

    def test_cli_configuration_preserves_unrelated_policy_and_errors_redact(self):
        jev.ud.write_json(self.root/'policy.json', {'pins':['preserve'], 'jev':{}})
        with patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(jev.main(['--root', str(self.root), 'configure', '--routing', 'active', '--share-summaries', 'yes']), 0)
        stored = json.loads((self.root/'policy.json').read_text())
        self.assertEqual(stored['pins'], ['preserve'])
        self.assertEqual(stored['jev']['judging'], 'off')
        with patch('sys.stderr', new_callable=io.StringIO) as stderr:
            self.assertEqual(jev.main(['--root', str(self.root), 'route', '--input', '/unavailable/secret-marker']), 1)
        self.assertNotIn('secret-marker', stderr.getvalue())

    def test_configure_changes_only_locator_not_credential_store(self):
        with patch.object(t, 'secure_backend', side_effect=AssertionError('must not access store')), patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(jev.main(['--root', str(self.root), 'configure', '--credential-service', 'Existing TypeSafe Entry', '--credential-ref', 'existing@example.test']), 0)
        p = jev.ud.load_policy(self.root)['jev']
        self.assertEqual(p['credential_service'], 'Existing TypeSafe Entry')
        self.assertEqual(p['credential_ref'], 'existing@example.test')
        self.assertEqual(p['routing'], 'off')

    def test_live_runner_measures_false_acceptance_and_order(self):
        with patch.object(t, 'credential', return_value=('fixture','environment')), patch.object(t, 'request', side_effect=fake_call()):
            result = q.qualification(True)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['false_acceptances'],2)
        self.assertEqual(result['order_disagreements'],0)
        self.assertEqual(len(result['events']),4)

    def test_live_qualification_is_opt_in_and_pending_without_credentials(self):
        with patch.object(t, 'credential', side_effect=AssertionError()):
            self.assertEqual(q.qualification()['reason'], 'live-not-requested')
        with patch.object(t, 'credential', side_effect=t.ServiceError('missing-credential')):
            self.assertEqual(q.qualification(True)['status'], 'pending')


class TransportTests(unittest.TestCase):
    def payload(self): return {'model':'jev-1.13.0', 'state':'synthetic', 'questions':{'yes':{'type':'noul','instructions':'Is this synthetic?'}}}

    def test_live_score_rounding_retains_probabilities_and_rejects_inconsistency(self):
        p = {'model':'jev-1.13.0', 'state':'synthetic', 'questions':{'impact':{
            'type':'score', 'instructions':'Rate impact', 'criteria':['none','small','large','severe']}}}
        r = response(p)
        a = r['answers']['impact']
        a.update(probabilities={'0':.97,'1':.03,'2':0.,'3':0.}, score=.04)
        clean, _ = t.validate_response(p,r)
        self.assertEqual(clean['impact'], a['probabilities'])
        for score in (.06, -.01, 3.01, True, float('nan'), .040001):
            with self.subTest(score=score), self.assertRaises(t.ServiceError):
                a['score'] = score
                t.validate_response(p,r)
        a['score'] = .04
        a['probabilities']['0'] = .96
        with self.assertRaises(t.ServiceError): t.validate_response(p,r)
        a['probabilities']['0'] = .97
        a['legend']['0'] = 'changed'
        with self.assertRaises(t.ServiceError): t.validate_response(p,r)
        # Legacy shadow judging uses five levels and retains the scalar score.
        p['questions']['impact']['criteria'].append('critical')
        a['legend'] = {str(i): level for i, level in enumerate(p['questions']['impact']['criteria'])}
        a['probabilities']['4'] = 0.
        t.validate_response(p,r)
        a['probabilities'].update({'0':.969, '1':.031})
        with self.assertRaises(t.ServiceError): t.validate_response(p,r)

    def test_invalid_response_values_and_coverage(self):
        p = self.payload()
        for change in ({'model':'other'}, {'answers':{}}, {'usage':{'input_tokens':True,'output_tokens':1}}, {'answers':{'yes':{'type':'noul','noul':float('nan')}}}):
            with self.subTest(change=change), self.assertRaises(t.ServiceError):
                t.validate_response(p, {**response(p), **change})
        p = jev.judge_payload(q.judge_fixture(), q.policy())
        r = response(p); r['answers']['clarity_0']['probabilities']['invented'] = 0
        with self.assertRaises(t.ServiceError): t.validate_response(p, r)
        r = response(p); r['answers']['clarity_0']['score'] = 0
        with self.assertRaises(t.ServiceError): t.validate_response(p, r)

    def test_choice_cannot_return_an_unknown_candidate(self):
        p = {'model':'jev-1.13.0','state':'test','questions':{'route':{'type':'choice','instructions':'Choose','criteria':{'a':None,'b':None}}}}
        r = {'model':p['model'],'usage':{'input_tokens':1,'output_tokens':1},'answers':{'route':{'type':'choice','choice':'invented','confidence':1,'probabilities':{'a':0.5,'b':0.5}}}}
        with self.assertRaises(t.ServiceError): t.validate_response(p,r)

    def test_single_attempt_budget_never_retries_transient_failure(self):
        class Opener:
            calls = 0
            def open(self, *args, **kwargs):
                self.calls += 1
                raise urllib.error.HTTPError(t.ENDPOINT, 503, 'private-provider-body', {}, io.BytesIO(b'private'))
        opener = Opener()
        with self.assertRaises(t.ServiceError) as error:
            t._request_loop(b'{}', 'fixture', time.monotonic()+20, opener,
                            sleep=lambda _: self.fail('single attempt must not sleep'), max_attempts=1)
        self.assertEqual(opener.calls, 1)
        self.assertEqual(error.exception.attempts, 1)
        self.assertNotIn('private', str(error.exception))
        for invalid in (0, 3, True, '1'):
            with self.subTest(invalid=invalid), patch.object(t.multiprocessing, 'get_context', side_effect=AssertionError), self.assertRaisesRegex(t.ServiceError, 'invalid-attempt-limit'):
                t.request(self.payload(), 'fixture', max_attempts=invalid)

    def test_request_response_bounds_and_redirect(self):
        with self.assertRaises(t.ServiceError): t.encoded_payload({'state':'x'*t.REQUEST_LIMIT})
        with self.assertRaises(t.ServiceError): t.NoRedirect().redirect_request(None,None,302,None,None,'https://elsewhere.invalid')
        class Opener:
            def open(self, *a, **k): return io.BytesIO(b'x'*(t.RESPONSE_LIMIT+1))
        with self.assertRaises(t.ServiceError) as error:
            t._request_loop(b'{}','fixture',time.monotonic()+20,Opener())
        self.assertEqual(error.exception.code, 'response-too-large')

    def test_retry_once_and_auth_never_retried(self):
        class Opener:
            def __init__(self, codes): self.codes = iter(codes); self.calls = 0
            def open(self, *a, **k):
                self.calls += 1; code = next(self.codes)
                if code: raise urllib.error.HTTPError(t.ENDPOINT,code,'SECRET PROVIDER BODY',{},io.BytesIO(b'SECRET'))
                return io.BytesIO(b'{}')
        for code in (401,403,422):
            o = Opener([code])
            with self.assertRaises(t.ServiceError) as e: t._request_loop(b'{}','fixture',time.monotonic()+20,o,sleep=lambda _:None)
            self.assertEqual(o.calls,1); self.assertNotIn('SECRET',str(e.exception))
        o = Opener([429,0]); _, attempts = t._request_loop(b'{}','fixture',time.monotonic()+20,o,sleep=lambda _:None)
        self.assertEqual(attempts,2)
        o = Opener([529,529])
        with self.assertRaises(t.ServiceError): t._request_loop(b'{}','fixture',time.monotonic()+20,o,sleep=lambda _:None)
        self.assertEqual(o.calls,2)

    def test_expired_deadline_never_opens(self):
        with self.assertRaises(t.ServiceError) as e: t._request_loop(b'{}','fixture',time.monotonic()-1)
        self.assertEqual(e.exception.code,'deadline-exceeded')

    def test_env_precedence_and_auth_status_no_probe(self):
        with patch.object(t, 'secure_backend', side_effect=AssertionError()):
            self.assertEqual(t.credential('default', {'TYPESAFE_API_KEY':'fixture'}), ('fixture','environment'))
        with patch.dict(os.environ, {'TYPESAFE_API_KEY':'private-fixture'}), patch.object(t, 'request', side_effect=AssertionError()):
            status = t.auth('status','default','jev-1.13.0')
            self.assertTrue(status['configured']); self.assertFalse(status['verified'])
            self.assertNotIn('private-fixture', json.dumps(status))

    def test_credential_mutations_are_rejected_before_lookup(self):
        for action in ('set', 'delete', 'update', 'unknown'):
            with self.subTest(action=action), patch.object(t, 'credential', side_effect=AssertionError('must not access store')):
                with self.assertRaises(t.ServiceError) as e: t.auth(action, 'default', 'jev-1.13.0')
                self.assertEqual(e.exception.code, 'unsupported-auth-action')
            with patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit):
                jev.main(['auth', action])

    def test_existing_service_and_account_are_read_without_mutation(self):
        from unittest.mock import Mock
        backend = Mock()
        backend.get_password.return_value = 'private-fixture'
        backend.set_password.side_effect = AssertionError('must never write')
        backend.delete_password.side_effect = AssertionError('must never delete')
        with patch.object(t, 'secure_backend', return_value=backend), patch.object(t, '_read_stored_credential', side_effect=t._stored_credential), patch.dict(os.environ, {}, clear=True):
            status = t.auth('status', 'existing@example.test', 'jev-1.13.0', service='Existing TypeSafe Entry')
        backend.get_password.assert_called_once_with('Existing TypeSafe Entry', 'existing@example.test')
        backend.set_password.assert_not_called(); backend.delete_password.assert_not_called()
        self.assertTrue(status['configured'])
        self.assertNotIn('private-fixture', json.dumps(status))

    def test_missing_existing_entry_has_no_write_fallback(self):
        from unittest.mock import Mock
        backend = Mock(); backend.get_password.return_value = None
        with patch.object(t, 'secure_backend', return_value=backend), patch.object(t, '_read_stored_credential', side_effect=t._stored_credential), patch.dict(os.environ, {}, clear=True):
            status = t.auth('status', 'existing', 'jev-1.13.0', service='Existing Entry')
        self.assertFalse(status['configured']); self.assertEqual(status['reason'], 'missing-credential')
        backend.set_password.assert_not_called(); backend.delete_password.assert_not_called()

    def test_all_supported_backend_classes_resolve_without_leaking(self):
        for module, name in t.SECURE_BACKENDS:
            backend = type(name, (), {'__module__':module, 'get_password':lambda *args:'synthetic-private-key'})()
            class FakeKeyring:
                @staticmethod
                def get_keyring(): return backend
            with self.subTest(module=module,name=name), patch.dict(sys.modules, {'keyring':FakeKeyring}):
                self.assertEqual(t._stored_credential('default', t.SERVICE), 'synthetic-private-key')

    def test_owned_credential_process_times_out_and_is_reaped(self):
        before = {p.pid for p in t.multiprocessing.active_children()}
        started = time.monotonic()
        with patch.object(t, '_credential_worker', stalled_credential_worker), patch.object(t, 'CREDENTIAL_DEADLINE', 1):
            with self.assertRaises(t.ServiceError) as error:
                t._read_keyring_credential('fixture-account', 'fixture-service')
        self.assertEqual(error.exception.code, 'credential-store-timeout')
        self.assertEqual(error.exception.attempts, 0)
        self.assertLess(time.monotonic()-started, 2)
        self.assertEqual({p.pid for p in t.multiprocessing.active_children()}, before)

    def test_macos_native_read_uses_only_locator_in_argv(self):
        from unittest.mock import Mock
        result = Mock(returncode=0, stdout=b'private-key-sentinel\n', stderr=b'private-error-sentinel')
        with patch.object(t.sys, 'platform', 'darwin'), patch.object(t.subprocess, 'run', return_value=result) as run, patch.object(t, '_read_keyring_credential', side_effect=AssertionError):
            self.assertEqual(t.credential('fixture-account', {}, service='fixture-service'), ('private-key-sentinel','os-store'))
        self.assertEqual(run.call_args.args[0], ['/usr/bin/security','find-generic-password','-s','fixture-service','-a','fixture-account','-w'])
        self.assertEqual(run.call_args.kwargs['timeout'], 5)
        self.assertTrue(run.call_args.kwargs['capture_output'])
        self.assertFalse(run.call_args.kwargs['check'])
        self.assertNotIn('private-key-sentinel', str(run.call_args))
        for framed, expected in ((b'key\n\n','key\n'), (b'key\r\n','key\r'), (b'key','key')):
            result.stdout = framed
            with self.subTest(framed=framed), patch.object(t.subprocess,'run',return_value=result):
                self.assertEqual(t._macos_credential('fixture','fixture'), expected)

    def test_macos_native_errors_are_redacted_and_never_fall_back_to_writes(self):
        from unittest.mock import Mock
        cases = [(Mock(returncode=44, stdout=b'', stderr=b'private-error'), 'missing-credential'),
                 (Mock(returncode=1, stdout=b'private-key', stderr=b'private-error'), 'credential-store-unavailable'),
                 (Mock(returncode=0, stdout=b'\xff', stderr=b''), 'credential-store-unavailable')]
        for result, code in cases:
            with self.subTest(code=code), patch.object(t.subprocess, 'run', return_value=result) as run:
                with self.assertRaises(t.ServiceError) as error: t._macos_credential('fixture','fixture')
                self.assertEqual(str(error.exception), code)
                self.assertEqual(run.call_count, 1)
        with patch.object(t.subprocess, 'run', side_effect=subprocess.TimeoutExpired('private-command', 5, output=b'private-key')):
            with self.assertRaisesRegex(t.ServiceError, '^credential-store-timeout$'): t._macos_credential('fixture','fixture')

    def test_non_macos_uses_bounded_keyring_reader(self):
        for platform in ('linux','win32'):
            with self.subTest(platform=platform), patch.object(t.sys,'platform',platform), patch.object(t,'_read_keyring_credential',return_value='private-key') as read, patch.object(t,'_macos_credential',side_effect=AssertionError):
                self.assertEqual(t.credential('fixture',{},service='existing'), ('private-key','os-store'))
                read.assert_called_once_with('fixture','existing')

    def test_owned_credential_process_returns_only_private_pipe_value(self):
        with patch.object(t, '_credential_worker', successful_credential_worker):
            self.assertEqual(t._read_keyring_credential('fixture-account', 'fixture-service'), 'synthetic-process-credential')

    def test_owned_credential_process_redacts_unexpected_errors(self):
        with patch.object(t, '_credential_worker', failed_credential_worker):
            with self.assertRaises(t.ServiceError) as error: t._read_keyring_credential('fixture-account', 'fixture-service')
        self.assertEqual(str(error.exception), 'credential-store-unavailable')

    def test_credential_timeout_status_is_unverified_without_http(self):
        with patch.object(t, '_read_stored_credential', side_effect=t.ServiceError('credential-store-timeout')), patch.dict(os.environ, {}, clear=True), patch.object(t, 'request', side_effect=AssertionError):
            self.assertEqual(t.auth('status','fixture','jev-1.13.0'), {'configured':False,'verified':False,'reason':'credential-store-timeout'})

    def test_owned_transport_process_is_killed_on_deadline(self):
        import multiprocessing
        if 'fork' not in multiprocessing.get_all_start_methods(): self.skipTest('fork required for isolated delayed transport fixture')
        context = multiprocessing.get_context('fork')
        started = time.monotonic()
        def delayed(*args, **kwargs):
            time.sleep(5)
            return {}, 1
        with patch.object(t.multiprocessing, 'get_context', return_value=context), patch.object(t,'_request_loop',side_effect=delayed), patch.object(t,'DEADLINE',0.3):
            with self.assertRaises(t.ServiceError) as e: t.request(self.payload(),'fixture')
        self.assertEqual(e.exception.code,'deadline-exceeded')
        self.assertLess(time.monotonic()-started, 1.5)

    def test_insecure_keyring_rejected(self):
        class FakeKeyring:
            @staticmethod
            def get_keyring(): return object()
        with patch.dict(sys.modules, {'keyring':FakeKeyring}):
            with self.assertRaises(t.ServiceError) as e: t.secure_backend()
        self.assertEqual(e.exception.code,'unsupported-credential-store')


if __name__ == '__main__': unittest.main()
