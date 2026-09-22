#!/usr/bin/env python3
"""Offline, dated research priors and reproducible capability documentation.

No credentials, network, worker evidence, prices or permission changes.
Only reviewed, curated summaries belong in the index, never raw source pages.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import math
import re
from pathlib import Path
import sys
from urllib.parse import quote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot
import pilot_core as core

DEFAULT_INDEX = Path(__file__).resolve().parents[1] / 'assets/capability-index.json'
DEFAULT_DOC = Path(__file__).resolve().parents[1] / 'references/capability-index-data.md'
MAX_BYTES = 1024 * 1024
NOTICE = ('Research priors only: provider positioning and external evaluations do not '
          'establish native task success, security, availability or billed cost. '
          'Effort-specific capability is unknown unless explicitly evaluated. '
          'Reviewed local outcomes remain separate.')


def date(value):
    core.require(isinstance(value, str) and len(value) == 10, 'invalid-research-date')
    try:
        result = dt.date.fromisoformat(value)
    except ValueError:
        raise core.PilotError('invalid-research-date') from None
    core.require(result.isoformat() == value, 'invalid-research-date')
    return result


def text(value, limit=700):
    core.prose(value)
    core.require(len(value) <= limit and not any(ord(c) < 32 for c in value), 'invalid-research-text')


def metric_text(claim):
    metric = claim['metric']
    interval = (f"90% bootstrap interval {metric['ci_low']:g} to {metric['ci_high']:g}"
                if metric['ci_level'] is not None else 'confidence interval not reported')
    return (f"Epoch general ECI {metric['value']:g}; {interval}. Model-level composite across "
            "benchmark settings; not an effort-specific score or task-success probability.")


def validate(index):
    core.fields(index, {'schema', 'version', 'reviewed_on', 'review_after_days',
                        'evaluation_after_days', 'sources', 'claims'})
    core.require(index['schema'] == 'ultra-capability-index-v1', 'invalid-research-schema')
    core.label(index['version'])
    reviewed = date(index['reviewed_on'])
    for field in ('review_after_days', 'evaluation_after_days'):
        core.integer(index[field], 1)
        core.require(index[field] <= 3650, 'invalid-research-age-limit')
    core.require(isinstance(index['sources'], list) and 0 < len(index['sources']) <= 100,
                 'invalid-research-sources')
    sources = {}
    for source in index['sources']:
        core.fields(source, {'id', 'title', 'url', 'kind', 'checked_on', 'published_on',
                             'revision', 'use', 'limitations'},
                    {'license', 'attribution', 'retrieved_on'})
        core.label(source['id']); text(source['title'], 160); text(source['limitations'])
        core.require(source['id'] not in sources, 'duplicate-research-source')
        core.require(source['kind'] in {'provider', 'benchmark', 'composite'}, 'invalid-research-source-kind')
        core.require(source['use'] in {'curated-summary', 'reference-only'}, 'invalid-research-use')
        text(source['url'], 500)
        core.require(not any(c.isspace() or c in '<>"\\' for c in source['url']), 'invalid-research-url')
        url = urlsplit(source['url'])
        core.require(url.scheme == 'https' and url.hostname and not url.username and not url.password,
                     'invalid-research-url')
        try:
            url.port
        except ValueError:
            raise core.PilotError('invalid-research-url') from None
        checked = date(source['checked_on'])
        core.require(checked <= reviewed, 'research-check-after-review')
        if source['published_on'] is not None:
            core.require(date(source['published_on']) <= checked, 'research-publication-after-check')
        if source['revision'] is not None: text(source['revision'], 160)
        if source['kind'] == 'composite':
            core.require(set(source) >= {'license', 'attribution', 'retrieved_on'}, 'missing-research-attribution')
            core.require(source['license'] == 'CC-BY-4.0', 'unsupported-research-license')
            text(source['attribution'])
            core.require(date(source['retrieved_on']) <= checked, 'research-retrieval-after-check')
            core.require(isinstance(source['revision'], str) and re.fullmatch(r'sha256:[0-9a-f]{64}', source['revision']),
                         'missing-research-snapshot-hash')
        else:
            core.require(not set(source) & {'license', 'attribution', 'retrieved_on'}, 'invalid-research-source-fields')
        sources[source['id']] = source
    core.require(isinstance(index['claims'], list) and len(index['claims']) <= 2000, 'invalid-research-claims')
    identifiers = set()
    for claim in index['claims']:
        core.fields(claim, {'id', 'source_id', 'provider', 'model', 'effort', 'kind',
                           'summary', 'evaluated_on', 'benchmark', 'harness'}, {'metric'})
        for field in ('id', 'source_id', 'provider', 'model'): core.label(claim[field])
        core.require(claim['id'] not in identifiers, 'duplicate-research-claim')
        identifiers.add(claim['id'])
        source = sources.get(claim['source_id'])
        core.require(source is not None and source['use'] == 'curated-summary', 'research-source-not-usable')
        text(claim['summary'])
        core.require(claim['kind'] in {'provider-claim', 'benchmark-result', 'capability-prior'}, 'invalid-research-kind')
        core.require(('metric' in claim) == (claim['kind'] == 'capability-prior'), 'invalid-research-metric')
        if claim['effort'] is not None: core.label(claim['effort'])
        if claim['evaluated_on'] is not None:
            core.require(date(claim['evaluated_on']) <= date(source['checked_on']), 'research-evaluation-after-check')
        if claim['kind'] == 'capability-prior':
            core.require(source['kind'] == 'composite' and claim['effort'] is None
                         and claim['evaluated_on'] is None and claim['benchmark'] == 'Epoch general ECI'
                         and claim['harness'] is None, 'research-kind-mismatch')
            metric = claim['metric']
            core.fields(metric, {'value', 'ci_low', 'ci_high', 'ci_level', 'source_model', 'model_release_on',
                                 'source_organization', 'native_identity'})
            for field in ('value',):
                core.require(type(metric[field]) in (int, float) and math.isfinite(metric[field]), 'invalid-research-score')
            interval = [metric[k] for k in ('ci_low', 'ci_high', 'ci_level')]
            if any(v is not None for v in interval):
                core.require(all(type(v) in (int, float) and math.isfinite(v) for v in interval), 'invalid-research-interval')
                core.require(metric['ci_level'] == 0.90 and metric['ci_low'] <= metric['value'] <= metric['ci_high'],
                             'invalid-research-interval')
            text(metric['source_model'], 160)
            if metric['source_organization'] is not None: text(metric['source_organization'], 200)
            native = metric['native_identity']
            if native is not None:
                core.fields(native, {'provider', 'model'})
                core.require(native == {'provider': claim['provider'], 'model': claim['model']}, 'research-identity-mismatch')
            else:
                core.require(claim['provider'] == 'research' and claim['model'].startswith('epoch:'), 'research-identity-mismatch')
            if metric['model_release_on'] is not None:
                core.require(date(metric['model_release_on']) <= date(source['checked_on']), 'research-release-after-check')
            core.require(claim['summary'] == metric_text(claim), 'research-summary-metric-mismatch')
        elif claim['kind'] == 'benchmark-result':
            core.require(source['kind'] == 'benchmark', 'research-kind-mismatch')
            for field in ('benchmark', 'harness'): text(claim[field], 160)
        else:
            core.require(source['kind'] == 'provider' and claim['benchmark'] is None
                         and claim['harness'] is None and claim['evaluated_on'] is None,
                         'research-kind-mismatch')
    return index


def load(path=DEFAULT_INDEX):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    core.require(len(raw) <= MAX_BYTES, 'research-index-too-large')
    return validate(json.loads(raw))


def report(index, as_of=None):
    validate(index)
    today = date(as_of) if as_of else dt.datetime.now(dt.timezone.utc).date()
    core.require(date(index['reviewed_on']) <= today, 'research-review-in-future')
    sources = {s['id']: s for s in index['sources']}
    rows = []
    for claim in index['claims']:
        source = sources[claim['source_id']]
        check_age = (today - date(source['checked_on'])).days
        evaluation_age = ((today - date(claim['evaluated_on'])).days
                          if claim['evaluated_on'] else None)
        flags = []
        if check_age > index['review_after_days']: flags.append('source-review-due')
        if claim['kind'] == 'benchmark-result':
            if evaluation_age is None: flags.append('evaluation-date-unknown')
            elif evaluation_age > index['evaluation_after_days']: flags.append('old-evaluation')
            if claim['effort'] is None: flags.append('evaluated-effort-unknown')
        elif claim['kind'] == 'capability-prior':
            flags += ['model-level-prior', 'mixed-effort-settings', 'evaluation-date-unknown']
            if claim['metric']['native_identity'] is None: flags.append('native-id-unmapped')
            if claim['metric']['ci_level'] is None: flags.append('interval-unreported')
        else:
            flags.append('provider-claim-not-evaluation')
        rows.append({**claim, 'source': source, 'source_check_age_days': check_age,
                     'evaluation_age_days': evaluation_age, 'flags': flags})
    return {'schema': 'ultra-capability-report-v1', 'index_version': index['version'],
            'index_hash': core.digest(index), 'as_of': today.isoformat(), 'notice': NOTICE,
            'sources': index['sources'], 'claims': rows,
            'counts': {'claims': len(rows),
                       'provider_claims': sum(r['kind'] == 'provider-claim' for r in rows),
                       'benchmark_results': sum(r['kind'] == 'benchmark-result' for r in rows),
                       'capability_priors': sum(r['kind'] == 'capability-prior' for r in rows),
                       'native_mapped_priors': sum(r['kind'] == 'capability-prior' and r['metric']['native_identity'] is not None for r in rows),
                       'sources_review_due': sum((today - date(s['checked_on'])).days > index['review_after_days']
                                                 for s in sources.values())}}


def describe(index, provider, model, effort, *, as_of=None):
    """Exact model match; unspecified benchmark effort never matches a native effort.

    Stale research stays visibly labeled; it never blocks an otherwise eligible
    worker or creates a minimum-observation qualification requirement.
    """
    data = report(index, as_of)
    matches = [r for r in data['claims'] if r['provider'] == provider and r['model'] == model
               and (r['kind'] != 'capability-prior' or r['metric']['native_identity'] is not None)
               and (r['effort'] == effort or (r['kind'] in {'provider-claim', 'capability-prior'} and r['effort'] is None))]
    statements = []
    for row in matches:
        source = row['source']
        details = [row['kind'], 'source='+source['id'], 'checked='+source['checked_on'],
                   'evaluated='+str(row['evaluated_on'] or 'unknown'),
                   'effort='+str(row['effort'] or 'unspecified')]
        if row['benchmark']: details += ['benchmark='+row['benchmark'], 'harness='+str(row['harness'] or 'mixed/unspecified')]
        if row['kind'] == 'capability-prior':
            details += ['snapshot='+source['revision'], 'retrieved='+source['retrieved_on'],
                        'attribution=Epoch AI CC-BY-4.0 https://epoch.ai/eci']
        details += row['flags']
        statements.append('['+'; '.join(details)+'] '+row['summary'])
    if not statements: statements = ['No matching research for this exact model/effort; capability unknown.']
    result = ('Research index '+index['version']+' sha256:'+data['index_hash']+'. '+NOTICE+'\n'
              + '\n'.join(statements))
    core.prose(result)  # Reject overflow, never silently drop observations.
    return result


def render_markdown(data):
    def escape(value):
        return html.escape(str(value), quote=True).replace('|', '&#124;').replace('[', '&#91;').replace(']', '&#93;')
    lines = ['# Capability research index', '', f"As of {data['as_of']}; version {data['index_version']}.",
             '', data['notice'], '',
             '| Model | Research summary | Source checked | Evaluation date | Flags |',
             '| --- | --- | --- | --- | --- |']
    for row in data['claims']:
        display = row['metric']['source_model'] if row['kind'] == 'capability-prior' else row['provider']+'/'+row['model']
        lines.append('| '+' | '.join(escape(v) for v in [display, row['summary'],
                     row['source']['checked_on'], row['evaluated_on'] or 'Unknown / not an evaluation',
                     ', '.join(row['flags']) or 'none'])+' |')
    lines += ['', '## Sources', '']
    for source in data['sources']:
        safe_url = quote(source['url'], safe='/:#?&=.%+~@!$*,-_')
        lines += [f"- [{escape(source['title'])}]({safe_url}) ({source['use']}); checked {source['checked_on']}; "
                  f"published {source['published_on'] or 'unknown'}; revision {escape(source['revision'] or 'unversioned')}. "
                  + escape(source['limitations'])]
        if source.get('attribution'):
            lines += ['  '+escape(source['attribution'])+' License: '+source['license']+'.']
    return '\n'.join(lines)+'\n'


def render_html(data):
    esc = html.escape
    rows = ''.join('<tr>'+''.join('<td>'+esc(str(v))+'</td>' for v in [
        (r['metric']['source_model'] if r['kind'] == 'capability-prior' else r['model'])+' / '+(r['effort'] or 'effort unspecified'), r['summary'], r['source']['checked_on'], r['evaluated_on'] or 'Unknown',
        ', '.join(r['flags'])])+'</tr>' for r in data['claims'])
    sources = ''.join('<li><a href="'+esc(s['url'], quote=True)+'">'+esc(s['title'])+'</a>: '
                      +esc(f"{s['use']}; checked {s['checked_on']}; published {s['published_on'] or 'unknown'}; "
                           f"revision {s['revision'] or 'unversioned'}. "+s['limitations']+' '+s.get('attribution', ''))+'</li>' for s in data['sources'])
    priors = [r for r in data['claims'] if r['kind'] == 'capability-prior']
    overview = ''
    if priors:
        overview = ('<h2>Model catalog</h2><label for="model-filter">Filter by model or organization </label>'
                    '<input id="model-filter" type="search" placeholder="Claude, Gemini, GPT-4, Qwen…">'
                    '<p id="model-count">'+str(len(priors))+' models</p><div class="catalog"><table id="model-table">'
                    '<thead><tr><th>Model</th><th>Organization</th><th>General ECI</th><th>90% interval</th><th>Native mapping</th></tr></thead><tbody>')
        for row in sorted(priors, key=lambda r: (-r['metric']['value'], r['model'])):
            metric = row['metric']
            native = metric['native_identity']
            binding = native['provider']+'/'+native['model'] if native else 'Research only; map exact host ID'
            interval = f"{metric['ci_low']:g}–{metric['ci_high']:g}" if metric['ci_level'] is not None else 'Not reported'
            overview += ('<tr><td>'+esc(metric['source_model'])+'</td><td>'+esc(metric['source_organization'] or 'Unknown')
                         +f"</td><td>{metric['value']:g}</td><td>{interval}</td><td>"
                         +esc(binding)+'</td></tr>')
        overview += ('</tbody></table></div><p>Epoch AI, <a href="https://epoch.ai/eci">Epoch Capabilities Index</a>, '
                     '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. '
                     'Model-level research; not an effort-specific ranking. Intervals describe the index, not task success.</p>'
                     '<script>const filter=document.getElementById("model-filter");'
                     'const rows=[...document.querySelectorAll("#model-table tbody tr")];'
                     'filter.addEventListener("input",()=>{const q=filter.value.toLowerCase().trim();let n=0;'
                     'rows.forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(q);if(!r.hidden)n++;});'
                     'document.getElementById("model-count").textContent=n+" of "+rows.length+" models";});</script>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>Capability research index</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;'
            'padding:20px;color:#182330}table{border-collapse:collapse;width:100%}td,th{padding:12px;text-align:left;'
            'border-bottom:1px solid #ccd3dd}li{margin:12px 0}.catalog{max-height:560px;overflow:auto}'
            'thead{position:sticky;top:0;background:white}input{font:inherit;padding:8px}summary{cursor:pointer;margin-top:24px}'
            '</style><h1>Capability research index</h1><p>'
            +esc(f"{data['counts']['provider_claims']} provider claims · {data['counts']['capability_priors']} capability priors · "
                 f"{data['counts']['benchmark_results']} benchmark results · "
                 f"{data['counts']['sources_review_due']} sources due for review · As of {data['as_of']}")
            +'</p><p>'+esc(data['notice'])+'</p>'+overview+'<details><summary>Research details and sources</summary><table><tr><th>Model</th><th>Starting expectation</th>'
            '<th>Checked</th><th>Evaluated</th><th>Limits</th></tr>'+rows+'</table><h2>Sources</h2><ul>'+sources+'</ul></details></html>')


def main(argv=None):
    parser = pilot.SafeParser(description=__doc__)
    parser.add_argument('--index', type=Path, default=DEFAULT_INDEX)
    parser.add_argument('--as-of', help='UTC date; defaults to today for reports')
    parser.add_argument('--output-dir', type=Path, help='New report.json, report.html and report.md files')
    parser.add_argument('--write-docs', action='store_true', help='Regenerate bundled reference at index review date')
    parser.add_argument('--check', action='store_true', help='Check generated reference without a network request')
    args = parser.parse_args(argv)
    try:
        index = load(args.index)
        if args.write_docs or args.check:
            core.require(not args.output_dir and not args.as_of and not (args.write_docs and args.check), 'conflicting-options')
            generated = render_markdown(report(index, index['reviewed_on']))
            if args.check:
                core.require(DEFAULT_DOC.read_text(encoding='utf-8') == generated, 'research-docs-out-of-date')
            else:
                core.require(not DEFAULT_DOC.is_symlink(), 'invalid-output')
                DEFAULT_DOC.write_text(generated, encoding='utf-8')
            print(json.dumps({'checked': args.check, 'written': args.write_docs}))
            return 0
        data = report(index, args.as_of)
        if args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            paths = [args.output_dir / ('report.'+suffix) for suffix in ('json', 'html', 'md')]
            core.require(all(not p.exists() and not p.is_symlink() for p in paths), 'report-exists')
            pilot.write_new(paths[0], data)
            for path, rendered in zip(paths[1:], (render_html(data), render_markdown(data))):
                with path.open('x', encoding='utf-8') as stream: stream.write(rendered)
            print(json.dumps({'index_hash': data['index_hash'], 'as_of': data['as_of'], 'counts': data['counts']}))
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError):
        print('{"error":"capability-index-invalid"}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
