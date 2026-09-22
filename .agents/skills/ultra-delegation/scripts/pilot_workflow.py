"""Resumable native-host plans. The coordinator executes tools; this module never does."""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
from pathlib import Path
import re
import tempfile
from contextlib import contextmanager

import pilot_core as core


def contract_hash(packet):
    value = copy.deepcopy(packet)
    value['context'].pop('observed_at', None)
    return core.digest(value)


def task_contract_hash(packet):
    """The immutable task, choice, and native-host boundary for a request."""
    value = copy.deepcopy(packet)
    value.pop('candidates', None)
    value['context'].pop('observed_at', None)
    return core.digest(value)


def _evidence_snapshot(outcomes):
    return [{'id': row['id'], 'hash': core.digest(row)} for row in outcomes]


def _require_evidence_snapshot(request, decision, outcomes, identifier):
    """Freeze route evidence while allowing only later outcomes for this request."""
    snapshot = request.get('evidence_snapshot')
    core.require(isinstance(snapshot, list), 'missing-evidence-snapshot')
    by_id = {row['id']: row for row in outcomes}
    frozen = []
    for saved in snapshot:
        core.require(isinstance(saved, dict) and set(saved) == {'id', 'hash'}, 'invalid-evidence-snapshot')
        row = by_id.get(saved['id'])
        core.require(row is not None and core.digest(row) == saved['hash'], 'decision-evidence-changed')
        frozen.append(row)
    core.require(core.digest(frozen) == decision['evidence_hash'], 'decision-evidence-changed')
    frozen_ids = {row['id'] for row in frozen}
    cutoff = core.timestamp(request['evidence_cutoff_at'])
    current = core.timestamp(core.now())
    for row in outcomes:
        if row['id'] in frozen_ids:
            continue
        core.require(row.get('request_id') == identifier and cutoff <= core.timestamp(row['created_at']) <= current,
                     'decision-evidence-changed')


def _path(root, identifier):
    core.require(isinstance(identifier, str) and re.fullmatch(r'req_[a-f0-9]{24}', identifier), 'invalid-request-id')
    core.require(not Path(root).is_symlink(), 'symlink-workflow')
    path = Path(root).resolve() / 'workflows' / (identifier + '.json')
    core.require(not path.is_symlink() and not path.parent.is_symlink(), 'symlink-workflow')
    return path


def _seal(value):
    value['integrity'] = core.digest({k: v for k, v in value.items() if k != 'integrity'})
    return value


@contextmanager
def _lock(path):
    """Cross-process lock released by the OS if this coordinator dies."""
    core.require(not path.is_symlink(), 'symlink-workflow')
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    try:
        if os.name == 'nt':
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b'0')
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == 'nt':
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _read(path, identifier):
    import pilot
    value = pilot.read_json(path)
    core.require(value.get('id') == identifier and value.get('schema') == 'ultra-pilot-request-v1', 'invalid-request')
    core.require(value.get('integrity') == core.digest({k: v for k, v in value.items() if k != 'integrity'}), 'request-changed')
    return value


def _write(path, value):
    _seal(value)
    temp_fd, name = tempfile.mkstemp(prefix='.workflow-', dir=path.parent)
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _expire(request):
    if request['state'] != 'in-progress':
        return False
    limit = request['limits'].get('max_elapsed_seconds')
    elapsed = (dt.datetime.now(dt.timezone.utc) - core.timestamp(request['created_at'])).total_seconds()
    if limit and elapsed >= limit:
        request.update(state='coordinator-required', reason_code='elapsed-limit')
        return True
    return False


def get(root, identifier, *, _check_elapsed=True):
    path = _path(root, identifier)
    value = _read(path, identifier)
    if _check_elapsed and _expire(value):
        with _lock(path.with_suffix('.lock')):
            value = _read(path, identifier)
            if _expire(value):
                _write(path, value)
    return value


def _new_attempt(request, configuration, kind, parent=None):
    number = len(request['attempts']) + 1
    attempt = {'id': 'attempt-' + str(number), 'configuration_id': configuration, 'kind': kind,
               'state': 'planned', 'parent_attempt_id': parent, 'decision_id': request['decision_id'],
               'created_at': core.now()}
    request['attempts'].append(attempt)
    return attempt


def start(root, decision, packet, policy, bakeoff='auto'):
    import pilot
    core.require(bakeoff in {'auto', 'on', 'off'}, 'invalid-bakeoff')
    core.require(isinstance(decision, dict) and isinstance(decision.get('id'), str), 'invalid-decision')
    identifier = 'req_' + core.digest({'decision': decision['id'], 'bakeoff': bakeoff})[:24]
    path = _path(root, identifier)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock(path.with_suffix('.lock')):
        if path.exists():
            return _read(path, identifier)
        policy = core.policy(policy)
        core.require(decision == pilot.get_decision(root, decision['id']), 'decision-changed')
        core.require(policy == pilot.load_policy(root), 'policy-changed')
        pilot.recheck(root, decision['id'], packet)
        selected = decision['selected_configuration_id']
        alternatives = decision.get('alternative_configuration_ids', [])
        # Overrides deliberately carry no model alternatives.
        pool = list(dict.fromkeys([selected, *alternatives]))
        outcomes = pilot.load_records(root, 'outcomes')
        core.require(core.digest(outcomes) == decision['evidence_hash'], 'decision-evidence-changed')
        history = next((r['evidence'] for r in decision.get('candidate_assessments', []) if r['configuration_id'] == selected), None)
        if history is None:
            history = next(r['evidence'] for r in decision['candidates'] if r['configuration_id'] == selected)
        compare = bakeoff == 'on' or (bakeoff == 'auto' and (not history.get('groups') or history.get('recent_failure', False)))
        request = {'schema': 'ultra-pilot-request-v1', 'id': identifier, 'decision_id': decision['id'],
                   'created_at': core.now(), 'state': 'in-progress', 'task_id': packet['task_id'],
                   'group_id': packet.get('group_id', packet['task_id']), 'synthetic': packet.get('synthetic', False),
                   'contract_hash': contract_hash(packet), 'policy_hash': core.digest(policy),
                   'task_contract_hash': task_contract_hash(packet),
                   'decision_policy_version': core.DECISION_POLICY_VERSION, 'pool': pool,
                   'acceptance_gates': decision['acceptance_gates'], 'bakeoff': bakeoff,
                   'limits': policy['workflow'], 'attempts': [], 'events': [], 'accepted_attempt_id': None,
                   'decision_history': [decision['id']], 'evidence_snapshot': _evidence_snapshot(outcomes),
                   'evidence_cutoff_at': core.now()}
        _new_attempt(request, selected, 'initial')
        if compare and len(pool) > 1 and policy['workflow'].get('max_attempts') != 1:
            _new_attempt(request, pool[1], 'comparison')
        _write(path, request)
        return request


def _attempt(request, identifier):
    row = next((a for a in request['attempts'] if a['id'] == identifier), None)
    core.require(row is not None, 'unknown-attempt')
    return row


def next_actions(request):
    if request['state'] != 'in-progress':
        return []
    limits = request['limits']
    if _expire(request):
        return [{'action': 'coordinator', 'reason_code': 'elapsed-limit'}]
    busy = sum(a['state'] in {'launching', 'running'} for a in request['attempts'])
    slots = max(0, (limits.get('max_concurrency') or len(request['pool'])) - busy)
    return [{'action': 'dispatch', 'attempt_id': a['id'], 'configuration_id': a['configuration_id'],
             'kind': a['kind'], 'recheck_required': True} for a in request['attempts'] if a['state'] == 'planned'][:slots]


def recheck(root, identifier, attempt_id, packet, *, _check_elapsed=True):
    import pilot
    request = get(root, identifier, _check_elapsed=_check_elapsed)
    a = _attempt(request, attempt_id)
    core.require(request['state'] == 'in-progress' and a['state'] == 'planned', 'attempt-not-dispatchable')
    core.require(any(x.get('attempt_id') == attempt_id for x in next_actions(request)), 'execution-limit')
    p = pilot.load_policy(root)
    core.require(core.digest(p) == request['policy_hash'], 'decision-policy-changed')
    core.require(request['decision_policy_version'] == core.DECISION_POLICY_VERSION, 'decision-policy-changed')
    core.require(contract_hash(packet) == request['contract_hash'], 'execution-inputs-changed')
    d = pilot.get_decision(root, request['decision_id'])
    core.require(not d['synthetic'], 'synthetic-decision-not-executable')
    outcomes = pilot.load_records(root, 'outcomes')
    _require_evidence_snapshot(request, d, outcomes, identifier)
    prepared = core.prepare(packet, p, outcomes)
    row = next((r for r in prepared['rows'] if r['configuration_id'] == a['configuration_id']), None)
    core.require(row is not None and row['eligible'], 'candidate-no-longer-eligible')
    return {'recheck': 'passed', 'request_id': identifier, 'attempt_id': attempt_id,
            'configuration_id': a['configuration_id'], 'execution': 'coordinator-native-host'}


def validate_observation(root, raw):
    request = get(root, raw['request_id'])
    a = _attempt(request, raw['attempt_id'])
    core.require(a['state'] == 'completed', 'attempt-not-completed')
    for key, expected in [('decision_id', a['decision_id']), ('configuration_id', a['configuration_id']),
                          ('artifact_hash', a['artifact_hash']), ('attempt_kind', a['kind']), ('worker_id', a['run_id'])]:
        core.require(raw.get(key) == expected, 'outcome-attempt-mismatch')


def _recover(request, attempt, repairable):
    if any(a['state'] in {'planned', 'launching', 'running', 'completed'} for a in request['attempts']):
        return  # Await the existing comparison before spending on recovery.
    limit = request['limits'].get('max_attempts')
    if limit and len(request['attempts']) >= limit:
        request.update(state='coordinator-required', reason_code='attempt-limit')
        return
    repairs = any(a['configuration_id'] == attempt['configuration_id'] and a['kind'] == 'repair' for a in request['attempts'])
    if repairable and not repairs:
        _new_attempt(request, attempt['configuration_id'], 'repair', attempt['id'])
        return
    used = {a['configuration_id'] for a in request['attempts']}
    alternative = next((c for c in request['pool'] if c not in used), None)
    if alternative:
        _new_attempt(request, alternative, 'fallback', attempt['id'])
    else:
        request.update(state='coordinator-required', reason_code='viable-alternatives-exhausted')


def replan(root, identifier, decision, packet, policy):
    """Attach one fresh route to an exhausted request without resetting its contract."""
    import pilot
    core.require(isinstance(decision, dict) and isinstance(decision.get('id'), str), 'invalid-decision')
    path = _path(root, identifier)
    with _lock(path.with_suffix('.lock')):
        request = _read(path, identifier)
        # A retry of the same fresh decision is a read, even after it has
        # scheduled the next attempt.  This also avoids appending duplicate
        # replan events after a coordinator retry.
        if decision['id'] == request['decision_id']:
            return request
        core.require(request['state'] == 'coordinator-required', 'request-not-replanable')
        core.require(not any(a['state'] in {'planned', 'launching', 'running', 'completed'} for a in request['attempts']),
                     'request-not-settled')
        policy = core.policy(policy)
        core.require(policy == pilot.load_policy(root) and core.digest(policy) == request['policy_hash'], 'policy-changed')
        core.require(decision == pilot.get_decision(root, decision['id']), 'decision-changed')
        core.require(decision.get('decision_policy_version') == core.DECISION_POLICY_VERSION, 'decision-policy-changed')
        core.require(not decision.get('synthetic') and decision.get('action') == 'route', 'decision-not-a-route')
        core.require(decision.get('task_id') == request['task_id'] and decision.get('group_id') == request['group_id'],
                     'replan-task-changed')
        core.require(task_contract_hash(packet) == request.get('task_contract_hash'), 'execution-inputs-changed')
        core.require(core.digest(packet) == decision.get('input_hash'), 'execution-inputs-changed')
        core.require(decision.get('policy_hash') == request['policy_hash'], 'policy-changed')
        core.require(set(request['acceptance_gates']) <= set(decision.get('acceptance_gates', [])),
                     'acceptance-contract-weakened')
        outcomes = pilot.load_records(root, 'outcomes')
        core.require(core.digest(outcomes) == decision.get('evidence_hash'), 'decision-evidence-changed')
        age = (dt.datetime.now(dt.timezone.utc) - core.timestamp(decision['created_at'])).total_seconds()
        core.require(0 <= age <= policy['capability_age_seconds'], 'decision-expired')
        prepared = core.prepare(packet, policy, outcomes)
        selected = decision.get('selected_configuration_id')
        eligible = {row['configuration_id'] for row in prepared['rows'] if row['eligible']}
        core.require(selected in eligible, 'candidate-no-longer-eligible')
        original = pilot.get_decision(root, request['decision_history'][0])
        if 'explicit-choice' in original.get('reason_codes', []):
            core.require(selected == original.get('selected_configuration_id'), 'explicit-choice-changed')
        pool = [configuration for configuration in dict.fromkeys(
            [selected, *decision.get('alternative_configuration_ids', [])]) if configuration in eligible]
        used = {attempt['configuration_id'] for attempt in request['attempts']}
        candidate = next((configuration for configuration in pool if configuration not in used), None)
        request['decision_history'].append(decision['id'])
        request['decision_id'] = decision['id']
        request['decision_policy_version'] = core.DECISION_POLICY_VERSION
        request['pool'] = pool
        request['contract_hash'] = contract_hash(packet)
        request['acceptance_gates'] = sorted(set(request['acceptance_gates']) | set(decision['acceptance_gates']))
        request['evidence_snapshot'] = _evidence_snapshot(outcomes)
        request['evidence_cutoff_at'] = core.now()
        event_id = 'replan-' + core.digest({'request': identifier, 'decision': decision['id']})[:24]
        request['events'].append({'id': event_id, 'type': 'replanned', 'attempt_id': None,
                                  'event_hash': core.digest({'decision_id': decision['id']}), 'created_at': core.now()})
        if candidate is None:
            request['reason_code'] = 'viable-alternatives-exhausted'
        else:
            limit = request['limits'].get('max_attempts')
            if limit and len(request['attempts']) >= limit:
                request['reason_code'] = 'attempt-limit'
            else:
                parent = request['attempts'][-1]['id'] if request['attempts'] else None
                _new_attempt(request, candidate, 'fallback', parent)
                request.pop('reason_code', None)
                request['state'] = 'in-progress'
        core.require(len(request['events']) <= 1000, 'workflow-event-limit')
        _write(path, request)
        return request


def event(root, identifier, value, *, packet=None):
    """Idempotent allowlisted native events; reviewed results come from the outcome ledger."""
    if isinstance(value, dict) and value.get('type') == 'artifact-corrected':
        core.label(value.get('attempt_id'))
        # Review publication and pre-review correction share the same lock order.
        lock = _path(root, identifier).with_suffix('.review-' + value['attempt_id'] + '.lock')
        with _lock(lock):
            attempt = _attempt(get(root, identifier, _check_elapsed=False), value['attempt_id'])
            outcome_id = 'out_' + core.digest({'decision': attempt['decision_id'],
                'configuration': attempt['configuration_id'], 'attempt': attempt['id']})[:24]
            with _lock(Path(root)/'outcomes'/(outcome_id+'.lock')):
                return _event(root, identifier, value, packet=packet)
    return _event(root, identifier, value, packet=packet)


def _event(root, identifier, value, *, packet=None):
    import pilot
    core.fields(value, {'id', 'type', 'attempt_id'}, {'run_id', 'configuration_id', 'checkout_hash', 'base_revision',
                'artifact_hash', 'previous_artifact_hash', 'outcome_id', 'reason_code', 'repairable', 'findings_hash', 'configuration_source'})
    for key in ('id', 'type', 'attempt_id'): core.label(value[key])
    path = _path(root, identifier)
    lock = path.with_suffix('.lock')
    with _lock(lock):
        r = get(root, identifier, _check_elapsed=False)
        # Expiry halts dispatch and recovery, but a host run already owned by
        # this request still needs a durable terminal record and review.
        if _expire(r):
            _write(path, r)
        previous = next((e for e in r['events'] if e['id'] == value['id']), None)
        if previous:
            core.require(previous['event_hash'] == core.digest(value), 'event-id-conflict')
            return r
        a = _attempt(r, value['attempt_id'])
        kind = value['type']
        if kind == 'launching':
            core.require(packet is not None, 'dispatch-packet-required')
            recheck(root, identifier, a['id'], packet, _check_elapsed=False)
            a['state'] = 'launching'  # Reserve before the native tool call; no blind resume dispatch.
        elif kind == 'dispatched':
            core.require(a['state'] == 'launching', 'attempt-not-launching')
            core.require(value.get('configuration_id') == a['configuration_id'], 'observed-configuration-mismatch')
            for key in ('run_id', 'base_revision'): core.label(value.get(key))
            _hash(value.get('checkout_hash'))
            core.require(not any(x.get('run_id') == value['run_id'] for x in r['attempts']), 'duplicate-native-run')
            source = value.get('configuration_source', 'host-accepted-controls')
            core.require(source in {'host-accepted-controls', 'host-reported'}, 'invalid-configuration-source')
            a.update(state='running', configuration_source=source, run_id=value['run_id'], base_revision=value['base_revision'], checkout_hash=value['checkout_hash'])
        elif kind == 'completed':
            core.require(a['state'] == 'running', 'attempt-not-running')
            _hash(value.get('artifact_hash'))
            a.update(state='completed', artifact_hash=value['artifact_hash'])
        elif kind == 'artifact-corrected':
            core.require(a['state'] == 'completed', 'artifact-already-reviewed-or-not-completed')
            core.require(not a.get('artifact_correction'), 'artifact-correction-exhausted')
            core.require(not any(o.get('request_id') == identifier and o.get('attempt_id') == a['id']
                                 for o in pilot.load_records(root, 'outcomes')), 'artifact-review-already-published')
            outcome_id = 'out_' + core.digest({'decision': a['decision_id'],
                'configuration': a['configuration_id'], 'attempt': a['id']})[:24]
            core.require(not (Path(root)/'outcomes'/(outcome_id+'.pending')).exists(), 'artifact-review-already-started')
            _hash(value.get('artifact_hash')); _hash(value.get('previous_artifact_hash'))
            core.require(value['previous_artifact_hash'] == a['artifact_hash'], 'artifact-correction-mismatch')
            core.require(value['artifact_hash'] != a['artifact_hash'], 'artifact-correction-unchanged')
            core.label(value.get('reason_code'))
            correction = {k: value[k] for k in ('previous_artifact_hash', 'artifact_hash', 'reason_code')}
            a.update(artifact_hash=value['artifact_hash'], artifact_correction=correction)
        elif kind == 'reviewed':
            core.require(a['state'] == 'completed', 'attempt-not-completed')
            outcome_id = value.get('outcome_id')
            core.require(isinstance(outcome_id, str) and re.fullmatch(r'out_[a-f0-9]{24}', outcome_id), 'invalid-outcome-id')
            outcome = pilot.read_json(Path(root)/'outcomes'/(outcome_id+'.json'))
            core.require(outcome.get('request_id') == identifier and outcome.get('attempt_id') == a['id'], 'outcome-attempt-mismatch')
            validate_observation(root, outcome)
            d = pilot.get_decision(root, a['decision_id'])
            required = {'decision_id', 'configuration_id', 'artifact_hash', 'reviewer_id', 'reviewer_kind', 'review_accepted',
                        'gates', 'scores', 'costs', 'latency_ms', 'request_id', 'attempt_id', 'attempt_kind', 'worker_id'}
            optional = {'prompt_version', 'reviewed_demands', 'critical_defects'}
            verified = core.assess_outcome({k: outcome[k] for k in required | optional if k in outcome}, d, pilot.load_policy(root))
            core.require(verified['id'] == outcome_id and verified['accepted'] == outcome['accepted'], 'outcome-changed')
            a.update(state='accepted' if verified['accepted'] else 'rejected', outcome_id=outcome_id,
                     scores=verified['scores'], costs=verified['costs'], critical_defects=verified['critical_defects'])
            if verified['accepted']:
                accepted = [x for x in r['attempts'] if x['state'] == 'accepted']
                def preference(row):
                    total = sum(c['usd'] for c in row['costs'].values() if c['usd'] is not None)
                    complete = all(c['usd'] is not None for c in row['costs'].values())
                    # Unknown cost is never treated as free; a tied known total wins.
                    return (-sum(row['scores'].values()), not complete, total if complete else 0,
                            r['attempts'].index(row))
                best = min(accepted, key=preference)
                r.update(state='accepted', accepted_attempt_id=best['id'])
        elif kind in {'execution-failed', 'cancel', 'launch-not-started'}:
            allowed = {'planned', 'launching', 'running', 'completed'} if kind == 'cancel' else {'running', 'launching'}
            core.require(a['state'] in allowed, 'invalid-attempt-transition')
            core.label(value.get('reason_code'))
            if kind == 'launch-not-started':
                core.require(a['state'] == 'launching', 'attempt-not-launching')
                # Explicit reconciliation only, after coordinator checked the native host.
                core.require(a.get('launch_reconciliations', 0) < 1, 'launch-reconciliation-exhausted')
                a.update(state='planned', reason_code=value['reason_code'],
                         launch_reconciliations=a.get('launch_reconciliations', 0) + 1)
            else:
                a.update(state='canceled' if kind == 'cancel' else 'failed', reason_code=value['reason_code'])
        else:
            raise core.PilotError('unknown-workflow-event')
        repairable = value.get('repairable', False)
        core.require(type(repairable) is bool, 'invalid-repairable')
        if repairable:
            _hash(value.get('findings_hash'))
            core.require(a['state'] in {'failed', 'rejected'}, 'repair-without-failure')
            a['findings_hash'] = value['findings_hash']
        if r['state'] == 'in-progress' and a['state'] in {'rejected', 'failed'}:
            _recover(r, a, repairable)
        if kind == 'cancel' and r['state'] == 'in-progress' and not any(
                row['state'] in {'planned', 'launching', 'running', 'completed'} for row in r['attempts']):
            r.update(state='canceled', reason_code=value['reason_code'])
        r['events'].append({'id': value['id'], 'type': kind, 'attempt_id': a['id'],
                            'event_hash': core.digest(value), 'created_at': core.now(),
                            **(a['artifact_correction'] if kind == 'artifact-corrected' else {})})
        core.require(len(r['events']) <= 1000, 'workflow-event-limit')
        _write(path, r)
        return r


def _hash(value):
    core.require(isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value), 'invalid-artifact-hash')


def report(request):
    attempts = request['attempts']
    primary = next(a for a in attempts if a['kind'] == 'initial')
    return {'id': request['id'], 'task_id': request['task_id'], 'decision_id': request['decision_id'],
            'state': request['state'], 'first_attempt_success': primary['state'] == 'accepted',
            'bakeoff_success': any(a['state'] == 'accepted' and a['kind'] in {'initial', 'comparison'} for a in attempts),
            'request_success': request['state'] == 'accepted', 'accepted_attempt_id': request['accepted_attempt_id'],
            'attempts': [{k: a[k] for k in ('id', 'configuration_id', 'kind', 'state', 'parent_attempt_id',
                'reason_code', 'outcome_id', 'artifact_hash') if k in a} for a in attempts],
            'recovery_attempts': sum(a['kind'] in {'repair', 'fallback'} and a['state'] != 'planned' for a in attempts)}
