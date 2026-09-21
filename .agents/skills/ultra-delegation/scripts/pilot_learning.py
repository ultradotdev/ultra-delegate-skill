"""Explicit metadata-only evidence audit, export, import and retraction."""
from __future__ import annotations

import copy
from pathlib import Path
import re
import pilot_core as core


def retractions(root):
    import pilot
    rows = []
    for path in sorted((Path(root)/'retractions').glob('*.json')):
        row = pilot.read_json(path)
        core.fields(row, {'outcome_id', 'reason_code', 'created_at'})
        core.require(path.stem == row['outcome_id'], 'invalid-retraction')
        core.label(row['reason_code']); core.timestamp(row['created_at'])
        rows.append(row)
    return rows


def retract(root, identifier, reason):
    import pilot
    core.require(isinstance(identifier, str) and re.fullmatch(r'out_[a-f0-9]{24}', identifier), 'invalid-outcome-id')
    core.label(reason)
    core.require((Path(root)/'outcomes'/(identifier+'.json')).is_file(), 'unknown-outcome')
    directory = Path(root)/'retractions'; directory.mkdir(exist_ok=True)
    row = {'outcome_id': identifier, 'reason_code': reason, 'created_at': core.now()}
    pilot.write_new(directory/(identifier+'.json'), row)
    return row


FIELDS = {'id', 'schema', 'created_at', 'configuration_id', 'scope_id', 'operation', 'risk', 'work_kind',
          'complexity', 'group_id', 'synthetic', 'accepted', 'gates', 'scores', 'costs', 'reviewed_demands',
          'critical_defects', 'reviewer_kind', 'artifact_hash', 'latency_ms', 'observation_origin',
          'observation_hash', 'provenance'}
OBSERVATION_FIELDS = {'created_at', 'configuration_id', 'scope_id', 'operation', 'risk', 'work_kind',
                      'complexity', 'group_id', 'synthetic', 'accepted', 'gates', 'scores', 'costs',
                      'reviewed_demands', 'critical_defects', 'reviewer_kind', 'artifact_hash', 'latency_ms'}
PROVENANCE = {'local-reviewed', 'imported-unverified'}


def _observation_hash(row):
    """Stable identity for the observation facts, excluding local ledger IDs."""
    return core.digest({key: row[key] for key in sorted(OBSERVATION_FIELDS) if key in row})


def _origin(row):
    origin = row.get('observation_origin', row.get('id'))
    core.label(origin)
    return origin


def export(root):
    import pilot
    rows = [{k: copy.deepcopy(o[k]) for k in FIELDS if k in o} for o in pilot.load_records(root, 'outcomes')]
    # Strip arbitrary extra nested metadata as well as source-specific reviewer IDs.
    for o in rows:
        o['gates'] = [{k: g[k] for k in ('id', 'mandatory', 'passed')} for g in o['gates']]
        o['scores'] = {k: o['scores'][k] for k in core.DIMENSIONS}
        o['costs'] = {k: {f: o['costs'][k][f] for f in ('usd', 'kind')} for k in core.COST_COMPONENTS}
        o['observation_origin'] = _origin(o)
        # Preserve the unverified source fingerprint across policy-specific local
        # re-evaluation.  A target may recompute ``accepted`` under stricter
        # floors, but that does not create a second source observation.
        o['observation_hash'] = o.get('observation_hash', _observation_hash(o))
        core.require(isinstance(o['observation_hash'], str) and re.fullmatch(r'[a-f0-9]{64}', o['observation_hash']), 'invalid-learning-record')
        # An import never becomes local independent review merely by being
        # exported again from another project.
        o['provenance'] = o.get('provenance', 'local-reviewed')
        core.require(o['provenance'] in PROVENANCE, 'invalid-learning-provenance')
    body = {'schema': 'ultra-pilot-learning-v1', 'outcomes': rows}
    return {**body, 'content_hash': core.digest(body)}


def import_bundle(root, bundle):
    import pilot
    core.fields(bundle, {'schema', 'outcomes', 'content_hash'})
    body = {k: bundle[k] for k in ('schema', 'outcomes')}
    core.require(bundle['schema'] == 'ultra-pilot-learning-v1' and core.digest(body) == bundle['content_hash'], 'invalid-learning-bundle')
    core.require(isinstance(bundle['outcomes'], list) and len(bundle['outcomes']) <= 10000, 'invalid-learning-bundle')
    values = []
    policy = pilot.load_policy(root)
    for row in bundle['outcomes']:
        core.require(isinstance(row, dict) and set(row) <= FIELDS, 'invalid-learning-record')
        for k in ('configuration_id', 'scope_id', 'operation', 'group_id'): core.label(row[k])
        core.timestamp(row['created_at'])
        core.require(type(row['synthetic']) is bool and type(row['accepted']) is bool, 'invalid-learning-record')
        core.require(row['risk'] in {'low','medium','high'} and row['work_kind'] in core.KINDS and row['complexity'] in {'routine','complex'}, 'invalid-learning-record')
        origin = _origin(row)
        observation_hash = row.get('observation_hash', _observation_hash(row))
        core.require(isinstance(observation_hash, str) and re.fullmatch(r'[a-f0-9]{64}', observation_hash), 'invalid-learning-record')
        provenance = row.get('provenance', 'local-reviewed')
        core.require(provenance in PROVENANCE, 'invalid-learning-provenance')
        identity = core.digest({'origin': origin, 'observation_hash': observation_hash})[:24]
        decision = {'id':'import_'+identity, 'task_id':'import_'+identity, 'group_id':row['group_id'],
                    **{k: row[k] for k in ('scope_id','operation','risk','work_kind','complexity','synthetic')},
                    'candidates':[{'configuration_id':row['configuration_id'], 'eligible':True}],
                    'acceptance_gates':[g['id'] for g in row['gates'] if g['mandatory']]}
        raw = {k: row[k] for k in ('configuration_id','artifact_hash','reviewer_kind','gates','scores','costs','latency_ms')}
        raw.update(decision_id=decision['id'], reviewer_id='imported-reviewer', review_accepted=row['accepted'],
                   reviewed_demands=row.get('reviewed_demands', []), critical_defects=row.get('critical_defects', []))
        value = core.assess_outcome(raw, decision, policy)
        value.update(id='out_'+identity, created_at=row['created_at'], observation_origin=origin,
                     observation_hash=observation_hash, provenance='imported-unverified', source_hash=bundle['content_hash'])
        values.append(value)
    # A local observation keeps the native outcome ID, while an imported copy
    # uses the portable ``origin`` + facts identity.  On a round trip the
    # portable ID therefore differs from the original local ID.  Index all
    # ledger records (including retracted ones) by their portable identity so
    # returning evidence cannot create a second record or change the local
    # review that produced it.
    existing = {}
    for record in pilot.load_records(root, 'outcomes', include_retracted=True):
        key = (_origin(record), record.get('observation_hash', _observation_hash(record)))
        existing[key] = record

    imported = 0
    # Origin is the observation identity; a caller-supplied fingerprint is not
    # authority to mint another observation with that same origin. Validate the
    # whole batch before writes, including conflicts with retracted records.
    origin_hashes = {origin: fingerprint for origin, fingerprint in existing}
    for value in values:
        origin, fingerprint = value['observation_origin'], value['observation_hash']
        core.require(origin not in origin_hashes or origin_hashes[origin] == fingerprint,
                     'learning-origin-conflict')
        origin_hashes[origin] = fingerprint
    for value in values:
        identity_key = (value['observation_origin'], value['observation_hash'])
        if identity_key in existing:
            continue
        path = Path(root)/'outcomes'/(value['id']+'.json')
        if path.exists():
            existing_record = pilot.read_json(path)
            core.require(existing_record.get('observation_origin') == value['observation_origin']
                         and existing_record.get('observation_hash') == value['observation_hash'], 'learning-origin-conflict')
        else:
            pilot.write_new(path, value); imported += 1
        existing[identity_key] = value
    return {'imported':imported, 'already_present':len(values)-imported, 'provenance':'imported-unverified'}
