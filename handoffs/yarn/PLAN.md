# Yarn implementation and native pilot plan

## Current handoff status

Use active routing without a qualification-count or routing-shadow gate. The
limited live routing validation is not evidence for this Yarn consolidation: v4
wording returned `clarify` for 12/12 requests; with the same task data and a
two-question v5 wording revision, 11/12 returned `route` and one returned
`no-suitable-candidate`. The bundle's [validation](../../docs/active-recovery-validation.md)
and [results](../../docs/active-recovery-results.json) record 11 accepted native
requests across 12 cards, but their eight native invocations and 23 task attempts
are correlated development batches. Security/artifact judges were off and full
worker/review costs are unknown. Treat the following trials as new, independently
reviewed repository work.

## Establish the application

Inspect both source versions and record actual refs, framework, entry points,
flows, persistence, integrations, test commands, and deployment boundaries. Build
a behavior matrix for keep/reconcile/replace/defer decisions. Confirm the current
baseline checks before changing it. Implement one small end-to-end consolidation
slice at a time; architecture and final product choices remain with the
coordinator.

## Integrate the pilot boundary

Wrap the bundled Python CLI or module in a narrow local service boundary using
argument-based subprocess calls and JSON. Keep state under the selected project
root. Handle missing Python, unavailable Jev, stale discovery, failed native
recheck, and coordinator-required recovery honestly. Never substitute a provider
API or pretend the bundle dispatches workers.

| Boundary | Responsibility |
| --- | --- |
| Yarn settings | Active/off policy, summary sharing, separate artifact sharing, credential locator, advisory checks |
| Packet preparation | Task contract, explicit structured boundaries and authorization, exact host discovery, candidates, tools, capacities, and acceptance gates |
| Pilot | Eligibility, one Jev routing batch, ordered routes, persisted workflow, metadata learning, reports |
| Coordinator/native host | Per-attempt recheck, isolated tool execution, native run/checkout/base record, artifact custody |
| Independent review | Project tests, scope/quality review, critical-defect finding, authoritative outcome |
| Integration | Reconcile selected artifact, merge only after normal review, final acceptance and release |

## Run real bounded trials

Use the twelve task cards: four code reviews, four regression-test changes, and
four localized bug fixes across independently scoped groups. First run the work
needed to make each card meaningful in the actual repository. For every trial:

1. Prepare a real non-synthetic packet from fresh native discovery and an
   immutable acceptance contract. Write scope-specific allowed changes/actions,
   protected behavior/data, coordinator decisions, security requirements,
   authorization, and security sensitivity; inspect the generated worker contract.
2. Route it with active sharing enabled and `--live`, then start a workflow.
3. Obtain its planned action and per-attempt recheck; reserve `launching`.
4. Call the native tool in an isolated checkout and record the actual run ID,
   configuration, base revision, checkout hash, and artifact hash.
5. Run declared tests and independent review. Security remains off unless
   separately enabled. If enabled, dry-run the artifact-bound security payload,
   then run it live only with artifact-sharing permission. Independently review
   and submit required findings before the bound outcome can be accepted; emit
   `reviewed` only after publication.
6. Let one concrete repair or an eligible fallback proceed when needed. Preserve
   the original contract, failures, and unresolved blocker.

Initial bake-offs may compare two configurations from the ordered pool. A passing
candidate can be delivered without waiting for another candidate; no candidate
patch is automatically integrated. Costs are measured, estimated, or unknown.
Do not treat subscription quotas as a dollar cap or a successful comparison as a
model-only causal result when effort or tools differ.

## Review and hand back

Acceptance requires all mandatory gates, an independent review, required quality
floors, and no critical defect. The helper runs no scanners. Jev security signals
and the blinded judge are advisory, while independent confirmed mandatory
findings affect acceptance and unresolved findings require a coordinator
disposition. Use the
checklist to retain exact command results, artifacts, workers, validators, and
remaining limitations.

Generate the report from the real local ledger. It must distinguish first-attempt,
bake-off, and eventual request success; recovery attempts; pending and
coordinator-required requests; and known versus unknown costs. The simulated test
suite and benchmark fixtures stay visibly separate from real Yarn evidence.

Use the bundled `runtime/ultra-delegation/references/repository-trial.md` for the
current prepare/execute/review flow and configurable efficiency preference.
See `validation/repository-trial-validation.md` for this iteration’s test status.
