# Native Codex pilot

Use this path for a bounded Codex-native review, test change, or isolated bug-fix
proposal. The Python helper prepares packets and records the native workflow. The
coordinator calls Codex-native tools. Neither the helper nor a task packet creates
a sandbox, grants authority, or runs a model.

For normal first use, follow [repository-trial.md](repository-trial.md): its
`prepare` command creates the packet, exact sharing preview, and next steps
with the shipped research and efficiency hints. The lower-level builder below
remains available for explicit packets.

## Discover the actual host

Prepare a fresh `host.json` from the host's currently exposed model/effort/tool
metadata. The builder accepts only `read-files`, `edit-files`, and `run-tests` as
declared native tools. They are host capability observations, not operating-system
permissions or a security guarantee.

```json
{
  "observed_at": "2026-09-21T00:00:00+00:00",
  "models": {"discovered-model-id": ["medium", "high"]},
  "tools": ["read-files", "edit-files", "run-tests"],
  "delegation_allowed": true
}
```

Supply a current native catalog and a task object with `task_id`, `group_id`, and
the complete task contract. The contract must include an explicit scope,
requirements, mandatory acceptance gates, worker boundary, intended use, risk,
work kind, operation, complexity, required tools/modalities, and input/output
reservations. It must also contain the structured `boundaries` object shown below.
Every category has nonempty items or a nonempty `not_applicable` explanation,
never both. Set authorization explicitly; `unknown` cannot route. Keep the packet summary sanitized: source excerpts and credentials
do not belong in routing inputs.

The coordinator writes this shape (the user does not fill it in). Replace the
example with the actual request, including every field; `task` is a nested object.

```json
{
  "task_id": "parser-fix-001",
  "group_id": "independent-parser-task-001",
  "task": {
    "scope_id": "python-parser",
    "summary": "Repair a bounded parser edge case in the supplied repository.",
    "requirements": ["Preserve the public API.", "Reject malformed tokens with ValueError."],
    "acceptance_gates": ["behavioral-tests", "scope", "complete-output"],
    "boundaries": {
      "allowed_changes": {"items": ["Modify the parser and its focused tests."], "not_applicable": null},
      "allowed_actions": {"items": ["Read assigned files and run focused tests locally."], "not_applicable": null},
      "protected_behavior": {"items": ["Preserve the public API and unrelated parser behavior."], "not_applicable": null},
      "protected_data": {"items": [], "not_applicable": "No user, production, or credential data is supplied."},
      "coordinator_decisions": {"items": ["The coordinator owns integration and release."], "not_applicable": null},
      "security_requirements": {"items": [{"id": "no-external-effects", "requirement": "Do not use networks, external services, credentials, or external writes.", "mandatory": true}], "not_applicable": null},
      "authorization": "granted",
      "security_sensitive": false
    },
    "worker_boundary": "One parser and focused tests in an isolated checkout; coordinator owns integration.",
    "intended_use": "Patch proposal independently reviewed before integration.",
    "risk": "low",
    "work_kind": "coding",
    "operation": "patch-proposal",
    "complexity": "routine",
    "required_tools": ["read-files", "edit-files", "run-tests"],
    "required_modalities": ["text"],
    "input_tokens": 8000,
    "output_tokens": 4000
  }
}
```

Token reservations are coordinator-supplied planning bounds, not observed usage.
`prepare` accepts a new or empty output directory and refuses to overwrite a
previous bundle. It writes `worker-contract.md` beside `packet.json` and the
sharing preview. Inspect its exact boundary JSON and SHA-256 before routing; a
hash mismatch or changed contract requires a fresh packet. Its default candidate declaration names supported work types;
the appended, model-specific research supplies expectations, not proven success.

```sh
python3 "$SKILL_PATH/scripts/pilot_codex.py" \
  --task task.json --catalog codex-model-catalog.json \
  --host-observation host.json --output packet.json \
  --candidate discovered-model-id:medium \
  --candidate discovered-model-id:high \
  --capability-index "$SKILL_PATH/assets/capability-index.json" \
  --capability-description 'Bounded component patch with project tests and review.' \
  --scope-envelope 'One isolated low-risk component; coordinator owns integration.'
```

Every candidate must appear in both the supplied catalog and fresh host observation.
The `--capability-index` option appends
distinct, dated research priors where exact model matches exist. Read
[capability-index.md](capability-index.md) for source coverage, age warnings and
the offline HTML/JSON preview. Research does not replace host discovery or local
outcome evidence.

The builder writes a host-configuration revision and hashes the declared native
tool policy into its identity. That describes advertised host configuration; it
is not an immutable model-weights claim. `max_output_tokens` may be omitted only
under the explicit host-managed-output policy exception described in
[pilot.md](pilot.md).

## Route and start a native request

Create a fresh v2 project ledger. Do not copy an old policy into it: a prior
release policy is not silently migrated or activated. Historical decision and
outcome records remain reportable as historical data.

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot init \
  --share-summaries --allow-host-managed-output
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot route \
  --input packet.json --dry-run
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot route \
  --input packet.json --live
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-start \
  --decision dec_RETURNED_ID --input packet.json --bakeoff auto
```

`--share-summaries` authorizes the bounded routing request, not artifact sharing.
The `--live` route command is the only Jev network step. The worker task is
authorized by the coordinator's normal task scope, then rechecked for every
planned native attempt. If the candidate, packet contract, policy, evidence,
host context, or delegation guard has changed, stop and create a fresh decision.

Follow [pilot-workflow.md](pilot-workflow.md) exactly: inspect the planned action,
record `launching`, make the native tool call in an isolated checkout, then record
the returned run ID, observed configuration, base revision and checkout hash.
Record its artifact hash, independently review it through an outcome template,
observe it, and finally submit the `reviewed` event. Native run output is never a
Python dispatch result.

## Limits and evidence

The request retains failed, rejected, incomplete, canceled, comparison, repair,
and fallback attempts. Only independent review plus all mandatory gates, quality
floors, and no critical defect accepts an artifact. Canceled work is not a failed
result. A successful alternative completes the request without automatically
merging its patch or waiting for irrelevant comparisons.

Use optional `workflow.max_attempts`, `workflow.max_concurrency`, and
`workflow.max_elapsed_seconds` only when project limits are wanted. They bound
workflow planning; unknown native usage and subscription quota do not become made
up dollar caps. Reports label costs as measured, estimated, or unknown.

The included fixtures and unit tests exercise simulated native events. They do not
document a completed real Codex or Yarn trial. Keep real results separate and
record actual host/model metadata, review evidence, and project validation.
