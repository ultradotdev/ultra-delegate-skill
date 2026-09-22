#!/usr/bin/env python3
"""Build a native Codex packet from explicit task, catalog and host observations.

No network, credentials, repository scanning, worker execution or policy changes.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pilot
import pilot_boundaries
import pilot_core as core
import capability_index as research


def _write_new_text(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(value)
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise


def build_packet(task_packet, catalog, host, profiles, capability, envelope, capability_index=None):
    core.fields(task_packet, {'task_id', 'group_id', 'task'})
    core.fields(host, {'observed_at', 'models', 'tools', 'delegation_allowed'})
    core.timestamp(host['observed_at'])
    core.require(type(host['delegation_allowed']) is bool, 'invalid-context-guard')
    core.labels(host['tools'])
    core.require(set(host['tools']) <= {'read-files', 'edit-files', 'run-tests'}, 'unsupported-native-tool-policy')
    core.require(isinstance(host['models'], dict), 'invalid-host-models')
    for name, efforts in host['models'].items():
        core.label(name); core.labels(efforts)
    core.prose(capability); core.prose(envelope)
    if capability_index is not None: research.validate(capability_index)
    core.require(isinstance(catalog, dict) and isinstance(catalog.get('models'), list), 'invalid-model-catalog')
    core.require(isinstance(profiles, list) and 0 < len(profiles) <= 12, 'invalid-profiles')
    packet = {'schema':'ultra-pilot-task-v1', 'synthetic':False, **copy.deepcopy(task_packet),
              'context':{'host':'codex', 'provider':'openai', 'observed_at':host['observed_at'],
                         'delegation_allowed':host['delegation_allowed']}, 'candidates':[]}
    for i, profile in enumerate(profiles):
        core.require(isinstance(profile, str) and ':' in profile, 'invalid-profile')
        model, effort = profile.rsplit(':',1)
        core.label(model); core.label(effort)
        matches = [m for m in catalog['models'] if isinstance(m, dict) and m.get('slug') == model]
        core.require(len(matches) == 1, 'model-not-in-catalog')
        m = matches[0]
        supported = [r.get('effort') for r in m.get('supported_reasoning_levels', []) if isinstance(r, dict)]
        core.require(effort in host['models'].get(model, []) and effort in supported, 'native-setting-unavailable')
        window = m.get('context_window')
        core.integer(window,1)
        core.require(window <= 1_000_000_000, 'invalid-context-capacity')
        percent = m.get('effective_context_window_percent',100)
        core.require(core.transport.number(percent,1,100), 'invalid-context-margin')
        output = m.get('max_output_tokens')
        if output is not None: core.integer(output,1)
        modalities = m.get('input_modalities', [])
        core.labels(modalities)
        # Only advertised model/configuration metadata enters this identity.
        # This is a host-configuration revision, not an immutable weights claim.
        manifest = {'model':model, 'efforts':supported, 'context_window':window,
                    'effective_context_window_percent':percent, 'max_output_tokens':output,
                    'input_modalities':modalities, 'comp_hash':m.get('comp_hash')}
        description = capability
        if capability_index is not None:
            description += '\n' + research.describe(capability_index, 'openai', model, effort,
                as_of=core.timestamp(host['observed_at']).astimezone(dt.timezone.utc).date().isoformat())
            core.prose(description)
        packet['candidates'].append({
            'id':'candidate-'+str(i), 'provider':'openai', 'host':'codex', 'adapter':'codex-native',
            'model':model, 'model_revision':model+':hostcfg-'+core.digest(manifest)[:12],
            'effort':effort, 'prompt_contract':'native-bounded-v1', 'prompt_version':'1',
            'tool_policy':'native-tools-'+core.digest(sorted(host['tools']))[:12], 'capability_description':description, 'scope_envelope':envelope,
            'available':True, 'tools':copy.deepcopy(host['tools']), 'modalities':copy.deepcopy(modalities),
            'context_window':int(window*percent/100), 'max_output_tokens':output,
            'output_limit_source':'native-host' if output is None else 'explicit',
            'execution_location':'remote', 'estimate_usd':None, 'roles':['fallback' if i==0 else 'challenger'],
        })
    core.validate_packet(packet)
    return packet


def prepare_project(root, task_packet, catalog, host, output_dir, *, profiles=None,
                    capability=None, envelope=None, capability_index=None, efficiency_hints=None):
    """Create an inspectable local packet bundle; never infer host availability."""
    p = pilot.load_policy(root)
    if profiles is None:
        profiles = []
        for model in sorted(catalog.get('models', []), key=lambda m: m.get('slug', '')):
            name = model.get('slug')
            supported = [r.get('effort') for r in model.get('supported_reasoning_levels', [])]
            available = [e for e in host.get('models', {}).get(name, []) if e in supported]
            if available:
                profiles.append(name + ':' + ('medium' if 'medium' in available else available[0]))
    assets = Path(__file__).resolve().parent.parent / 'assets'
    index = research.load(assets / 'capability-index.json') if capability_index is None else capability_index
    hints = pilot.read_json(assets / 'efficiency-hints.json') if efficiency_hints is None else efficiency_hints
    core.fields(hints, {'schema', 'note', 'models'})
    core.require(hints['schema'] == 'ultra-efficiency-hints-v1' and isinstance(hints['models'], list), 'invalid-efficiency-catalog')
    identities = [(r['provider'], r['model'], r['effort']) for r in hints['models']]
    core.require(len(identities) == len(set(identities)), 'duplicate-efficiency-hint')
    packet = build_packet(task_packet, catalog, host, profiles,
        capability or ('Native coding assistant. Supported work includes inspecting source, proposing bounded '
                       'implementation fixes, writing tests, and reviewing code for defects using the discovered '
                       'tools. This describes work types, not a demonstrated success rate. Model-specific '
                       'capability expectations follow in the attributed research.'),
        envelope or task_packet['task']['worker_boundary'], index)
    for candidate in packet['candidates']:
        matches = [r for r in hints['models'] if r['provider'] == candidate['provider'] and r['model'] == candidate['model'] and r['effort'] in {None, candidate['effort']}]
        if matches:
            match = next((r for r in matches if r['effort'] == candidate['effort']), matches[0])
            candidate['efficiency_hint'] = copy.deepcopy(match['hint'])
    outcomes = pilot.load_records(root, 'outcomes')
    preview = pilot.route_packet(packet, p, outcomes, dry_run=True)
    directory = Path(output_dir)
    core.require(not directory.is_symlink(), 'preparation-directory-symlink')
    core.require(not directory.exists() or (directory.is_dir() and not any(directory.iterdir())),
                 'preparation-directory-not-empty')
    directory.mkdir(parents=True, exist_ok=True)
    core.require(not directory.is_symlink(), 'preparation-directory-symlink')
    paths = {name: directory / name for name in ('packet.json', 'sharing-preview.json', 'worker-contract.md', 'next-steps.json', 'task-labels.json')}
    instructions = {'schema': 'ultra-pilot-preparation-v1', 'input_hash': preview['input_hash'],
        'policy_hash': preview['policy_hash'], 'dispatch_authorized': False,
        'selection_preference': p['selection_preference'], 'bakeoff': p['bakeoff'],
        'eligible_candidates': sum(r['eligible'] for r in preview['candidates']),
        'excluded_candidates': [{'id': r['id'], 'reasons': r['reasons']} for r in preview['candidates'] if not r['eligible']],
        'summary_sharing_enabled': p['share_summaries'],
        'next_step': 'Inspect sharing-preview.json, then route --live if summary sharing is authorized; follow the returned action.',
        'route_command': [sys.executable, str(Path(pilot.__file__).resolve()), '--root', str(Path(root).resolve()),
                          'route', '--input', str(paths['packet.json'].resolve()), '--live'],
        'files': {name: str(path.resolve()) for name, path in paths.items()}}
    pilot.write_new(paths['packet.json'], packet)
    pilot.write_new(paths['sharing-preview.json'], preview)
    _write_new_text(paths['worker-contract.md'], pilot_boundaries.worker_contract(packet['task']['boundaries']))
    pilot.write_new(paths['task-labels.json'], {packet['task_id']: packet['task']['summary']})
    pilot.write_new(paths['next-steps.json'], instructions)
    return instructions


def prepare_main(argv):
    parser = pilot.SafeParser(description='Prepare the local native packet and exact sharing preview. No inference or dispatch.')
    parser.add_argument('--root', type=Path, default=Path('.ultra-delegation/pilot'))
    for name in ('task', 'catalog', 'host-observation', 'output-dir'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--candidate', action='append')
    parser.add_argument('--capability-description')
    parser.add_argument('--scope-envelope')
    parser.add_argument('--capability-index', type=Path)
    parser.add_argument('--efficiency-hints', type=Path)
    args = parser.parse_args(argv)
    result = prepare_project(args.root, pilot.read_json(args.task), pilot.read_json(args.catalog),
        pilot.read_json(args.host_observation), args.output_dir, profiles=args.candidate,
        capability=args.capability_description, envelope=args.scope_envelope,
        capability_index=research.load(args.capability_index) if args.capability_index else None,
        efficiency_hints=pilot.read_json(args.efficiency_hints) if args.efficiency_hints else None)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Match pilot.py's global-root spelling as well as prepare --root ROOT.
    if len(argv) >= 3 and argv[0] == '--root' and argv[2] == 'prepare':
        argv = ['prepare', *argv[:2], *argv[3:]]
    if argv and argv[0] == 'prepare':
        try:
            return prepare_main(argv[1:])
        except (core.PilotError, core.transport.ServiceError) as error:
            print(json.dumps({'error': str(error)}), file=sys.stderr)
        except (ValueError, OSError, KeyError, TypeError):
            print('{"error":"native-preparation-invalid"}', file=sys.stderr)
        return 2
    parser = pilot.SafeParser(description=__doc__)
    for name in ('task', 'catalog', 'host-observation', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--candidate', action='append', required=True, help='Exact exposed model:native-effort')
    parser.add_argument('--capability-description', required=True)
    parser.add_argument('--scope-envelope', required=True)
    parser.add_argument('--capability-index', type=Path, help='Reviewed research JSON; adds dated priors only')
    args = parser.parse_args(argv)
    try:
        packet = build_packet(pilot.read_json(args.task), pilot.read_json(args.catalog),
                              pilot.read_json(args.host_observation), args.candidate,
                              args.capability_description, args.scope_envelope,
                              research.load(args.capability_index) if args.capability_index else None)
        pilot.write_new(args.output,packet)
        print(json.dumps({'packet_written':True, 'input_hash':core.digest(packet),
                          'candidate_count':len(packet['candidates']), 'dispatch_authorized':False,
                          'model_revision_kind':'host-configuration-not-immutable-weights'}))
        return 0
    except (ValueError, OSError, KeyError, TypeError):
        print('{"error":"native-packet-invalid"}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
