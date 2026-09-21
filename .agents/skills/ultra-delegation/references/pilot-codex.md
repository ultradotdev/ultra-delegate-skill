# Native Codex repository trial

Use this workflow for the first bounded, read-only repo reviews or patch proposals.
The Python CLI prepares and checks decisions; the coordinator launches the exact
selected configuration through Codex's native worker tool and independently
reviews its result. It does not launch workers itself.

## Discover and prepare

Use the current host tool metadata to identify available model IDs and native
efforts. Supply an explicit Codex model catalog file containing `models` entries
with `slug`, `supported_reasoning_levels` (objects with `effort`), `context_window`,
optional `effective_context_window_percent`, and `input_modalities`. Include
`max_output_tokens` only when the host actually reports it. Do not substitute
provider marketing limits or invent missing capacity.

Create `host.json` from a fresh observation. The IDs below are illustrative;
replace them with exact currently exposed settings and a current UTC timestamp.
Get `delegation_allowed` from the coordinator's context guard. This first builder
supports only the `read-files` tool policy. The worker receives a read-only
instruction boundary; the tool list is a cooperative capability declaration,
not an operating-system sandbox.

```json
{
  "observed_at": "2026-09-21T00:00:00+00:00",
  "models": {"discovered-model-id": ["medium"]},
  "tools": ["read-files"],
  "delegation_allowed": true
}
```

Create `task.json` with exactly `task_id`, `group_id`, and `task`. Use the task
shape from `pilot.py example`, replacing all illustrative content. Required task
fields are `scope_id`, `operation`, `risk`, `complexity`, `work_kind`, `summary`,
`requirements`, `acceptance_gates`, `worker_boundary`, `intended_use`,
`required_tools`, `required_modalities`, `input_tokens`, and `output_tokens`.

Pick a narrow scope, explicit files and questions, and independently checkable
acceptance gates. Include `complete-output` whenever using the host-managed
output exception. That gate requires every requested part of the output to be
present and usable; truncated or incomplete results fail even if other quality
scores are high. Keep related variants in one `group_id` and use a fresh group
for an independent task. Keep source excerpts out of the routing summary.

Input and output budgets are declared admission reservations, not measured token
usage. Account conservatively for the complete worker input and host/tool
overhead. If context fit cannot be established, stop. The host manages its own
request assembly and output limits; a completeness gate detects incomplete
results after execution and cannot guarantee a hard token or cost cap.

```sh
SKILL_PATH=/path/to/extracted/ultra-delegation
python3 "$SKILL_PATH/scripts/pilot_codex.py" \
  --task task.json --catalog codex-model-catalog.json \
  --host-observation host.json --output packet.json \
  --candidate discovered-model-id:medium \
  --capability-description 'Read-only Python correctness review with source citations.' \
  --scope-envelope 'Bounded low-risk reviews; no edits, credentials or network.'
```

Repeat `--candidate` for a broader discovered set, up to twelve. The first becomes
`candidate-0`, the second `candidate-1`, and so on. IDs and efforts must occur in
both current host observations and the supplied catalog. Capability descriptions
are coordinator hypotheses, not quality evidence. Candidate costs remain unknown.
The builder reads only the three specified inputs and reserves a new packet file.
It does not scan source, conversations or credentials.

Configuration identity incorporates a hash of advertised host model settings,
including the context margin. This is a **host-configuration revision**, not an
immutable model-weights snapshot. It separates changed advertised configurations
but cannot detect an undisclosed provider update. Normal evidence freshness and
periodic independent audits remain necessary.

## Route, recheck, execute and assess

Keep `.ultra-delegation/` ignored in the target project. Start in shadow mode with
an explicitly chosen baseline. Supply only the existing credential's service and
account names; never its value. Environment credentials still take precedence.

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot init \
  --mode shadow --share-summaries --baseline-id candidate-0 \
  --allow-host-managed-output \
  --credential-service EXISTING_SERVICE --credential-ref EXISTING_ACCOUNT
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot route \
  --input packet.json --dry-run
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot route \
  --input packet.json --live
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot recheck \
  --decision dec_RETURNED_ID --input packet.json
```

`init` refuses to overwrite a policy. The host-managed-output flag is off by
default. It admits an unknown output ceiling only for remote Codex/OpenAI
`codex-native` candidates marked `native-host`; known context fit, reported output
bounds and every other eligibility check remain mandatory. The report preserves
null capacity and labels it unreported. It does not convert the reserved output
budget into an advertised host limit.

Immediately after successful recheck, the coordinator uses the native worker
tool with the selected model and effort and the complete bounded task. Verify the
returned execution profile matches. A changed packet, policy, evidence, stale
observation or failed guard requires reevaluation. A nomination is an experiment
proposal requiring its own authorized, isolated trial plan, not a dispatch route.

In shadow mode, Jev's recommendation and the effective baseline route may differ.
Record both. An accepted baseline result does not prove Jev chose that worker or
that an abstention was wrong. For meaningful model comparisons, obtain additional
independently reviewed results on the same task and record all failures and costs.

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot outcome-template \
  --decision dec_RETURNED_ID --candidate candidate-0 --output outcome.json
# Independently review the actual artifact, fill every gate and score, and hash it.
# Unknown cost or latency stays unknown. An unfilled form is invalid.
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot observe \
  --input outcome.json
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot report
```

Keep the reviewed artifact and test evidence locally alongside the metadata
report. Accepted observations contribute only to matching configuration and task
scope. One successful independent group does not qualify a model; confidence
bounds and group counts appear in future decisions. Security assessment remains
optional, off by default, and requires separate artifact-sharing permission.

## Observed readiness and limits

A real read-only smoke-runner review completed this full path with a native Terra
medium worker. The coordinator verified four findings, passing smoke tests,
unchanged source hashes and output completeness, then recorded an accepted result.
The next independent group saw one success with a Wilson lower bound of about
0.207, still unqualified. Jev recommended repackaging; shadow mode retained the
baseline. No model comparison, security-accuracy claim, threshold qualification
or total savings measurement follows from this single trial.
