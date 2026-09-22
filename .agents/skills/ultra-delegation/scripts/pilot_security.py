"""Optional, artifact-bound Jev screening and independent finding disposition.

No scanners or native-worker execution. Detailed findings are local artifacts;
only allowlisted references and decisions enter the outcome ledger.
"""
from __future__ import annotations

import copy
from pathlib import Path
import re

import pilot_core as core
import pilot_questions as questions

BANDS = questions.SECURITY_THRESHOLDS


def bands(policy):
    value = policy.get('security_thresholds', BANDS)
    core.fields(value, set(BANDS))
    core.require(all(core.transport.number(v) for v in value.values()) and value['investigate'] < value['strong'], 'invalid-security-thresholds')
    return value


def _hash(value):
    core.require(isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value), 'invalid-security-hash')
    return value


def evaluate(packet, policy, enabled, *, live=False, call=None, key=None):
    import pilot
    result = {'mode': 'advisory' if enabled else 'off', 'status': 'not_checked',
              'reason_codes': [], 'question_version': questions.SECURITY_VERSION,
              'model': policy['model'], 'requirements': [], 'follow_up_required': False,
              'reviewed': False, 'disposition': 'not-required', 'findings': [], 'required_finding_ids': [],
              'excerpt_count': 0, **pilot.empty_usage()}
    if not enabled:
        return result
    result.update(status='unavailable', disposition='unavailable')
    if not policy['share_artifacts']:
        result['reason_codes'] = ['artifact-sharing-disabled']; return result
    if not live:
        result['reason_codes'] = ['live-not-requested']; return result
    if packet is None:
        result['reason_codes'] = ['security-input-missing']; return result
    try:
        payload = questions.security_payload(packet, policy['model'])
        core.transport.encoded_payload(payload)
        result.update(input_hash=core.digest(packet), question_hash=core.digest(payload['questions']),
                      coverage_hash=core.digest(packet['excerpts']), excerpt_count=len(packet['excerpts']))
        answers, usage, error = pilot.ask(payload, policy, call=call, key=key)
        result.update(usage)
        if error:
            result['reason_codes'] = [error]; return result
        thresholds = bands(policy)
        for i, req in enumerate(packet['requirements']):
            probability, sufficiency = answers['violation_'+str(i)]['noul'], answers['sufficient_'+str(i)]['noul']
            signal = ('insufficient-evidence' if sufficiency < thresholds['sufficient'] else
                      'strong-concern' if probability >= thresholds['strong'] else
                      'investigate' if probability > thresholds['investigate'] else 'no-concern')
            result['requirements'].append({'id': req['id'], 'mandatory': req['mandatory'],
                'violation_probability': probability, 'evidence_probability': sufficiency,
                'signal': signal, 'follow_up': signal != 'no-concern'})
        result['follow_up_required'] = any(r['follow_up'] for r in result['requirements'])
        result.update(status='indeterminate' if result['follow_up_required'] else 'pass',
                      disposition='pending' if result['follow_up_required'] else 'not-required',
                      reason_codes=['security-follow-up-required' if result['follow_up_required'] else 'no-concern-detected-in-assessed-evidence'])
    except Exception:
        result.update(status='unavailable', disposition='unavailable', reason_codes=['invalid-security-input'])
    return result


def binding(raw, decision, policy):
    _hash(raw['artifact_hash'])
    return {'decision_id': decision['id'], 'configuration_id': raw['configuration_id'],
            'artifact_hash': raw['artifact_hash'], 'request_id': raw.get('request_id'),
            'attempt_id': raw.get('attempt_id'), 'boundary_hash': decision.get('boundary_hash'),
            'question_version': questions.SECURITY_VERSION, 'model': policy['model'],
            'policy_hash': core.digest({k: policy.get(k) for k in ('share_artifacts', 'security_check', 'security_thresholds', 'model')})}


def _directory(root, name):
    core.require(not Path(root).is_symlink(), 'symlink-security-store')
    path = Path(root)/name
    core.require(not path.is_symlink(), 'symlink-security-store')
    path.mkdir(exist_ok=True)
    return path


def _read(path):
    import pilot
    core.require(not path.is_symlink(), 'symlink-security-store')
    record = pilot.read_json(path)
    core.require(record.get('integrity') == core.digest({k:v for k,v in record.items() if k != 'integrity'}), 'security-assessment-changed')
    return record


def prepare(root, raw, decision, policy, packet=None, *, enabled=False, live=False, dry_run=False, call=None, key=None):
    """Reserve before paying; interrupted requests resume as unavailable, never repay."""
    import pilot
    import pilot_workflow as workflow
    bound = binding(raw, decision, policy)
    identifier = 'sec_'+core.digest(bound)[:24]
    if not enabled:
        packet = None
    if packet is not None:
        payload = questions.security_payload(packet, policy['model'])
        core.transport.encoded_payload(payload)
        core.require(core.digest(packet['boundaries']) == decision.get('boundary_hash'), 'security-boundaries-changed')
        expected = decision.get('security_requirements', [])
        actual = [{'id': r['id'], 'requirement_hash': core.digest(r['requirement']), 'mandatory': r['mandatory']} for r in packet['requirements']]
        core.require(actual == expected, 'security-requirements-changed')
    else:
        payload = None
    if dry_run:
        core.require(payload is not None, 'security-input-missing')
        return {'dry_run': True, 'assessment_id': identifier, 'binding': bound, 'payload': payload,
                'artifact_sharing_enabled': policy['share_artifacts']}
    directory = _directory(root, 'security-assessments')
    path = directory/(identifier+'.json')
    with workflow._lock(path.with_suffix('.lock')):
        if path.exists():
            saved = _read(path)
            core.require(saved['binding'] == bound, 'security-assessment-changed')
            if packet is not None:
                core.require(saved.get('input_hash') in (None, core.digest(packet)), 'security-inputs-changed')
            return saved
        # Changing evaluator settings cannot erase a known concern on this artifact.
        identity_keys = ('decision_id','configuration_id','artifact_hash','request_id','attempt_id','boundary_hash')
        prior_concerns = []
        for other in directory.glob('sec_*.json'):
            previous = _read(other)
            if all(previous['binding'].get(k) == bound.get(k) for k in identity_keys) and previous.get('follow_up_required'):
                prior_concerns.append(previous)
        core.require(enabled or not prior_concerns, 'security-settings-changed-review-required')
        pending = path.with_suffix('.pending')
        core.require(not pending.is_symlink(), 'symlink-security-store')
        interrupted = pending.exists()
        if not enabled and not interrupted:
            result = evaluate(None, policy, False)
            result.update(assessment_id=identifier, artifact_hash=raw['artifact_hash'], boundary_hash=decision.get('boundary_hash'))
            if decision.get('security_sensitive'):
                result.update(follow_up_required=True, disposition='pending')
            return result
        if not interrupted:
            pilot.write_new(pending, {'binding': bound, 'input_hash': core.digest(packet) if packet else None})
        if interrupted:
            marker = pilot.read_json(pending)
            core.require(marker['binding'] == bound, 'security-assessment-changed')
            if packet is not None:
                core.require(marker.get('input_hash') == core.digest(packet), 'security-inputs-changed')
            result = evaluate(None, policy, True)
            result.update(status='unavailable', disposition='unavailable', reason_codes=['interrupted-evaluation-not-repeated'], cost_usd=None, cost_kind='unknown')
        elif not decision.get('security_requirements') and enabled:
            result = evaluate(None, policy, False)
            result.update(mode='advisory', status='pass', reason_codes=['no-applicable-security-requirements'])
        else:
            result = evaluate(packet, policy, enabled, live=live, call=call, key=key)
        result.update(schema='ultra-pilot-security-v1', assessment_id=identifier, binding=bound,
                      artifact_hash=raw['artifact_hash'], boundary_hash=decision.get('boundary_hash'), created_at=core.now())
        if packet is not None: result['input_hash'] = core.digest(packet)
        if prior_concerns:
            flagged = {r['id'] for old in prior_concerns for r in old['requirements'] if r['follow_up']}
            flagged.update(r for old in prior_concerns for r in old.get('required_finding_ids', []))
            result['required_finding_ids'] = sorted(flagged)
            for requirement in result['requirements']:
                if requirement['id'] in flagged: requirement['follow_up'] = True
            result['reason_codes'].append('prior-artifact-concern-requires-review')
        if decision.get('security_sensitive') or prior_concerns:
            result.update(follow_up_required=True, disposition='pending')
        result['integrity'] = core.digest(result)
        pilot.write_new(path, result)
        pending.unlink()
        return result


def validate_review(review, raw, decision):
    """Validate the metadata-only reviewer verdict; never infer severity from Noul."""
    core.fields(review, {'assessment_id', 'artifact_hash', 'reviewer_id', 'reviewer_kind', 'reviewed_requirements', 'findings', 'details_hash', 'details_ref'})
    core.label(review['assessment_id']); _hash(review['artifact_hash']); _hash(review['details_hash'])
    core.require(review['artifact_hash'] == raw['artifact_hash'], 'security-artifact-changed')
    core.label(review['reviewer_id'])
    core.require(review['reviewer_id'] != raw.get('worker_id'), 'worker-cannot-review-self')
    core.require(review['reviewer_kind'] in {'human', 'frontier'}, 'invalid-security-reviewer')
    core.require(review['details_ref'] == 'security-findings/'+review['details_hash']+'.json', 'invalid-security-details-ref')
    core.labels(review['reviewed_requirements'])
    reqs = {r['id']:r for r in decision.get('security_requirements', [])}
    core.require(set(review['reviewed_requirements']) <= set(reqs), 'unknown-security-requirement')
    core.require(isinstance(review['findings'], list) and len(review['findings']) <= 48, 'invalid-security-findings')
    ids = set(); blocked = False
    for finding in review['findings']:
        core.fields(finding, {'id', 'requirement_id', 'disposition', 'severity', 'scope', 'coordinator_disposition'})
        core.label(finding['id']); core.require(finding['id'] not in ids, 'duplicate-security-finding'); ids.add(finding['id'])
        req = finding['requirement_id']
        core.require(req is None or req in reqs, 'unknown-security-requirement')
        core.require(finding['disposition'] in {'confirmed', 'dismissed', 'unresolved'}, 'invalid-security-disposition')
        core.require(finding['severity'] in {'critical','high','medium','low','informational'}, 'invalid-security-severity')
        core.require(finding['scope'] in {'delivered','pre-existing'}, 'invalid-security-scope')
        core.require(finding['scope'] != 'pre-existing' or req is None, 'task-obligation-not-unrelated')
        cd = finding['coordinator_disposition']
        core.require(cd in {None, 'accept-with-limitation', 'handoff'}, 'invalid-coordinator-disposition')
        if finding['disposition'] == 'unresolved':
            core.require(cd is not None, 'unresolved-security-finding')
            blocked |= cd == 'handoff'
        else:
            core.require(cd is None, 'unexpected-coordinator-disposition')
        if finding['scope'] == 'delivered' and finding['disposition'] == 'confirmed':
            blocked |= finding['severity'] == 'critical' or (req is not None and reqs[req]['mandatory'])
    return not blocked


def publish_findings(root, document, raw, decision, assessment):
    import pilot
    core.fields(document, {'assessment_id','artifact_hash','reviewer_id','reviewer_kind','reviewed_requirements','findings'})
    core.require(document['assessment_id'] == assessment['assessment_id'], 'security-assessment-mismatch')
    core.require(isinstance(document['findings'], list) and len(document['findings']) <= 48, 'invalid-security-findings')
    metadata = copy.deepcopy(document)
    metadata['findings'] = []
    for entry in document['findings']:
        prose_keys = {'location','evidence','consequence','correction'}
        core.require(isinstance(entry, dict), 'invalid-security-finding')
        for name in prose_keys: core.prose(entry.get(name))
        core.fields(entry, {'id','requirement_id','disposition','severity','scope','coordinator_disposition'} | prose_keys)
        metadata['findings'].append({k:v for k,v in entry.items() if k not in prose_keys})
    digest = core.digest(document)
    metadata.update(details_hash=digest, details_ref='security-findings/'+digest+'.json')
    validate_review(metadata, raw, decision)
    flagged = {r['id'] for r in assessment['requirements'] if r['follow_up']} | set(assessment.get('required_finding_ids', []))
    if decision.get('security_sensitive') or 'prior-artifact-concern-requires-review' in assessment['reason_codes']:
        core.require(set(metadata['reviewed_requirements']) == {r['id'] for r in decision.get('security_requirements', [])}, 'security-follow-up-incomplete')
    addressed = {f['requirement_id'] for f in metadata['findings']}
    core.require(flagged <= set(metadata['reviewed_requirements']) & addressed, 'security-follow-up-incomplete')
    directory = _directory(root, 'security-findings');path=directory/(digest+'.json')
    if path.exists():
        core.require(not path.is_symlink() and core.digest(pilot.read_json(path)) == digest, 'security-findings-changed')
    else: pilot.write_new(path, document)
    return metadata


def complete(root, raw, decision, policy, packet=None, findings=None, *, enabled=False, live=False, call=None, key=None):
    assessment = prepare(root, raw, decision, policy, packet, enabled=enabled, live=live, call=call, key=key)
    result = {k:copy.deepcopy(v) for k,v in assessment.items() if k not in {'integrity', 'binding', 'schema', 'created_at'}}
    metadata = raw.get('security_review')
    if findings is not None:
        supplied = publish_findings(root, findings, raw, decision, assessment)
        core.require(metadata is None or metadata == supplied, 'security-review-changed')
        metadata = supplied
    if metadata is not None:
        import pilot
        validate_review(metadata, raw, decision)
        core.require(metadata['assessment_id'] == assessment['assessment_id'], 'security-assessment-mismatch')
        core.require(not (Path(root)/'security-findings').is_symlink(), 'symlink-security-store')
        path = Path(root)/metadata['details_ref']
        core.require(not path.is_symlink() and core.digest(pilot.read_json(path)) == metadata['details_hash'], 'security-findings-changed')
        # Revalidate coverage even when a saved metadata reference is submitted.
        publish_findings(root, pilot.read_json(path), raw, decision, assessment)
        result.update(reviewed=True, disposition='handoff' if any(f['coordinator_disposition']=='handoff' for f in metadata['findings']) else 'completed',
                      findings=metadata['findings'], details_hash=metadata['details_hash'], details_ref=metadata['details_ref'])
    core.require(not result['follow_up_required'] or metadata is not None, 'security-follow-up-required')
    return result, metadata


def workflow_security(root, request_id, attempt_id, packet=None, *, live=False, dry_run=False, call=None, key=None):
    import pilot
    import pilot_workflow as workflow
    request = workflow.get(root, request_id);attempt = workflow._attempt(request, attempt_id)
    core.require(attempt['state'] == 'completed', 'attempt-not-completed')
    decision = pilot.get_decision(root, attempt['decision_id'])
    raw = {**{k:attempt[k] for k in ('configuration_id','artifact_hash')}, 'request_id':request_id, 'attempt_id':attempt_id}
    result = prepare(root, raw, decision, pilot.load_policy(root), packet, enabled=True, live=live, dry_run=dry_run, call=call, key=key)
    if not dry_run:
        result = copy.deepcopy(result)
        result['next_step'] = 'independent-security-review' if result['follow_up_required'] else 'workflow-review'
        result['review_template'] = {'assessment_id':result['assessment_id'],'artifact_hash':raw['artifact_hash'], 'reviewer_id':None, 'reviewer_kind':'frontier',
            'reviewed_requirements':[], 'findings':[]}
    return result
