#!/usr/bin/env python3
"""Build a native Codex packet from explicit task, catalog and host observations.

No network, credentials, repository scanning, worker execution or policy changes.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pilot
import pilot_core as core


def build_packet(task_packet, catalog, host, profiles, capability, envelope):
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
        packet['candidates'].append({
            'id':'candidate-'+str(i), 'provider':'openai', 'host':'codex', 'adapter':'codex-native',
            'model':model, 'model_revision':model+':hostcfg-'+core.digest(manifest)[:12],
            'effort':effort, 'prompt_contract':'native-bounded-v1', 'prompt_version':'1',
            'tool_policy':'native-tools-'+core.digest(sorted(host['tools']))[:12], 'capability_description':capability, 'scope_envelope':envelope,
            'available':True, 'tools':copy.deepcopy(host['tools']), 'modalities':copy.deepcopy(modalities),
            'context_window':int(window*percent/100), 'max_output_tokens':output,
            'output_limit_source':'native-host' if output is None else 'explicit',
            'execution_location':'remote', 'estimate_usd':None, 'roles':['fallback' if i==0 else 'challenger'],
        })
    core.validate_packet(packet)
    return packet


def main(argv=None):
    parser = pilot.SafeParser(description=__doc__)
    for name in ('task', 'catalog', 'host-observation', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--candidate', action='append', required=True, help='Exact exposed model:native-effort')
    parser.add_argument('--capability-description', required=True)
    parser.add_argument('--scope-envelope', required=True)
    args = parser.parse_args(argv)
    try:
        packet = build_packet(pilot.read_json(args.task), pilot.read_json(args.catalog),
                              pilot.read_json(args.host_observation), args.candidate,
                              args.capability_description, args.scope_envelope)
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
