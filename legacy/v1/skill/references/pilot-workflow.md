# Native execution and recovery protocol

The workflow module persists a request and its attempts. It plans native actions;
the coordinator executes Codex tools and project checks. It never dispatches a
worker, creates a worktree, merges output, or guesses a native run result.

For flag-based events, combined review publication, and resume instructions,
start with [repository-trial.md](repository-trial.md). The raw event interface
below remains supported for integrations.

Start only from a saved active route and the identical packet:

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-start \
  --decision dec_RETURNED_ID --input packet.json --bakeoff auto
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-next \
  --request req_RETURNED_ID --input packet.json
```

`workflow-next` returns planned `dispatch` actions and performs the per-attempt
recheck. It does not reserve or start a native worker. `auto` makes an initial
comparison for cold or failed selected evidence; `on` and `off` override it.
Optional `policy.json.workflow` limits are positive `max_attempts`,
`max_concurrency`, and `max_elapsed_seconds` values. Exhaustion returns the task
to the coordinator.

For every returned dispatch action, reserve the attempt immediately before the
native call. The packet is required for this event, so the helper repeats its
recheck. Then call the coordinator's native tool using the returned configuration
ID and an isolated checkout. Record the actual native run—not a Python-made-up
run—before recording completion.

```sh
cat > /tmp/launch.json <<'JSON'
{"id":"event-001","type":"launching","attempt_id":"attempt-1"}
JSON
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-event \
  --request req_RETURNED_ID --input /tmp/launch.json --packet packet.json

# Coordinator uses its native worker tool here. It records the actual model/config,
# native run ID, base revision, and isolated checkout hash.
cat > /tmp/dispatched.json <<'JSON'
{"id":"event-002","type":"dispatched","attempt_id":"attempt-1","run_id":"native-run-01","configuration_id":"cfg_RECORDED","base_revision":"base-revision","checkout_hash":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
JSON
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-event \
  --request req_RETURNED_ID --input /tmp/dispatched.json

cat > /tmp/completed.json <<'JSON'
{"id":"event-003","type":"completed","attempt_id":"attempt-1","artifact_hash":"abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"}
JSON
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-event \
  --request req_RETURNED_ID --input /tmp/completed.json
```

Replace `cfg_RECORDED` with the configuration in the planned action and each
placeholder hash with a real lowercase SHA-256 digest. Event IDs are opaque,
unique labels. Event data is allowlisted and redacted: do not put raw errors,
source excerpts, prompts, or worker output in it.

## Independent review and acceptance

Create the form after completion. It binds the decision, request, attempt, run,
configuration, and artifact hash. Fill it from a separate review and observed
tests, then write the resulting outcome before the `reviewed` event.

Each decision is also bound to the packet's structured boundary hash. Review the
delivered artifact against allowed changes/actions, protected behavior/data,
coordinator decisions, and every mandatory security requirement. The worker
contract cannot be widened during recovery.

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot outcome-template \
  --decision dec_RETURNED_ID --candidate candidate-LOCAL_ID \
  --request req_RETURNED_ID --attempt attempt-1 --output outcome.json
# Fill outcome.json with all mandatory gates, scores, costs, and review verdict.
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot observe --input outcome.json

cat > /tmp/reviewed.json <<'JSON'
{"id":"event-004","type":"reviewed","attempt_id":"attempt-1","outcome_id":"out_RETURNED_ID"}
JSON
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-event \
  --request req_RETURNED_ID --input /tmp/reviewed.json
```

Security is off by default. The helper does not invoke scanners or collect
evidence. When security screening is enabled, the coordinator supplies only the
selected excerpts and validation summary, plus the unchanged boundaries and
security requirements from the packet. It previews the exact payload, and then
explicitly requests the live advisory call:

```sh
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-security \
  --request req_RETURNED_ID --attempt attempt-1 --input security-input.json --dry-run
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-security \
  --request req_RETURNED_ID --attempt attempt-1 --input security-input.json --live
```

If the result says `security-follow-up-required`, or the boundary marks the task
security-sensitive, a separate human/frontier reviewer completes the returned
review template with evidence-backed findings. Submit the detailed local document
with `workflow-review --security-findings security-findings.json` or the matching
`observe` option. Findings must be recorded before acceptance. Jev probabilities
do not set finding severity or disposition. Confirmed mandatory delivered
findings block acceptance; unresolved findings require `accept-with-limitation`
or `handoff`. Detailed prose remains in the hash-bound local findings file while
the outcome ledger stores allowlisted metadata.

The helper independently reloads the outcome and verifies its decision,
configuration, artifact, attempt kind, native run, required gates, scores, and
critical-defect veto. A reviewed accepted attempt changes the request to
`accepted` immediately. Do not wait for a comparison before delivering the
accepted artifact; cancel only a run the coordinator owns. No workflow event
integrates or merges a patch.

## Failure, reconciliation, and recovery

Use a stable reason code for a native execution failure. A repair needs an
explicit findings hash from a real review; it retains the failed attempt and
creates at most one repair for that configuration.

```sh
cat > /tmp/failed.json <<'JSON'
{"id":"event-005","type":"execution-failed","attempt_id":"attempt-1","reason_code":"native-tool-failed","repairable":true,"findings_hash":"fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"}
JSON
python3 "$SKILL_PATH/scripts/pilot.py" --root .ultra-delegation/pilot workflow-event \
  --request req_RETURNED_ID --input /tmp/failed.json
```

If launch status is uncertain, do not dispatch again. Verify the native host
first. Use `launch-not-started` only after it confirms no run exists; this returns
the reserved attempt to `planned` once. Repeated reconciliation hands the request
to the coordinator instead of creating an unbounded launch loop.

```json
{"id":"event-006","type":"launch-not-started","attempt_id":"attempt-1","reason_code":"host-confirmed-absent"}
```

`cancel` records an owned canceled attempt with a reason code. Canceled attempts
are neither accepted nor failed and do not trigger replacement work. When an attempt is rejected or fails, existing
initial comparison work is allowed to finish before more recovery spend. Then the
workflow chooses one targeted repair when eligible, otherwise the next never-used
eligible configuration. With no eligible route left it becomes
`coordinator-required`.

The acceptance contract never changes during recovery. Before a fallback
recheck, only `context.observed_at` may be refreshed in the packet; all other
contract fields must remain identical. A stale or unavailable candidate, changed
policy, foreign evidence change, failed guard, changed configuration, or expired
context stops the native dispatch and requires a new decision or coordinator
action.

When material findings require a new Jev decision, prepare and preview a fresh
packet, then run `route --live`. Use `workflow-replan --request req_RETURNED_ID
--decision dec_NEW_ID --input packet.json` to attach the saved decision to the
same settled request. Requirements, user choice, native host/provider, policy,
and limits remain fixed; discovered candidates may expand and review gates may
become stricter. Old attempts retain their own decisions. Replanning does not
reset repair limits or retry configurations already exhausted.

Workflow locks are released by the operating system after a coordinator crash.
If outcome publication was interrupted during optional paid evaluation, resume
`observe` with the same independently reviewed outcome. It records the evaluator
as unavailable with unknown cost instead of repeating a potentially paid call.
Completed outcomes remain immutable; duplicate submissions do not call Jev.

Check each returned configuration before launching. A batch can contain different
models and efforts even when earlier decisions used the same pair. Group only
matching configurations into a native invocation, and record actual accepted
host controls. Never copy a planned configuration into telemetry for a different
worker. Host configuration identity does not establish immutable model weights.

Experimental security bands can be changed with `configure --security-investigate 0.20 --security-strong 0.80 --security-sufficient 0.80`. Changing bands does not enable screening or artifact sharing. Known concerns on an unchanged artifact still require independent disposition; a changed policy cannot erase them.
