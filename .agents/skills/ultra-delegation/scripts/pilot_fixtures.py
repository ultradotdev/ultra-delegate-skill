#!/usr/bin/env python3
"""Executable repository fixtures and paired routing campaigns.

This helper materializes files and records observations. The coordinator runs all
native workers, compilers, tests, and independent reviews. No network or credentials.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import html
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capability_index as research
import pilot
import pilot_core as core
import pilot_questions as questions

ASSET = Path(__file__).resolve().parent.parent / 'assets' / 'repository-fixtures.json'
SCHEMA = 'ultra-repository-campaign-v1'
ARMS = ('without_epoch', 'with_epoch')
THRESHOLDS = (0.80, 0.85, 0.90, 0.95)
FAMILIES = {'implementation', 'tests', 'review'}
LANGUAGES = {'python', 'typescript', 'go', 'rust'}


def _hash(value):
    core.require(isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value), 'invalid-hash')
    return value


def fixtures():
    data = pilot.read_json(ASSET)
    core.require(data['schema'] == 'ultra-repository-fixtures-v1', 'invalid-fixture-schema')
    cases = data['cases']
    core.require(len(cases) == 12 and len({c['id'] for c in cases}) == 12, 'invalid-fixture-count')
    core.require({(c['language'], c['family']) for c in cases} == {(l, f) for l in LANGUAGES for f in FAMILIES}, 'incomplete-fixture-matrix')
    for split in ('development', 'test'):
        subset = [c for c in cases if c['split'] == split]
        core.require(len(subset) == 6 and {c['language'] for c in subset} == LANGUAGES and {c['family'] for c in subset} == FAMILIES, 'invalid-fixture-split')
    for case in cases:
        core.require(case['starting_revision'] == core.digest({'files': case['files'], 'requirements': case['requirements']}), 'fixture-revision-mismatch')
        for file_set in (case['files'], case['checks'], case['reference_solution'], *case['mutants'].values()):
            for name, text in file_set.items():
                core.require(isinstance(name, str) and Path(name).name == name and name not in {'.', '..'} and isinstance(text, str), 'unsafe-fixture-path')
    return data


def fixture(identifier):
    matches = [c for c in fixtures()['cases'] if c['id'] == identifier]
    core.require(len(matches) == 1, 'unknown-fixture')
    return matches[0]


def _write_files(directory, files):
    directory.mkdir(parents=True, exist_ok=False)
    for name, contents in files.items():
        (directory / name).write_text(contents, encoding='utf-8', newline='\n')


def materialize(identifier, directory):
    """Keep evaluator references beside, never inside, the worker checkout."""
    case = fixture(identifier)
    directory = Path(directory)
    core.require(not directory.exists(), 'fixture-directory-exists')
    directory.mkdir(parents=True)
    instructions = '# ' + case['summary'] + '\n\n' + '\n'.join('- ' + r for r in case['requirements'])
    instructions += '\n\nSubmit your patch or findings and commands actually run. Do not inspect the sibling evaluator directory.\n'
    _write_files(directory / 'worker', {**case['files'], 'TASK.md': instructions})
    _write_files(directory / 'evaluator' / 'checks', case['checks'])
    _write_files(directory / 'evaluator' / 'reference', {**case['files'], **case['reference_solution'], **case['checks']})
    for name, replacements in case['mutants'].items():
        _write_files(directory / 'evaluator' / 'mutants' / name, {**case['files'], **replacements})
    pilot.write_new(directory / 'evaluator' / 'contract.json', case)
    guide = '''# Independent evaluation

Use the worker directory as the isolated native-worker checkout. Keep this evaluator
folder out of the worker packet. Starter files and requirements are content-hashed
as starting_revision; use that identifier alongside the actual checkout commit.

Implementation: copy evaluator/checks into the completed worker checkout and run
the command in contract.json. Rust also requires running ./check-bin after compile.
Never give the reference solution to the worker. Checks do not replace review.

Tests: run submitted tests against the original module, then separately against
each evaluator/mutants replacement. Keep submitted tests unchanged for every run.
Rust requires compiling tests.rs and running ./tests-bin. A mutant is killed only
when compilation succeeded and the submitted tests failed. Compilation failures,
timeouts, and toolchain errors are unavailable observations, not mutant kills.

Review: a separate reviewer maps each submitted finding to a reference_findings id
or null for an unsupported finding. Record concrete supporting locations/reasoning
in the local review artifact. Duplicate findings cannot inflate recall.

TypeScript uses Node >=22.18 with built-in type stripping; no npm packages. Go uses
the standard library and Go >=1.20. Rust uses rustc --edition=2021, no Cargo crates.
Python uses Python >=3.10 and unittest. No dependency download is needed.

Score input: {fixture_id, artifact_hash, worker_id, reviewer_id, reviewer_kind,
review_accepted, scope_passed, critical_defects, executions, findings}.
Each execution: {id, compiled, exit_code}; ids are baseline and mutant names for
tests, or contract for implementation. exit_code=null means unavailable.
Each finding: {id, reference_id}; reference_id=null means unsupported.
Reviewer kind must be human or frontier, distinct from worker. False review or
scope gates and any critical defects veto acceptance. Security scanning is optional.
The score validates the record shape; it cannot establish reviewer independence.
'''
    (directory / 'evaluator' / 'README.md').write_text(guide, encoding='utf-8')
    return {'fixture_id': identifier, 'starting_revision': case['starting_revision'], 'worker': str((directory / 'worker').resolve()),
            'evaluator': str((directory / 'evaluator').resolve()), 'commands': case['commands'], 'worker_test_command': case['worker_test_command'],
            'dispatch_authorized': False}


def score(raw):
    core.fields(raw, {'fixture_id', 'artifact_hash', 'worker_id', 'reviewer_id', 'reviewer_kind', 'review_accepted', 'scope_passed', 'critical_defects', 'executions', 'findings'})
    case = fixture(raw['fixture_id'])
    _hash(raw['artifact_hash'])
    core.label(raw['worker_id']); core.label(raw['reviewer_id'])
    core.require(raw['worker_id'] != raw['reviewer_id'] and raw['reviewer_kind'] in {'human', 'frontier'}, 'independent-review-required')
    for name in ('review_accepted', 'scope_passed'):
        core.require(type(raw[name]) is bool, 'invalid-review-gate')
    core.integer(raw['critical_defects'])
    core.require(isinstance(raw['executions'], list) and isinstance(raw['findings'], list), 'invalid-observations')
    executions = {}
    expected = set(case['mutants']) | {'baseline'} if case['family'] == 'tests' else {'contract'} if case['family'] == 'implementation' else set()
    for execution in raw['executions']:
        core.fields(execution, {'id', 'compiled', 'exit_code'})
        core.require(execution['id'] in expected and execution['id'] not in executions, 'unknown-or-duplicate-execution')
        core.require(type(execution['compiled']) is bool, 'invalid-compilation-status')
        code = execution['exit_code']
        core.require(code is None or (type(code) is int and 0 <= code <= 255), 'invalid-exit-code')
        executions[execution['id']] = execution
    result = {'schema': 'ultra-fixture-score-v1', 'fixture_id': case['id'], 'starting_revision': case['starting_revision'],
              'artifact_hash': raw['artifact_hash'], 'review_hash': core.digest(raw), 'rubric_version': case['rubric_version'],
              'reviewer_id': raw['reviewer_id'], 'reviewer_kind': raw['reviewer_kind'], 'worker_id': raw['worker_id'],
              'review_accepted': raw['review_accepted'], 'scope_passed': raw['scope_passed'], 'critical_defects': raw['critical_defects'],
              'mutation_detection': None, 'review_precision': None, 'review_recall': None, 'complete': True}
    if case['family'] == 'review':
        ids, matched, false_positives = set(), set(), 0
        references = {f['id'] for f in case['reference_findings']}
        for finding in raw['findings']:
            core.fields(finding, {'id', 'reference_id'}); core.label(finding['id'])
            core.require(finding['id'] not in ids, 'duplicate-finding'); ids.add(finding['id'])
            ref = finding['reference_id']
            core.require(ref is None or ref in references, 'unknown-reference-finding')
            if ref is None or ref in matched: false_positives += 1
            else: matched.add(ref)
        result.update(true_positives=len(matched), false_positives=false_positives, false_negatives=len(references - matched),
                      review_precision=len(matched) / len(ids) if ids else None, review_recall=len(matched) / len(references))
        passed = matched == references and false_positives == 0
    else:
        core.require(not raw['findings'], 'unexpected-findings')
        usable = {k: v for k, v in executions.items() if v['compiled'] and v['exit_code'] is not None}
        result['complete'] = set(usable) == expected
        if case['family'] == 'tests':
            killed = sum(name in usable and usable[name]['exit_code'] != 0 for name in case['mutants'])
            baseline = usable.get('baseline', {}).get('exit_code') == 0
            result.update(mutants_killed=killed, mutants_total=len(case['mutants']), baseline_passed=baseline,
                          mutation_detection=killed / len(case['mutants']) if result['complete'] else None)
            passed = baseline and killed == len(case['mutants']) and result['complete']
        else:
            passed = usable.get('contract', {}).get('exit_code') == 0
    result['accepted'] = bool(passed and raw['review_accepted'] and raw['scope_passed'] and raw['critical_defects'] == 0)
    return result


def prepare_campaign(manifest, index):
    """Freeze matched packet pairs; only Epoch descriptions differ between arms."""
    core.fields(manifest, {'policy', 'reference_configuration_id', 'cases'})
    policy = core.policy(manifest['policy'])
    core.require(policy['mode'] == 'active', 'active-policy-required')
    core.require(policy['pin_id'] is None, 'benchmark-pin-not-supported')
    research.validate(index)
    # The control arm retains provider/SWE claims already in the supplied packet.
    # The treatment receives only Epoch claims, not unrelated index changes.
    epoch = copy.deepcopy(index)
    epoch['claims'] = [c for c in epoch['claims'] if c.get('source_id', '').startswith('epoch')]
    core.require(epoch['claims'], 'epoch-claims-required')
    groups, cases = set(), []
    for item in manifest['cases']:
        core.fields(item, {'fixture_id', 'prepared_packet', 'evidence'})
        case = fixture(item['fixture_id']); packet = copy.deepcopy(item['prepared_packet'])
        core.validate_packet(packet)
        core.require(packet.get('user_choice_id') is None, 'benchmark-user-choice-not-supported')
        core.require(packet['task_id'] == case['id'] and packet.get('group_id') == case['id'], 'fixture-task-binding-mismatch')
        core.require(packet['task']['summary'] == case['summary'] and packet['task']['requirements'] == case['requirements'], 'fixture-contract-mismatch')
        core.require(case['id'] not in groups, 'duplicate-fixture'); groups.add(case['id'])
        core.require(isinstance(item['evidence'], list), 'invalid-evidence')
        core.require(len({c['effort'] for c in packet['candidates']}) == 1, 'benchmark-effort-mismatch')
        core.require({(c['provider'], c['host'], c['adapter']) for c in packet['candidates']} == {('openai', 'codex', 'codex-native')}, 'benchmark-native-scope-mismatch')
        cfgs = {core.configuration_id(c) for c in packet['candidates']}
        core.require(manifest['reference_configuration_id'] in cfgs, 'reference-unavailable')
        treated = copy.deepcopy(packet)
        for candidate in treated['candidates']:
            core.require('Epoch general ECI' not in candidate['capability_description'], 'control-already-contains-epoch')
            text = research.describe(epoch, candidate['provider'], candidate['model'], candidate['effort'], as_of=core.timestamp(packet['context']['observed_at']).date().isoformat())
            candidate['capability_description'] += '\n' + text
        core.validate_packet(treated)
        for arm_packet in (packet, treated):
            prepared = core.prepare(arm_packet, policy, item['evidence'], clock=core.timestamp(packet['context']['observed_at']))
            core.require(manifest['reference_configuration_id'] in {r['configuration_id'] for r in prepared['rows'] if r['eligible']}, 'reference-ineligible')
            core.transport.encoded_payload(questions.route_payload(arm_packet['task'], prepared['cards'], policy['model']))
        cases.append({'fixture_id': case['id'], 'split': case['split'], 'language': case['language'], 'family': case['family'],
                      'starting_revision': case['starting_revision'], 'fixture_hash': core.digest(case),
                      'packets': dict(zip(ARMS, (packet, treated))), 'evidence': copy.deepcopy(item['evidence'])})
    core.require(cases, 'empty-campaign')
    for case in cases:
        for previous in case['evidence']:
            core.require(previous.get('group_id') not in groups, 'evaluation-outcome-leakage')
            core.require(previous.get('synthetic') is not True, 'synthetic-evidence')
            core.require(core.timestamp(previous['created_at']) < core.timestamp(case['packets'][ARMS[0]]['context']['observed_at']), 'future-evidence')
    frozen = {'policy': policy, 'reference_configuration_id': manifest['reference_configuration_id'], 'cases': cases,
              'index_hash': core.digest(index), 'question_version': questions.ROUTING_VERSION, 'policy_version': core.DECISION_POLICY_VERSION}
    return {'schema': SCHEMA, 'frozen': frozen, 'campaign_hash': core.digest(frozen), 'decisions': [], 'observations': [], 'threshold_freeze': None}


def validate_campaign(campaign):
    core.fields(campaign, {'schema', 'frozen', 'campaign_hash', 'decisions', 'observations', 'threshold_freeze'})
    core.require(campaign['schema'] == SCHEMA and core.digest(campaign['frozen']) == campaign['campaign_hash'], 'campaign-freeze-mismatch')
    core.require(campaign['frozen']['question_version'] == questions.ROUTING_VERSION and campaign['frozen']['policy_version'] == core.DECISION_POLICY_VERSION, 'campaign-runtime-version-mismatch')
    for case in campaign['frozen']['cases']:
        core.require(case['starting_revision'] == fixture(case['fixture_id'])['starting_revision'], 'fixture-revision-mismatch')
        core.require(case['fixture_hash'] == core.digest(fixture(case['fixture_id'])), 'fixture-evaluation-mismatch')
    freeze = campaign['threshold_freeze']
    if freeze is not None:
        core.fields(freeze, {'threshold', 'sweep_hash', 'development_decisions_hash', 'development_observations_hash', 'recorded_at', 'freeze_hash'})
        core.require(freeze['threshold'] in THRESHOLDS, 'unsupported-threshold')
        core.require(freeze['freeze_hash'] == core.digest({k: v for k, v in freeze.items() if k != 'freeze_hash'}), 'threshold-freeze-mismatch')
        development = {c['fixture_id'] for c in campaign['frozen']['cases'] if c['split'] == 'development'}
        decisions = [d for d in campaign['decisions'] if d['fixture_id'] in development]
        observations = [o for o in campaign['observations'] if o['fixture_id'] in development]
        core.require(core.digest(decisions) == freeze['development_decisions_hash'] and core.digest(observations) == freeze['development_observations_hash'], 'development-freeze-mismatch')
    return campaign


def _case(campaign, identifier):
    validate_campaign(campaign)
    matches = [c for c in campaign['frozen']['cases'] if c['fixture_id'] == identifier]
    core.require(len(matches) == 1, 'unknown-campaign-case')
    return matches[0]


def _policy(campaign, split):
    p = copy.deepcopy(campaign['frozen']['policy'])
    if split == 'test':
        frozen = campaign['threshold_freeze']
        core.require(frozen is not None, 'freeze-threshold-before-heldout')
        for key in ('operation_match', 'reasoning_fit', 'code_interaction_fit', 'context_synthesis_fit'):
            if key in p['thresholds']: p['thresholds'][key] = frozen['threshold']
    return p


def route_input(campaign, identifier, arm):
    case = _case(campaign, identifier); core.require(arm in ARMS, 'invalid-arm')
    return {'prepared_packet': copy.deepcopy(case['packets'][arm]), 'policy': _policy(campaign, case['split']),
            'evidence': copy.deepcopy(case['evidence']), 'dispatch_authorized': False}


def record_decision(campaign, identifier, arm, decision):
    case = _case(campaign, identifier); expected = route_input(campaign, identifier, arm)
    packet, p = expected['prepared_packet'], expected['policy']
    core.require(decision['input_hash'] == core.digest(packet) and decision['evidence_hash'] == core.digest(case['evidence']) and decision['policy_hash'] == core.digest(p), 'decision-freeze-mismatch')
    core.require(decision['question_version'] == campaign['frozen']['question_version'], 'decision-question-mismatch')
    core.require(not decision.get('synthetic', False) and decision['router']['attempts'] > 0 and decision['status'] in {'ok', 'abstained', 'unavailable'}, 'inference-observation-required')
    core.require(decision['id'] == 'dec_' + core.digest({k: v for k, v in decision.items() if k != 'id'})[:24], 'decision-record-mismatch')
    prepared = core.prepare(packet, p, case['evidence'], clock=core.timestamp(packet['context']['observed_at']))
    payload = questions.route_payload(packet['task'], prepared['cards'], p['model'])
    core.require(decision['question_hash'] == core.digest(payload['questions']) and decision['payload_hash'] == core.digest(payload), 'decision-question-mismatch')
    if decision['status'] in {'ok', 'abstained'}:
        answers = copy.deepcopy(decision['signals'])
        for name, question in payload['questions'].items():
            if question['type'] == 'score' and name in answers:
                answers[name]['legend'] = {str(i): text for i, text in enumerate(question['criteria'])}
        core.transport.validate_response(payload, {'model': p['model'], 'answers': answers, 'usage': {'input_tokens': 0, 'output_tokens': 0}})
        recommendation = core.recommendation(packet, prepared, decision['signals'], p)
        core.require(recommendation['action'] == decision['action'] and recommendation['configuration_id'] == decision['selected_configuration_id'], 'decision-selection-mismatch')
    existing = [d for d in campaign['decisions'] if d['fixture_id'] == identifier and d['arm'] == arm]
    if existing:
        core.require(existing[0]['decision'] == decision, 'decision-already-recorded')
        return campaign
    core.require(campaign['threshold_freeze'] is None or case['split'] != 'development', 'development-already-frozen')
    campaign['decisions'].append({'fixture_id': identifier, 'arm': arm, 'decision': copy.deepcopy(decision)})
    return campaign


def execution_plan(campaign, identifier):
    case = _case(campaign, identifier)
    decisions = {d['arm']: d['decision'] for d in campaign['decisions'] if d['fixture_id'] == identifier}
    core.require(set(decisions) == set(ARMS), 'paired-decisions-required')
    packet = case['packets'][ARMS[0]]
    p = _policy(campaign, case['split'])
    prepared = core.prepare(packet, p, case['evidence'], clock=core.timestamp(packet['context']['observed_at']))
    eligible = {r['configuration_id'] for r in prepared['rows'] if r['eligible']}
    configs = {core.configuration_id(c): c for c in packet['candidates']}
    runs = {}
    for arm, decision in decisions.items():
        if decision['action'] == 'route':
            cfg = decision['selected_configuration_id']; core.require(cfg in eligible, 'selected-ineligible')
            runs.setdefault(cfg, []).append(arm)
    reference = campaign['frozen']['reference_configuration_id']; runs.setdefault(reference, []).append('fixed_reference')
    if len(runs) == 1:
        challengers = sorted(eligible - set(runs), key=lambda cfg: core.digest([identifier, cfg]))
        if challengers: runs[challengers[0]] = ['rotating_challenger']
    return {'fixture_id': identifier, 'dispatch_authorized': False, 'runs': [
        {'run_id': 'run_' + core.digest([campaign['campaign_hash'], identifier, cfg])[:24], 'configuration_id': cfg,
         'model': configs[cfg]['model'], 'effort': configs[cfg]['effort'], 'roles': roles,
         'shared_observation': len(roles) > 1, 'starting_revision': case['starting_revision']}
        for cfg, roles in sorted(runs.items())],
        'note': 'One actual run per identical fixture/configuration, shared across roles explicitly. Recheck current host eligibility immediately before native dispatch.'}


def record_observation(campaign, raw):
    core.fields(raw, {'fixture_id', 'configuration_id', 'attempt_id', 'attempt_kind', 'score', 'latency_ms', 'costs'})
    case = _case(campaign, raw['fixture_id']); _policy(campaign, case['split'])
    core.label(raw['attempt_id'])
    core.require(raw['attempt_kind'] in {'initial', 'comparison', 'repair', 'fallback'}, 'invalid-attempt-kind')
    plan = execution_plan(campaign, raw['fixture_id'])
    packet = case['packets'][ARMS[0]]
    prepared = core.prepare(packet, _policy(campaign, case['split']), case['evidence'], clock=core.timestamp(packet['context']['observed_at']))
    eligible = {row['configuration_id'] for row in prepared['rows'] if row['eligible']}
    core.require(raw['configuration_id'] in eligible, 'unknown-outcome-configuration')
    if raw['attempt_kind'] in {'initial', 'comparison'}:
        core.require(raw['configuration_id'] in {r['configuration_id'] for r in plan['runs']}, 'unplanned-observation')
    result = score(raw['score'])
    core.require(result['fixture_id'] == raw['fixture_id'], 'score-fixture-mismatch')
    core.require(core.transport.number(raw['latency_ms'], 0, 1e12), 'invalid-latency')
    core.fields(raw['costs'], {'preparation', 'worker', 'review', 'retry', 'fallback'})
    for value in raw['costs'].values(): core.validate_cost(value)
    observation = {k: copy.deepcopy(v) for k, v in raw.items() if k != 'score'}
    observation['score'] = result
    observation['observation_hash'] = core.digest(raw)
    found = [o for o in campaign['observations'] if o['attempt_id'] == raw['attempt_id']]
    if found:
        core.require(found[0] == observation, 'attempt-already-recorded')
        return campaign
    if raw['attempt_kind'] in {'initial', 'comparison'}:
        core.require(not any(o['fixture_id'] == raw['fixture_id'] and o['configuration_id'] == raw['configuration_id'] and o['attempt_kind'] in {'initial', 'comparison'} for o in campaign['observations']), 'initial-configuration-already-observed')
    core.require(campaign['threshold_freeze'] is None or case['split'] != 'development', 'development-already-frozen')
    campaign['observations'].append(observation)
    return campaign


def _replay(campaign, entry, threshold):
    case = _case(campaign, entry['fixture_id']); packet = case['packets'][entry['arm']]
    decision = entry['decision']; p = copy.deepcopy(campaign['frozen']['policy'])
    for key in ('operation_match', 'reasoning_fit', 'code_interaction_fit', 'context_synthesis_fit'):
        if key in p['thresholds']: p['thresholds'][key] = threshold
    prepared = core.prepare(packet, p, case['evidence'], clock=core.timestamp(packet['context']['observed_at']))
    if decision['status'] not in {'ok', 'abstained'}: return None
    return core.recommendation(packet, prepared, decision['signals'], p)


def threshold_sweep(campaign):
    validate_campaign(campaign)
    development = {c['fixture_id'] for c in campaign['frozen']['cases'] if c['split'] == 'development'}
    entries = [d for d in campaign['decisions'] if d['fixture_id'] in development]
    rows = []
    for threshold in THRESHOLDS:
        routed = observed = accepted = failures = 0
        for entry in entries:
            recommendation = _replay(campaign, entry, threshold)
            if recommendation is None or recommendation['action'] != 'route': continue
            routed += 1
            matches = [o for o in campaign['observations'] if o['fixture_id'] == entry['fixture_id'] and o['configuration_id'] == recommendation['configuration_id'] and o['attempt_kind'] in {'initial', 'comparison'} and o['score']['complete']]
            if matches:
                observed += 1; accepted += matches[0]['score']['accepted']; failures += not matches[0]['score']['accepted']
        rows.append({'threshold': threshold, 'routed': routed, 'routing_observations': len(entries), 'worker_outcomes_known': observed,
                     'accepted': accepted, 'failed': failures, 'worker_outcomes_pending': routed-observed,
                     'coverage': routed/len(entries) if entries else None, 'acceptance_rate': accepted/observed if observed else None})
    return {'schema': 'ultra-threshold-sweep-v1', 'split': 'development', 'rows': rows,
            'note': 'Replays recorded inference only. Reused worker observations are correlated, not extra samples. Missing worker outcomes remain pending.'}


def freeze_threshold(campaign, threshold):
    validate_campaign(campaign); core.require(threshold in THRESHOLDS, 'unsupported-threshold')
    core.require(campaign['threshold_freeze'] is None, 'threshold-already-frozen')
    dev = {c['fixture_id'] for c in campaign['frozen']['cases'] if c['split'] == 'development'}
    core.require(dev and {(d['fixture_id'], d['arm']) for d in campaign['decisions'] if d['fixture_id'] in dev} == {(c, a) for c in dev for a in ARMS}, 'development-routing-incomplete')
    core.require(not any(d['fixture_id'] not in dev for d in campaign['decisions']), 'heldout-already-observed')
    sweep = threshold_sweep(campaign)
    selected = next(r for r in sweep['rows'] if r['threshold'] == threshold)
    core.require(selected['worker_outcomes_known'] > 0 and selected['worker_outcomes_pending'] == 0, 'development-outcomes-incomplete')
    campaign['threshold_freeze'] = {'threshold': threshold, 'sweep_hash': core.digest(sweep), 'development_decisions_hash': core.digest(campaign['decisions']),
                                    'development_observations_hash': core.digest(campaign['observations']), 'recorded_at': core.now()}
    campaign['threshold_freeze']['freeze_hash'] = core.digest(campaign['threshold_freeze'])
    return campaign


def campaign_report(campaign):
    validate_campaign(campaign)
    rows, comparisons = [], []
    workload_complete = True
    reference_id = campaign['frozen']['reference_configuration_id']
    def observed_cost(observation):
        if observation is None or not observation['score']['complete']: return None
        values = list(observation['costs'].values())
        if any(v['usd'] is None for v in values): return None
        return sum(v['usd'] for v in values)
    for case in campaign['frozen']['cases']:
        case_decisions = [d for d in campaign['decisions'] if d['fixture_id'] == case['fixture_id']]
        case_observations = [o for o in campaign['observations'] if o['fixture_id'] == case['fixture_id']]
        if {d['arm'] for d in case_decisions} != set(ARMS):
            workload_complete = False
        else:
            planned = execution_plan(campaign, case['fixture_id'])['runs']
            for run in planned:
                if not any(o['configuration_id'] == run['configuration_id'] and o['attempt_kind'] in {'initial', 'comparison'} and o['score']['complete'] for o in case_observations):
                    workload_complete = False
        for arm in ARMS:
            entry = next((d for d in campaign['decisions'] if d['fixture_id'] == case['fixture_id'] and d['arm'] == arm), None)
            decision = entry['decision'] if entry else None
            selected = decision.get('selected_configuration_id') if decision and decision['action'] == 'route' else None
            observations = case_observations
            primary = next((o for o in observations if o['configuration_id'] == selected and o['attempt_kind'] in {'initial', 'comparison'}), None)
            paired = [d for d in campaign['decisions'] if d['fixture_id'] == case['fixture_id'] and d['decision'].get('selected_configuration_id') == selected]
            rows.append({'fixture_id': case['fixture_id'], 'language': case['language'], 'family': case['family'], 'split': case['split'], 'arm': arm,
                         'action': decision['action'] if decision else 'pending', 'status': decision['status'] if decision else 'pending', 'selected_configuration_id': selected,
                         'first_attempt_accepted': primary['score']['accepted'] if primary and primary['score']['complete'] else None,
                         'eventual_fixture_acceptance': any(o['score']['accepted'] for o in observations) if observations else None,
                         'observed_attempts': len(observations), 'recovery_attempts': sum(o['attempt_kind'] in {'repair','fallback'} for o in observations),
                         'shared_selected_observation': primary is not None and len(paired) > 1,
                         'router_latency_ms': decision['router']['latency_ms'] if decision else None})
            reference = next((o for o in observations if o['configuration_id'] == reference_id and o['attempt_kind'] in {'initial', 'comparison'}), None)
            primary_cost, reference_cost = observed_cost(primary), observed_cost(reference)
            router_cost = decision['router'].get('cost_usd') if decision else None
            comparable = bool(primary and reference and primary['score']['accepted'] and reference['score']['accepted']
                              and primary_cost is not None and reference_cost is not None and router_cost is not None)
            comparison = {'fixture_id': case['fixture_id'], 'arm': arm, 'status': 'observed-comparison' if comparable else 'pending-or-not-comparable',
                          'kind': None, 'selected_plus_router_usd': None, 'reference_usd': None, 'counterfactual_difference_usd': None,
                          'shared_reference_run': bool(primary and reference and primary['attempt_id'] == reference['attempt_id']),
                          'note': 'Selected first attempt plus its router versus the fixed reference, including each recorded preparation/review component. Other campaign comparisons and recoveries remain in workload totals; this is not realized savings.'}
            if comparable:
                kinds = [v['kind'] for o in (primary, reference) for v in o['costs'].values()] + [decision['router']['cost_kind']]
                comparison.update(kind='measured' if all(k == 'measured' for k in kinds) else 'estimated',
                                  selected_plus_router_usd=primary_cost+router_cost, reference_usd=reference_cost,
                                  counterfactual_difference_usd=reference_cost-primary_cost-router_cost)
            comparisons.append(comparison)
    monetary = [c for o in campaign['observations'] for c in o['costs'].values()]
    routers = [d['decision']['router'] for d in campaign['decisions']]
    observed_costs_known = bool(campaign['observations']) and all(c['usd'] is not None for c in monetary) and all(r.get('cost_usd') is not None for r in routers)
    costs_known = workload_complete and observed_costs_known
    costs_measured = costs_known and all(c['kind'] == 'measured' for c in monetary) and all(r.get('cost_kind') == 'measured' for r in routers)
    total = sum(c['usd'] for c in monetary) + sum(r['cost_usd'] for r in routers) if costs_known else None
    known_rows = [r for r in rows if r['first_attempt_accepted'] is not None]
    report = {'schema': 'ultra-repository-benchmark-report-v1', 'campaign_hash': campaign['campaign_hash'], 'threshold_freeze': campaign['threshold_freeze'],
              'summary': {'fixture_count': len(campaign['frozen']['cases']), 'routing_decisions': len(campaign['decisions']), 'actual_worker_attempts': len(campaign['observations']),
                          'first_attempt_results_known': len(known_rows), 'first_attempt_accepted': sum(r['first_attempt_accepted'] for r in known_rows),
                          'accepted_fixtures': len({o['fixture_id'] for o in campaign['observations'] if o['score']['accepted']}),
                          'critical_defects': sum(o['score']['critical_defects'] for o in campaign['observations']),
                          'total_workload_usd': total, 'cost_kind': 'measured' if costs_measured else 'estimated' if costs_known else 'unknown',
                          'workload_complete': workload_complete,
                          'observed_workload_subtotal_usd': sum(c['usd'] for c in monetary)+sum(r['cost_usd'] for r in routers) if observed_costs_known else None,
                          'summed_router_latency_ms': sum(r['latency_ms'] for r in routers),
                          'summed_worker_latency_ms': sum(o['latency_ms'] for o in campaign['observations']),
                          'savings_usd': None, 'savings_status': 'not-established', 'security': 'off-unless-separately-recorded'},
              'cases': rows, 'paired_cost_comparisons': comparisons,
              'arm_metrics': {arm: {'routing_observations': sum(r['arm'] == arm and r['status'] != 'pending' for r in rows),
                                   'routes': sum(r['arm'] == arm and r['action'] == 'route' and r['status'] == 'ok' for r in rows),
                                   'first_attempt_results_known': sum(r['arm'] == arm for r in known_rows),
                                   'first_attempt_accepted': sum(r['arm'] == arm and r['first_attempt_accepted'] for r in known_rows)} for arm in ARMS},
              'observations': copy.deepcopy(campaign['observations']), 'threshold_sweep': threshold_sweep(campaign),
              'limitations': ['This is a small repository-fixture benchmark, not a certification.', 'A shared run is counted once in workload costs and is not independent evidence for each arm.',
                             'Eventual fixture acceptance includes the fixed reference and is not attributed to either routing arm.', 'Unknown billing and missing worker outcomes are not estimated from templates.']}
    return report


def write_report(campaign, prefix):
    report = campaign_report(campaign); prefix = Path(prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    pilot.write_new(prefix.with_suffix('.json'), report)
    esc = lambda x: html.escape(str(x))
    summary = report['summary']
    body = '<h1>Repository routing trial</h1><p>' + f"{summary['accepted_fixtures']}/{summary['fixture_count']} fixtures accepted · {summary['actual_worker_attempts']} actual worker attempts · {summary['routing_decisions']} routing decisions" + '</p>'
    body += '<p>Workload cost: ' + (esc(summary['total_workload_usd']) + ' USD (' + summary['cost_kind'] + ')' if summary['total_workload_usd'] is not None else 'unavailable') + '. Savings: not established.</p>'
    body += '<table><thead><tr><th>Task</th><th>Arm</th><th>Selected</th><th>First pass</th><th>Eventually accepted</th><th>Recovery attempts</th></tr></thead><tbody>'
    for row in report['cases']:
        verdict = lambda value: 'pending' if value is None else 'yes' if value else 'no'
        body += '<tr>' + ''.join('<td>'+esc(x)+'</td>' for x in (row['fixture_id'], row['arm'], row['selected_configuration_id'] or row['action'], verdict(row['first_attempt_accepted']), verdict(row['eventual_fixture_acceptance']), row['recovery_attempts'])) + '</tr>'
    body += '</tbody></table><details><summary>Evidence and limitations</summary><pre>' + esc(json.dumps(report, indent=2)) + '</pre></details>'
    document = '<!doctype html><meta charset="utf-8"><title>Repository routing trial</title><style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;text-align:left;padding:.6rem}pre{white-space:pre-wrap;font-size:12px}details{margin-top:2rem}</style>' + body
    with prefix.with_suffix('.html').open('x', encoding='utf-8') as stream: stream.write(document)
    return {'html': str(prefix.with_suffix('.html').resolve()), 'json': str(prefix.with_suffix('.json').resolve())}


def main(argv=None):
    parser = pilot.SafeParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    material = sub.add_parser('materialize'); material.add_argument('--fixture', required=True); material.add_argument('--directory', required=True)
    scoring = sub.add_parser('score'); scoring.add_argument('--input', required=True)
    preparing = sub.add_parser('prepare'); preparing.add_argument('--input', required=True); preparing.add_argument('--index', required=True); preparing.add_argument('--output', required=True)
    for name in ('route-input', 'execution-plan', 'record-decision', 'record-observation', 'sweep', 'freeze-threshold', 'report'):
        p = sub.add_parser(name); p.add_argument('--campaign', required=True)
        if name in {'route-input', 'execution-plan', 'record-decision'}: p.add_argument('--fixture', required=True)
        if name in {'route-input', 'record-decision'}: p.add_argument('--arm', choices=ARMS, required=True)
        if name in {'record-decision', 'record-observation'}: p.add_argument('--input', required=True)
        if name == 'freeze-threshold': p.add_argument('--threshold', type=float, choices=THRESHOLDS, required=True)
        if name in {'record-decision', 'record-observation', 'freeze-threshold'}: p.add_argument('--output', required=True)
        if name == 'report': p.add_argument('--output-prefix', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'list':
            result = [{k: c[k] for k in ('id', 'language', 'family', 'split', 'summary', 'starting_revision')} for c in fixtures()['cases']]
        elif args.command == 'materialize': result = materialize(args.fixture, args.directory)
        elif args.command == 'score': result = score(pilot.read_json(args.input))
        elif args.command == 'prepare':
            campaign = prepare_campaign(pilot.read_json(args.input), research.load(args.index)); pilot.write_new(Path(args.output), campaign)
            result = {'campaign_hash': campaign['campaign_hash'], 'output': args.output}
        else:
            campaign = pilot.read_json(args.campaign)
            if args.command == 'route-input': result = route_input(campaign, args.fixture, args.arm)
            elif args.command == 'execution-plan': result = execution_plan(campaign, args.fixture)
            elif args.command == 'sweep': result = threshold_sweep(campaign)
            elif args.command == 'report': result = write_report(campaign, args.output_prefix)
            else:
                if args.command == 'record-decision': record_decision(campaign, args.fixture, args.arm, pilot.read_json(args.input))
                elif args.command == 'record-observation': record_observation(campaign, pilot.read_json(args.input))
                else: freeze_threshold(campaign, args.threshold)
                pilot.write_new(Path(args.output), campaign); result = {'output': args.output, 'campaign_hash': campaign['campaign_hash']}
        print(json.dumps(result)); return 0
    except (ValueError, OSError, KeyError, TypeError, core.transport.ServiceError):
        print('{"error":"repository-benchmark-failed"}', file=sys.stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())
