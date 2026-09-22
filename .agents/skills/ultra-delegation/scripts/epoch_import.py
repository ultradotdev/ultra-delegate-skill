#!/usr/bin/env python3
"""Import an explicitly downloaded Epoch general ECI CSV into a new offline index.

No network or credentials. Import every scored model as research; only exact,
reviewed identity mappings enter native routing. Missing rows remain unknown.
"""
from __future__ import annotations

import copy
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import capability_index as research
import pilot
import pilot_core as core

URL = 'https://epoch.ai/data/eci_scores.csv'
SOURCE_ID = 'epoch-general-eci'
# Explicit correspondence, not a normalization heuristic. Pro/Instant are distinct.
MODEL_MAP = {'GPT-6 Astra': 'gpt-6-astra', 'GPT-6 Sol': 'gpt-6-sol',
             'GPT-6 Luna': 'gpt-6-luna', 'GPT-5.6 Sol': 'gpt-5.6-sol',
             'GPT-5.6 Terra': 'gpt-5.6-terra', 'GPT-5.6 Luna': 'gpt-5.6-luna',
             'GPT-5.5': 'gpt-5.5'}
REQUIRED = {'Model', 'Organization', 'eci', 'eci_ci_low', 'eci_ci_high', 'date'}


def import_scores(index, raw, retrieved_on, version, mappings=()):
    research.validate(index)
    retrieved = research.date(retrieved_on)
    core.require(retrieved <= dt.datetime.now(dt.timezone.utc).date(), 'future-epoch-retrieval')
    core.require(retrieved >= research.date(index['reviewed_on']), 'epoch-snapshot-before-index-review')
    core.label(version)
    core.require(version != index['version'], 'new-index-version-required')
    core.require(isinstance(raw, bytes) and 0 < len(raw) <= research.MAX_BYTES, 'epoch-export-too-large')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
    core.require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames))
                 and REQUIRED <= set(reader.fieldnames), 'invalid-epoch-columns')
    core.require(isinstance(mappings, (list, tuple)) and len(mappings) <= 1000, 'invalid-epoch-mappings')
    bindings = {('OpenAI', name): {'provider': 'openai', 'model': model} for name, model in MODEL_MAP.items()}
    for mapping in mappings:
        core.fields(mapping, {'source_model', 'source_organization', 'provider', 'model'})
        research.text(mapping['source_model'], 160); research.text(mapping['source_organization'], 200)
        core.label(mapping['provider']); core.label(mapping['model'])
        identity = (mapping['source_organization'], mapping['source_model'])
        target = {'provider': mapping['provider'], 'model': mapping['model']}
        core.require(identity not in bindings and target not in bindings.values(), 'ambiguous-epoch-mapping')
        bindings[identity] = target
    claims, seen = [], set()
    for row in reader:
        core.require(None not in row and all(v is not None for v in row.values()), 'invalid-epoch-row')
        name = row['Model']
        research.text(name, 160)
        organization = row['Organization'] or None
        if organization is not None: research.text(organization, 200)
        identity = (organization, name)
        core.require(identity not in seen, 'ambiguous-epoch-model')
        core.require(name not in MODEL_MAP or organization == 'OpenAI', 'ambiguous-epoch-model')
        seen.add(identity)
        # No zero-filled scores or fabricated intervals when the export lacks data.
        if not row['eci'].strip(): continue
        has_low, has_high = bool(row['eci_ci_low'].strip()), bool(row['eci_ci_high'].strip())
        core.require(has_low == has_high, 'incomplete-epoch-interval')
        metric = {'value': float(row['eci']), 'ci_low': float(row['eci_ci_low']) if has_low else None,
                  'ci_high': float(row['eci_ci_high']) if has_high else None, 'ci_level': 0.90 if has_low else None,
                  'source_model': name, 'source_organization': organization,
                  'model_release_on': row['date'] or None, 'native_identity': bindings.get(identity)}
        native = metric['native_identity']
        research_id = 'epoch:'+core.digest([organization, name])[:24]
        claim = {'id': 'epoch-eci-'+research_id, 'source_id': SOURCE_ID,
                 'provider': native['provider'] if native else 'research',
                 'model': native['model'] if native else research_id, 'effort': None,
                 'kind': 'capability-prior', 'evaluated_on': None,
                 'benchmark': 'Epoch general ECI', 'harness': None, 'metric': metric}
        claim['summary'] = research.metric_text(claim)
        claims.append(claim)
    core.require(claims, 'no-matching-epoch-scores')
    updated = copy.deepcopy(index)
    updated.update(version=version, reviewed_on=retrieved_on)
    updated['sources'] = [s for s in updated['sources'] if s['id'] != SOURCE_ID]
    updated['sources'].append({
        'id': SOURCE_ID, 'title': 'Epoch AI: Epoch Capabilities Index (model catalog)',
        'url': URL, 'kind': 'composite', 'checked_on': retrieved_on, 'published_on': None,
        'retrieved_on': retrieved_on, 'revision': 'sha256:'+hashlib.sha256(raw).hexdigest(),
        'use': 'curated-summary', 'license': 'CC-BY-4.0',
        'attribution': 'Epoch AI, Epoch Capabilities Index, https://epoch.ai/eci. '
                       'CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). '
                       'Retrieved '+retrieved_on+'. Scored rows normalized; explicit native IDs mapped; summaries generated.',
        'limitations': 'General ECI is a jointly fitted composite, not task-success probability or a native effort score. '
                        '90% bootstrap intervals describe index uncertainty. CSV date is model release, not evaluation date. '
                        'Underlying evaluation dates are unknown here. Scores can shift when the dataset is refitted. '
                        'Methodology: https://epoch.ai/data/eci-documentation/methodology. '
                        'SWE/Cyber ECI and third-party benchmark rows are not imported.',
    })
    updated['claims'] = [c for c in updated['claims'] if c['source_id'] != SOURCE_ID]
    updated['claims'].extend(sorted(claims, key=lambda c: c['model']))
    research.validate(updated)
    return updated


def main(argv=None):
    parser = pilot.SafeParser(description=__doc__)
    parser.add_argument('--scores', type=Path, required=True, help='Official public eci_scores.csv snapshot')
    parser.add_argument('--index', type=Path, default=research.DEFAULT_INDEX)
    parser.add_argument('--retrieved-on', required=True, help='Actual UTC retrieval date, YYYY-MM-DD')
    parser.add_argument('--version', required=True, help='New reviewed index version')
    parser.add_argument('--mappings', type=Path, help='Additional reviewed exact organization/name to native provider/model mappings')
    parser.add_argument('--output', type=Path, required=True, help='New file; never overwrites the current index')
    args = parser.parse_args(argv)
    try:
        with args.scores.open('rb') as stream: raw = stream.read(research.MAX_BYTES+1)
        mappings = pilot.read_json(args.mappings) if args.mappings else ()
        updated = import_scores(research.load(args.index), raw, args.retrieved_on, args.version, mappings)
        # Check the artifact bound used by the consumer before writing anything.
        encoded = json.dumps(updated, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)+'\n'
        core.require(len(encoded.encode('utf-8')) <= research.MAX_BYTES, 'research-index-too-large')
        pilot.write_new(args.output, updated)
        catalog = [c for c in updated['claims'] if c['source_id'] == SOURCE_ID]
        imported = [c['model'] for c in catalog if c['metric']['native_identity'] is not None]
        print(json.dumps({'catalog_models': len(catalog), 'native_mapped_models': imported,
                          'missing_default_mappings': sorted(set(MODEL_MAP.values())-set(imported)),
                          'index_hash': core.digest(updated), 'network_requests': 0}))
        return 0
    except (ValueError, OSError, KeyError, TypeError, csv.Error):
        print('{"error":"epoch-import-invalid"}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
