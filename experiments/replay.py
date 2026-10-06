#!/usr/bin/env python3
"""Replay routing rules against the calibration matrix, offline once Jev answers are cached.

  replay.py gonogo --host codex        # M3 probe: separation, cost gap, AUC of Jev's pass answers
  replay.py report --host codex        # M5: every rule, leave-one-out, bootstrap interval

Escalation follows the public check; quality is the hidden check. Expected values
use per-cell pass rates, so two runs per cell give 0, 0.5 or 1 per rung.
Objective: total cost per hidden-correct result, summed over fixtures.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / '.agents/skills/ultra-delegation/scripts'))
import ladder  # noqa: E402

RESULTS = HERE / 'results'
CONFIG = json.loads((HERE.parent / '.agents/skills/ultra-delegation/assets/tiers.json').read_text())
CUTOFFS = [round(0.05 * i, 2) for i in range(1, 20)]


def load(host):
    cells = [json.loads(l) for l in (RESULTS / f'{host}-cells.jsonl').read_text().splitlines() if l.strip()]
    cells = [c for c in cells if c['status'] != 'infra_error' and not c.get('leak')]
    jev = json.loads((RESULTS / f'{host}-jev-cold.json').read_text())
    return cells, jev


def stats(cells, rungs, proxy):
    """Per fixture and rung: public pass rate, hidden-given-public rate, mean cost and seconds."""
    out = {}
    for c in cells:
        out.setdefault(c['fixture'], {}).setdefault(c['rung'], []).append(c)
    proxy_cells = [c for c in cells if c['rung'] == proxy['id']]
    proxy_cost = sum(c['cost_usd'] or 0 for c in proxy_cells) / len(proxy_cells) if proxy_cells else None
    table = {}
    for fid, by_rung in out.items():
        row = []
        for r in [*rungs, proxy]:
            runs = by_rung.get(r['id'], [])
            if not runs:
                row.append(None if r is not proxy else {'pub': 1.0, 'q': 1.0, 'cost': proxy_cost, 'sec': None})
                continue
            pub = sum(x['public_pass'] for x in runs) / len(runs)
            hid_pub = [x['hidden_pass'] for x in runs if x['public_pass']]
            row.append({'pub': pub if r is not proxy else 1.0, 'q': sum(hid_pub) / len(hid_pub) if hid_pub else 0.0,
                        'hidden': sum(x['hidden_pass'] for x in runs) / len(runs),
                        'cost': sum(x['cost_usd'] or 0 for x in runs) / len(runs),
                        'sec': sum(x['seconds'] for x in runs) / len(runs)})
        table[fid] = row
    return table


def simulate(row, start):
    """Expected cost, seconds, hidden quality and coordinator hand-off probability from `start`."""
    reach, cost, sec, quality, slip = 1.0, 0.0, 0.0, 0.0, 0.0
    workers = row[:-1]
    for cell in workers[start:]:
        if cell is None:
            return None
        cost += reach * cell['cost']
        sec += reach * cell['sec']
        quality += reach * cell['pub'] * cell['q']
        slip += reach * cell['pub'] * (1 - cell['q'])
        reach *= 1 - cell['pub']
    coord = row[-1]
    cost += reach * (coord['cost'] or 0)
    quality += reach * coord['q']
    return {'cost': cost, 'sec': sec, 'quality': quality, 'handoff': reach, 'slip': slip,
            'coord_cost_known': coord['cost'] is not None}


def passes(answers):
    """Mean of repeated Jev answers per rung."""
    return [sum(a['passes'][i] for a in answers) / len(answers) for i in range(len(answers[0]['passes']))]


def objective(sims):
    q = sum(s['quality'] for s in sims)
    return sum(s['cost'] for s in sims) / q if q else float('inf')


def starts_for(rule, fid, table, jev, cutoff=None, others=None):
    if rule == 'cheapest_first':
        return 0
    if rule == 'always_top':
        return len(table[fid]) - 2
    if rule == 'oracle':
        row = table[fid]
        good = [i for i, c in enumerate(row[:-1]) if c and c['hidden'] >= 0.5]
        return good[0] if good else len(row) - 2
    if rule == 'jev_choice':
        return jev[fid][0]['start']
    if rule.startswith('jev_noul'):
        return ladder.jev_noul(passes(jev[fid]), cutoff)
    if rule == 'jev_ev':
        n = len(table[fid]) - 1
        costs = [sum(table[o][i]['cost'] for o in others if table[o][i]) / max(1, sum(1 for o in others if table[o][i]))
                 for i in range(n)]
        coord = table[fid][-1]['cost'] or max(costs) * 5
        return ladder.jev_ev(passes(jev[fid]), costs, coord)
    raise ValueError(rule)


def evaluate(table, jev):
    fids = sorted(f for f in table if f in jev and all(c is not None for c in table[f][:-1]))
    rows, starts = {}, {}
    fixed_rules = ['oracle', 'cheapest_first', 'always_top', 'jev_choice', 'jev_noul@0.5']
    for rule in fixed_rules:
        starts[rule] = {f: starts_for(rule, f, table, jev, 0.5) for f in fids}
    starts['jev_ev'] = {f: starts_for('jev_ev', f, table, jev, others=[o for o in fids if o != f]) for f in fids}
    starts['best_fixed (loo)'], starts['jev_noul (loo cutoff)'] = {}, {}
    for f in fids:  # leave-one-out: tune on the other fixtures, apply to this one
        others = [o for o in fids if o != f]
        n = len(table[f]) - 1
        best_s = min(range(n), key=lambda s: (objective([simulate(table[o], s) for o in others]), s))
        starts['best_fixed (loo)'][f] = best_s
        best_c = min(CUTOFFS, key=lambda c: (objective([simulate(table[o], ladder.jev_noul(passes(jev[o]), c)) for o in others]), c))
        starts['jev_noul (loo cutoff)'][f] = ladder.jev_noul(passes(jev[f]), best_c)
    for rule, chosen in starts.items():
        sims = {f: simulate(table[f], chosen[f]) for f in fids}
        rows[rule] = sims
    return fids, rows, starts


def bootstrap(fids, a, b, n=4000, seed=7):
    """90% interval on (cost per correct of a) - (cost per correct of b), resampling fixtures."""
    rng, diffs = random.Random(seed), []
    for _ in range(n):
        sample = [rng.choice(fids) for _ in fids]
        diffs.append(objective([a[f] for f in sample]) - objective([b[f] for f in sample]))
    diffs.sort()
    return diffs[int(0.05 * n)], diffs[int(0.95 * n)]


def auc(pairs):
    pos = [p for p, y in pairs if y]
    neg = [p for p, y in pairs if not y]
    if not pos or not neg:
        return None
    wins = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return wins / (len(pos) * len(neg))


def gonogo(host):
    cells, jev = load(host)
    rungs = CONFIG['ladders'][host]
    cheap, top = rungs[0]['id'], rungs[-1]['id']
    by = {}
    for c in cells:
        by.setdefault(c['fixture'], {}).setdefault(c['rung'], []).append(c)
    fids = sorted(f for f in by if cheap in by[f] and top in by[f])
    sep = [f for f in fids if not any(x['hidden_pass'] for x in by[f][cheap]) and any(x['hidden_pass'] for x in by[f][top])]
    pairs = []
    for f in fids:
        if f in jev:
            p = passes(jev[f])
            for idx, rid in ((0, cheap), (len(rungs) - 1, top)):
                pairs += [(p[idx], x['hidden_pass']) for x in by[f][rid]]
    mean = lambda xs: sum(xs) / len(xs) if xs else 0
    cf_cost = mean([by[f][cheap][0]['cost_usd'] + (0 if by[f][cheap][0]['public_pass'] else by[f][top][0]['cost_usd']) for f in fids])
    or_cost = mean([by[f][cheap][0]['cost_usd'] if by[f][cheap][0]['hidden_pass'] else by[f][top][0]['cost_usd'] for f in fids])
    cf_sec = mean([by[f][cheap][0]['seconds'] + (0 if by[f][cheap][0]['public_pass'] else by[f][top][0]['seconds']) for f in fids])
    or_sec = mean([by[f][cheap][0]['seconds'] if by[f][cheap][0]['hidden_pass'] else by[f][top][0]['seconds'] for f in fids])
    slips = sum(1 for f in fids if by[f][cheap][0]['public_pass'] and not by[f][cheap][0]['hidden_pass'])
    a = auc(pairs)
    print(f'# Go/no-go probe: {host}, {len(fids)} fixtures, cheapest={cheap}, top={top}\n')
    print('| Measure | Value | Target |\n|---|---:|---|')
    print(f'| Cheap fails hidden, top passes | {len(sep)}/{len(fids)} | at least 1/3 |')
    print(f'| Cheap passes public but fails hidden | {slips}/{len(fids)} | — |')
    print(f'| Mean cost: cheapest_first vs oracle | ${cf_cost:.4f} vs ${or_cost:.4f} | gap > 0 |')
    print(f'| Mean seconds: cheapest_first vs oracle | {cf_sec:.0f} vs {or_sec:.0f} | gap > 0 |')
    print(f'| AUC of Jev pass answers vs hidden outcome | {a if a is None else round(a, 3)} | above 0.6 |')
    print('\nSeparating fixtures: ' + (', '.join(sep) or 'none'))


def report(host):
    cells, jev = load(host)
    rungs, proxy = CONFIG['ladders'][host], CONFIG['coordinator_proxy'][host]
    table = stats(cells, rungs, proxy)
    fids, rows, starts = evaluate(table, jev)
    base = rows['cheapest_first']
    print(f'# Replay: {host}, {len(fids)} fixtures, leave-one-out where tuned\n')
    print('| Rule | Cost per correct | Total cost | Hidden-correct | Coordinator hand-offs | Public pass, hidden fail | Seconds | Start rungs | vs cheapest_first (90% CI) |')
    print('|---|---:|---:|---:|---:|---:|---:|---|---|')
    out = {}
    for rule, sims in rows.items():
        s = list(sims.values())
        hist = {}
        for f in fids:
            hist[rungs[starts[rule][f]]['id']] = hist.get(rungs[starts[rule][f]]['id'], 0) + 1
        ci = bootstrap(fids, sims, base) if rule != 'cheapest_first' else None
        out[rule] = {'cost_per_correct': objective(s), 'total_cost': sum(x['cost'] for x in s),
                     'correct': sum(x['quality'] for x in s), 'handoffs': sum(x['handoff'] for x in s),
                     'slips': sum(x['slip'] for x in s), 'seconds': sum(x['sec'] for x in s), 'starts': hist, 'ci': ci}
        o = out[rule]
        print(f"| {rule} | ${o['cost_per_correct']:.4f} | ${o['total_cost']:.3f} | {o['correct']:.1f}/{len(fids)} | "
              f"{o['handoffs']:.1f} | {o['slips']:.1f} | {o['seconds']:.0f} | "
              + ', '.join(f'{k} {v}' for k, v in hist.items())
              + (f" | {ci[0]:+.4f} to {ci[1]:+.4f} |" if ci else ' | — |'))
    if not any(c['coord_cost_known'] for c in base.values()):
        print('\nCoordinator rung cost not measured; hand-offs are counted but priced at $0.')
    (RESULTS / f'{host}-replay.json').write_text(json.dumps({'fixtures': fids, 'rules': out, 'starts': starts}, indent=1))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('cmd', choices=['gonogo', 'report'])
    p.add_argument('--host', required=True, choices=sorted(CONFIG['ladders']))
    a = p.parse_args(argv)
    gonogo(a.host) if a.cmd == 'gonogo' else report(a.host)


if __name__ == '__main__':
    main()
