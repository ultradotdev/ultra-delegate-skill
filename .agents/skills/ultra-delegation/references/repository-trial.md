# Repository trial: coordinator walkthrough

The user asks for an ordinary bounded repository task. The coordinator prepares
and maintains the files below; do not ask the user to hand-author JSON, manage
workflow events, or choose internal IDs. Ask only for missing desired behavior,
acceptance requirements, or permissions. Run commands from the target repository
using an absolute `SKILL_PATH` to the extracted skill.

## Prepare and inspect

Discover exact native model IDs, supported efforts, effective context capacities,
modalities, and tools as described in [pilot-codex.md](pilot-codex.md). An explicit
native catalog file may provide advertised capacities; currently exposed native
controls remain authoritative. Never infer availability from the research index.
The coordinator writes `task.json` with task_id, group_id, and the task contract
listed in that reference, and `host.json` from current discovery. Use fresh task
and group IDs for independent work; keep IDs unchanged during recovery.

Use `pilot.py` for this workflow, including `auth status|check` and `configure`.
The legacy `jev.py` uses a different policy and packet format; it rejects pilot
ledgers to prevent accidental configuration damage.

Initialize once using the existing credential locator supplied by the user, or
use `TYPESAFE_API_KEY`. There is no credential set/delete command. Only enable
summary sharing when this task's bounded summaries are authorized for Jev.

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot init \
  --share-summaries --credential-service EXISTING_SERVICE --credential-ref EXISTING_ACCOUNT
python3 "$SKILL_PATH/scripts/pilot_codex.py" prepare \
  --root .ultra-delegation/pilot --task task.json \
  --catalog codex-model-catalog.json --host-observation host.json \
  --output-dir .ultra-delegation/prepared/task-001
```

`prepare` automatically attaches the shipped research and efficiency hints, and
uses medium effort where jointly supported by the catalog and host. Otherwise
it uses the first explicitly exposed supported effort. Supply repeatable
`--candidate exact-model:effort` flags to select other discovered profiles.
Omit those flags to consider the full native pool; the coordinator's own model
is not a reason to restrict the worker pool to that one model.
It never silently drops profiles beyond the twelve-candidate packet bound.
It writes packet.json, sharing-preview.json, task-labels.json, and next-steps.json.
These explicit local files contain task text; retain them only in ignored local
storage. Decision/outcome ledgers stay sanitized.

Inspect the exact preview and exclusions. Native Codex output limits may be
host-managed: enable `--allow-host-managed-output` only under the documented
contract and include a mandatory `complete-output` gate. Missing acceptance
requirements are returned to the user; unavailable capabilities stay with the
coordinator. Follow next-steps.json's route command only after sharing is enabled.

`pilot.py --root .ultra-delegation/pilot auth status` reads configuration without
a network call; `auth check` makes one explicit synthetic access check. A sandbox
may hide an existing Keychain entry or restrict network access. Request the host
permission needed to read/send the already authorized request; never recreate the
credential or treat service-unavailable as a successful Jev recommendation.

`init` preserves an existing policy and records. Change preferences explicitly:

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot configure \
  --selection-preference efficiency_hints --bakeoff auto
```

The alternative is `strongest_fit`; bakeoff supports auto/on/off independently.
Auto compares cold or recently failing selections. No qualification count blocks
first use. Configuration changes invalidate earlier decisions; route again.
Security is off by default. `--share-artifacts` is a separate permission for
explicitly selected judge/security excerpts, not part of routing permission.

## Execute and review

Use the IDs returned by the commands. For each planned action, check the current
packet, reserve launch, then call the actual native worker tool in an isolated
checkout. The helper never launches a worker or executes project checks.
Prepare isolated copies before routing where possible: capability observations
expire after five minutes by default. Start promptly after routing. On a
`candidate-no-longer-eligible` error, inspect `route --dry-run` exclusion reasons;
refresh actual host discovery rather than guessing that an added review gate
invalidated the task. A changed packet before workflow-start needs reevaluation.

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-start \
  --decision dec_RETURNED_ID --input .ultra-delegation/prepared/task-001/packet.json
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-next \
  --request req_RETURNED_ID --input .ultra-delegation/prepared/task-001/packet.json
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-event \
  --request req_RETURNED_ID --attempt attempt-1 --type launching \
  --packet .ultra-delegation/prepared/task-001/packet.json
```

After the native call, record `--type dispatched --run-id ACTUAL_RUN_ID
--configuration-id ACTUAL_ACCEPTED_CONFIGURATION --base-revision BASE
--checkout-hash SHA256`. A configuration mismatch stops recording; never claim
that another worker executed the planned configuration. When it finishes,
record `--type completed --artifact-file DELIVERED_PATCH_OR_MANIFEST` for the actual
delivered artifact. The helper computes its SHA-256; do not transcribe long hashes.
For multiple files, create a local manifest of their actual content hashes and
filenames, then pass that manifest file. It must include every delivered change.
Hash the actual checkout/input and delivered artifact bytes; do not use examples
or hashes of arbitrary labels as execution evidence.

If the coordinator recorded the wrong artifact hash, stop before review. After
verifying the actual files, use `--type artifact-corrected --artifact-file FILE
--reason-code artifact-recording-error` on that attempt. This permits one
pre-review correction, preserves both hashes in the audit trail, and is reported
explicitly. It cannot alter a published, accepted, or interrupted paid review.
It corrects bookkeeping, never a worker's code; changed code needs a new attempt.

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-review-template \
  --request req_RETURNED_ID --attempt attempt-1 --output .ultra-delegation/review.json
# Coordinator runs checks and independently fills gates, scores, reviewer identity,
# reviewed demands, defects and observed telemetry. Unknown costs remain unknown.
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-review \
  --request req_RETURNED_ID --attempt attempt-1 --input .ultra-delegation/review.json
```

Review is independent of the worker, blinded to identity/cost where practical.
Mandatory checks plus reviewed quality and absence of critical defects determine
acceptance. Jev's fit numbers and optional artifact judge do not accept a patch.
For a concrete repairable failure, add `--repairable --findings-hash SHA256` to
workflow-review. One targeted repair per configuration is permitted. Otherwise
the existing comparison/fallback protocol applies. See [pilot-workflow.md](pilot-workflow.md)
for event details, uncertain launches, limits and replan.

## Resume, deliver, learn

`workflow-status --request req_RETURNED_ID` explains each attempt and the next
step without reserving launches. Repeat identical flag commands safely after an
interruption. A launching attempt requires reconciliation with the host; never
blindly launch again. Complete review publication resumes without another paid
check. Pending comparisons finish before recovery spend; an accepted attempt
can be delivered immediately. Only cancel owned work.

Generate `report --task-descriptions .ultra-delegation/prepared/task-001/task-labels.json`
for a readable local HTML/JSON report. The labels are explicit local-only text.
The first screen distinguishes first-attempt failure from eventual acceptance.
Deliver the actual reviewed artifact within the user's integration scope, along
with its report. If all eligible attempts fail, take the explicit coordinator
handoff rather than claiming completion or relaxing acceptance.

Reviewed outcomes are loaded into future routes automatically. Research priors
and efficiency hints are never exported as successful worker evidence. Relative
API price ordering is only a selection hint: native cost, latency and savings
remain unavailable until actually measured or explicitly estimated.

Use [repository-benchmark.md](repository-benchmark.md) for the twelve executable
fixtures and matched Epoch comparisons. Fixture validation and forced failure
checks are separate from naturally observed model results.
