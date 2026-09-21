# Yarn native-pilot runbook

Run from the Yarn repository. Set `HANDOFF_DIR` to the extracted handoff and use
a new project ledger. Python 3.10+ and the standard library are sufficient for
offline commands. Existing credential lookup is optional and read-only.

```sh
HANDOFF_DIR=/absolute/path/to/yarn-agent-handoff
SKILL_PATH="$HANDOFF_DIR/runtime/ultra-delegation"
python3 --version
python3 "$SKILL_PATH/scripts/pilot.py" --help
python3 "$SKILL_PATH/scripts/pilot_questions.py" --check
```

Do not reuse or migrate a prior-release policy into this RC6 ledger. Keep historic
records only as historic report inputs. The initial CLI policy is active, but it
does not send a routing request until a command uses `--live` and summary sharing
is explicitly enabled. RC6 permits immediate routing with empty history; it has
no local qualification-count or shadow-rollout prerequisite.

The scoped live routing validation is not a Yarn worker trial: v4 wording yielded
12/12 `clarify` responses, while the same task data with the v5 two-question
wording revision yielded 11/12 `route` responses and one `no-suitable-candidate`.
The bundled [validation](../../docs/active-recovery-validation.md) and
[results](../../docs/active-recovery-results.json) record 11 accepted native
requests across 12 task cards. The eight native invocations and 23 task attempts
are correlated development evidence; security/artifact judges were off and
worker/review costs are unknown. They are not Yarn quality, savings, or
calibration evidence.

## Prepare a real packet

Discover current native model IDs, supported efforts, capacity, modalities, and
the declared host tools. Use `pilot_codex.py` to turn that observation into a
non-synthetic packet. `read-files`, `edit-files`, and `run-tests` describe host
capabilities only; normal task authorization and native controls still apply.

```sh
python3 "$SKILL_PATH/scripts/pilot_codex.py" \
  --task task.json --catalog codex-model-catalog.json --host-observation host.json \
  --output .ultra-delegation/yarn-packet.json \
  --candidate discovered-model:medium \
  --capability-description 'Bounded Yarn slice with declared project validation.' \
  --scope-envelope 'One isolated low-risk task; coordinator owns integration.'

python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/yarn-pilot init \
  --share-summaries
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/yarn-pilot route \
  --input .ultra-delegation/yarn-packet.json --dry-run
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/yarn-pilot route \
  --input .ultra-delegation/yarn-packet.json --live
```

Do not execute a synthetic fixture, example model ID, invented capacity, or stale
host context. Use `--allow-host-managed-output` only for the documented native
output exception and include the `complete-output` mandatory gate.

## Run the persisted native workflow

Use the returned `dec_...` identifier and follow the detailed event examples in
`runtime/ultra-delegation/references/pilot-workflow.md`.

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/yarn-pilot workflow-start \
  --decision dec_RETURNED_ID --input .ultra-delegation/yarn-packet.json --bakeoff auto
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/yarn-pilot workflow-next \
  --request req_RETURNED_ID --input .ultra-delegation/yarn-packet.json
```

For each returned action: write the `launching` event with `--packet`, call the
native coordinator tool in an isolated checkout, then send `dispatched` with the
actual run/config/base/checkout values and `completed` with the artifact hash.
Create an outcome template with `--request` and `--attempt`, independently review
it, call `observe`, and send `reviewed`. On failure use a stable code and only a
specific review findings hash for the one allowed repair. Do not redispatch an
uncertain launch; use `launch-not-started` only after the host confirms absence.

Only refresh `context.observed_at` before a fallback recheck. Any other packet
change needs a new routing decision. The helper may return `coordinator-required`;
that is a real handoff, not a reason to weaken gates or invent another worker.

## Inspect results

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/yarn-pilot report
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/yarn-pilot learning audit
```

The report files are new exclusive outputs. Retain them with task evidence, but
do not claim its simulated fixtures or unit tests are completed real trials. Use
the acceptance checklist to record the actual run, review, costs, and unresolved
work.
