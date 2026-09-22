# Executable repository benchmark

Use `scripts/pilot_fixtures.py` for the shipped 12 real coding exercises. The older
`pilot_benchmark.py example` remains a routing-template diagnostic, not this suite.
The new helper never launches workers, compilers, tests, or API calls. The agent
runs native tools and records observed outputs. Python 3.10+ is sufficient for
bookkeeping; language checks require local Python, Node >=22.18, Go >=1.20, or Rust.
All exercise dependencies are standard-library only. Missing tools stay pending.

## Materialize and review a task

```sh
python3 "$SKILL_PATH/scripts/pilot_fixtures.py" list
python3 "$SKILL_PATH/scripts/pilot_fixtures.py" materialize \
  --fixture python-ranges --directory /tmp/repository-trial/python-ranges
```

The resulting `worker/` has starter files and `TASK.md`. Give only that directory
to the native worker. The sibling `evaluator/` has checks, reference fixes,
mutants, reference findings, and evaluation instructions. Keep it out of the worker
packet. Each exercise has a content-hashed starting revision and fixed contract;
also record the actual isolated checkout commit in normal pilot workflow events.

Implementation exercises must pass frozen checks plus independent review. Test
exercises must pass on the correct implementation and kill every seeded mutant;
compilation failures/timeouts/toolchain failures do not count as kills. Review
exercises score distinct supported findings against references: missing findings
reduce recall and unsupported or duplicate findings reduce precision. A reviewer
maps free-form findings to reference IDs; the helper cannot independently establish
that the reviewer is independent or that their mappings are correct.

`score --input review.json` accepts an independent review record as described in
the materialized evaluator README and returns acceptance plus mutation or finding
metrics. Scope failure, critical defects, or reviewer rejection veto acceptance.
Security scanning is optional; absence of a scanner is not proof of security.

## Paired Epoch campaign

`prepare --input manifest.json --index capability-index.json --output campaign.json`
freezes the policy, exact native reference configuration, packets, evidence,
fixture contracts, and runtime question/policy versions. The manifest has `policy`,
`reference_configuration_id`, and `cases`. Each case has `fixture_id`, a native
`prepared_packet`, and `evidence`. Packet task/group IDs, summary, and requirements
must match the exercise. Use the normal native packet builder with fresh host
observations and without appended Epoch descriptions for the control input.

The helper creates two packets per case: `without_epoch` preserves the supplied
packet; `with_epoch` appends only Epoch claims from the index. Everything else,
including candidate identities, effort, policy, task, and starting evidence, stays
fixed. All candidates use one effort and native host/provider. Candidate hints and
non-Epoch descriptions remain identical between arms. No evaluation-case outcome
may enter frozen routing evidence, and evidence must predate the packet.

1. `route-input --campaign FILE --fixture ID --arm without_epoch|with_epoch`
   returns the prepared packet, policy and frozen evidence. The coordinator calls
   the existing live router using these inputs and the approved sharing policy.
   Keep campaign records separate from the normal project learning ledger.
2. `record-decision --campaign FILE --fixture ID --arm ARM --input DECISION
   --output NEXT` records one actual inference response. It validates input,
   policy, evidence, question, payload and saved-decision hashes; retries of the
   identical record are idempotent. No shadow dispatch or qualification gate is
   introduced into ordinary skill use.
3. `execution-plan --campaign FILE --fixture ID` returns distinct model runs for
   both recommendations and the fixed reference. Identical task/configuration
   runs are shared explicitly, never counted as independent replicates. If only
   one configuration remains, a deterministic rotating challenger is added.
   The plan does not authorize dispatch: refresh/recheck actual host eligibility
   immediately before native execution through the normal skill workflow.
4. `record-observation --campaign FILE --input OBSERVATION --output NEXT` records
   actual independently reviewed results, latency and all cost components. The
   observation contains fixture/configuration/attempt IDs, attempt kind, raw
   score record, latency_ms, and preparation/worker/review/retry/fallback costs.
   Every cost is `{ "usd": null, "kind": "unknown" }` unless actually known;
   kinds `measured` and `estimated` remain distinct. Repair/fallback observations
   preserve earlier failures. Repeated identical attempts are idempotent.

Commands that change a campaign write a new snapshot with `--output`; keep the
latest snapshot as the input to the next command. Existing files are never
silently overwritten. Users need not author these files; the coordinating agent
prepares them from the task, host observation and observed validation.

## Development, threshold freeze, and held-out testing

Six development and six test fixtures are assigned before execution. Every
language and every work type occurs in each split. The fixture families are parser
or state/error fixes, test writing against seeded mutations, and concrete reviews.
The splits use distinct tasks, not renamed copies of a task.

` sweep --campaign FILE` replays saved development inference at 0.80, 0.85, 0.90,
and 0.95 for operation_match, reasoning_fit, code_interaction_fit, and
context_synthesis_fit. All other thresholds and inputs stay fixed. It uses only
actually observed worker results for the chosen configuration; missing outcomes
remain pending. Replay makes no additional service requests, and reused outcomes
are correlated observations rather than additional evidence.

Choose the operating threshold from the development sweep, then run
`freeze-threshold --campaign FILE --threshold 0.85 --output NEXT`. All development
routes and selected-threshold worker outcomes must be recorded first. The freeze
binds the development evidence, threshold, and timestamp. Held-out `route-input`
is unavailable until that freeze, and development observations cannot change
afterward. This restriction protects the benchmark, not normal project routing.
Run held-out cases once under the frozen policy; do not tune using their results.

## Report and interpretation

`report --campaign FILE --output-prefix trial/report` writes standalone HTML and
JSON. It shows selected configurations, first-attempt results, eventual fixture
acceptance, recovery counts, observed attempts, timing, and known workload costs.
Eventual fixture acceptance includes fixed-reference runs and is not attributed
to either router arm. The report explicitly marks shared observations.

Workload costs include every recorded worker attempt and both router calls, even
failures. Unknown components keep totals unknown. Estimates remain labeled.
This small suite cannot establish general calibration or savings; it reports
savings as not established rather than treating a cheaper recommendation as money
saved. Controlled failure-injection diagnostics and template simulations must
remain separate from these natural worker results. Completing the benchmark is
not required before using active Jev routing on a new repository task.

The JSON also provides selected-first-attempt versus fixed-reference cost
comparisons when both were actually accepted and all their cost components and
router overhead are known. Differences are labeled counterfactual and measured
or estimated, never realized savings. Separate experiment comparisons/recoveries
stay in the whole-campaign workload. A total is unavailable until both routes and
every planned native run have complete observations for every case; an available
partial observed subtotal is labeled separately. Record shared preparation work
once, not once per arm, and mark unmeasured billing unknown.
