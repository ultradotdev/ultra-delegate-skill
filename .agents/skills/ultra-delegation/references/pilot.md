# Jev project pilot

`scripts/pilot.py` is a Python 3.10+ local coordinator helper. It asks Jev one
bounded routing batch when live routing is enabled, persists decisions and
reviewed outcomes, plans recovery, and renders reports. It never starts a
worker, runs project tests, invokes another model CLI, or changes credentials.
The coordinator owns native execution, integration, and final acceptance.

`init` defaults to `--mode active`; the core policy default is `off` until a
project creates `policy.json`. A live Jev call requires both `--live` and
`share_summaries: true`. The initial policy keeps summary sharing, artifact
sharing, advisory security, and host-managed output disabled.

```sh
SKILL_PATH=/path/to/ultra-delegation
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot init
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot route \
  --input packet.json --dry-run
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot route \
  --input packet.json --live
```

Use a fresh state directory. `init`, decisions, outcomes, reports, and generated
templates reserve their destination and never overwrite it. Keep the state
directory out of version control. The CLI reads only specified JSON files and
the configured existing credential when a live Jev request is authorized; it
does not set, migrate, delete, print, or prompt for credentials.

## Packet and decision

A packet has schema `ultra-pilot-task-v1`, opaque `task_id` and `group_id`, a
bounded task contract, a fresh host context, and exact discovered candidates.
Its task declares requirements, mandatory acceptance gates, worker boundary,
risk, tools/modalities, and input/output admission reservations. Candidates
declare the exact model revision, host, adapter, native effort, prompt contract,
tool policy, availability, capacities, and roles. `pilot_codex.py` builds a
Codex packet from current host discovery.

The router applies hard eligibility first, then evaluates task demands and the
shortlist in one Jev batch. Sparse history is ordinary: a new eligible
configuration may be selected immediately. Demand signals guide selection and
required independent review; they do not become a complexity veto or a
qualification gate. A user choice or project pin remains authoritative. A user
choice has no implicit recovery alternatives.

The saved decision records `selected_configuration_id`, semantic ordered
`alternative_configuration_ids`, configuration metadata, input/policy/evidence
hashes, acceptance gates, and question/model versions. A service failure remains
an explicit decision result for the coordinator; it is not evidence against a
worker. A route is still only a plan until the native attempt recheck passes.

Unknown context capacity blocks routing. With the explicit
`allow_host_managed_output` policy opt-in, a remote Codex/OpenAI `codex-native`
candidate may omit an output ceiling only when it is marked `native-host` and
the task contains `complete-output`. This preserves context admission and makes
completion independently reviewable; it does not create a token, cost, or
sandbox guarantee.

## Native recovery workflow

After routing, use the exact protocol in [pilot-workflow.md](pilot-workflow.md).
It creates one request with immutable acceptance gates and planned attempts.
Auto bake-off starts two initial eligible candidates when selected history is
cold or includes failures; `--bakeoff on` and `--bakeoff off` override this.
Attempt kinds are `initial`, `comparison`, `repair`, and `fallback`.

An independently rejected or execution-failed artifact is retained. Once all
current work is terminal, the helper schedules at most one repair for that
configuration only when the coordinator supplies a concrete findings hash. It
then uses an unattempted eligible alternative. It returns
`coordinator-required` when viable configurations or optional workflow limits
are exhausted. A passing comparison or fallback accepts the request immediately;
the helper never merges candidate work or makes a release decision.

## Review, learning, and advisory checks

Generate a completed outcome form only after the artifact exists. The independent
review records every declared mandatory gate, coverage/correctness/maintainability/
clarity scores, critical defects, observed latency and measured/estimated/unknown
cost components. The optional judge is a blinded advisory score supplied through
`observe --judge-input`; it needs `share_artifacts` and never accepts a result.
Security is similarly advisory through `observe --security-check --security-input`.
Neither unavailable evaluator blocks ordinary outcome recording.

Use `learning audit`, `learning export --output FILE`, `learning import --input
FILE`, and `learning retract --outcome ID --reason CODE` for metadata-only local
learning operations. Imports are labelled `imported-unverified`; retractions keep
the original outcome on disk and remove it from normal routing evidence.

## Reports and current evidence

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot report
```

The command creates a new HTML/JSON pair. It separates first-attempt success,
initial-bake-off success, eventual request success, recovery overhead, pending
requests, coordinator-required requests, known versus unknown costs, and advisory
findings. It excludes task prose, source, artifacts, credentials, and arbitrary
provider text. Accepted results establish a reviewed outcome for their recorded
scope, not a general model-quality or savings claim.

The shipped unit and simulated fixtures verify contracts and recovery behavior.
They are not real Yarn trials, live Jev measurements, worker-quality evidence,
security certification, calibrated thresholds, or realized savings. Run the
practical harness in [pilot-benchmark.md](pilot-benchmark.md) only with separately
prepared cases and independently reviewed artifacts.
