# Yarn implementation and test-drive plan

## 1. Establish what is being consolidated

Inspect both implementations and identify the actual language/framework, entry points, user flows, persistence, integrations, test commands, and build/deployment boundaries. Record source refs and a behavior matrix: keep, reconcile, replace, defer, with a concrete reason and verification method. Do not assume the two versions use compatible data models or that the newest UI is the desired product.

Create a working branch or isolated checkout according to the repository's practices. Confirm the baseline builds/tests before changing it; record existing failures rather than attributing them to consolidation. Prefer a small end-to-end product slice before a broad migration. Ask the user only for product choices or missing sources that the repo and prior instructions cannot resolve.

## 2. Establish the delegation boundary in Yarn

Integrate the bundled pilot as a versioned local CLI or Python module behind a small service boundary consistent with Yarn's architecture. Prefer argument-based subprocess invocation and JSON serialization over shell command strings. Keep filesystem paths under the selected project's state root and handle structured errors, missing Python, and unavailable Jev without breaking ordinary work.

Separate these responsibilities:

| Boundary | Responsibility |
| --- | --- |
| Yarn project settings | Routing off/shadow/active, read-only credential locator, summary/artifact sharing, optional advisory security |
| Task preparation | Explicit task, requirements/gates, safe summary, actual host capabilities and exact candidates |
| Pilot | Deterministic eligibility, batched judgments, recommendations, evidence matching and report generation |
| Host execution | Native worker dispatch after `recheck`, isolated trials, collecting output and usage |
| Independent evaluation | Project tests/gates and human/frontier review, recorded separately from worker identity |
| Reporting | Effective versus suggested routes, paired outcomes, quality, security status, costs and pending observations |

The shipped pilot has no provider-execution service and does not make a browser app into an agent host. If Yarn cannot access native worker tools at runtime, implement the preparation/review/report interface and an explicit handoff to its supported host. Mark runtime dispatch unsupported until an actual host integration exists. Do not quietly substitute a different provider API or build a local inference adapter.

Keep provider keys in the existing user-controlled server/local credential environment. Use a credential availability indicator, not a text field that manages keychain entries. Make artifact sharing distinct from summary sharing. Security controls should explain advisory/not checked/unavailable states. User-facing product screens need task status, useful decisions and review results; low-level hashes and diagnostic internals belong in diagnostics/export.

The exact commands and schemas are in `runtime/ultra-delegation/references/pilot.md`. They are authoritative over illustrative worksheets. The generated question contract shows what is asked and which code paths consume each answer. Avoid inventing flags or treating an experiment nomination as a dispatchable route.

## 3. Use consolidation tasks as the first observed workload

Select real, bounded work across the inventory, using `templates/task-cards.json` as a worksheet. Useful starting families are component behavior comparison, localized patch proposals, regression-test additions and independent patch review. Architecture and acceptance decisions stay with the coordinator. Work outside the pilot's risk or capacity settings stays with the coordinator or must be repackaged; do not lower declared risk to make routing succeed.

Discover available configurations on the actual current host/provider, including supported effort, tools/modalities, resolved revision and input/output capacity. The shipped catalog contains discovery hints, not qualifications. Choose an explicit eligible baseline. Start shadow mode after summary-sharing is enabled for this project and run only explicitly prepared, sanitized packets.

For early scoped comparisons, run the baseline and selected challengers on the same task with the same acceptance contract, tools and input. Isolate writes and collect results before integration. Compare one controlled configuration change at a time where possible; record changed factors if the broader comparison is across composite configurations and avoid causal claims about one factor. Use normal project authorization and budget limits. Jev nomination does not itself authorize extra executions.

Review outputs independently using predeclared gates and the four pilot dimensions: coverage, correctness, maintainability, clarity. Record failures, retries and recovery work as well as successes. A same-task comparator must reference the same saved decision to appear as a paired comparison. Generate an outcome template per evaluated configuration and fill it from observations. Unknown costs stay null, not zero; allocate shared preparation once. Observe records are exclusive, so collect the complete review before submitting.

Reuse learned evidence only within the matching scope/operation/risk/complexity/work-kind and configuration contract. Early bake-offs provide comparisons; later runs can concentrate extra comparisons on uncertainty, changed capabilities, failures and periodic audits. Scheduling is manual in this pilot. Do not treat its default thresholds or a small workload as calibrated production guarantees. Reserve distinct future task groups for evaluation before tuning settings; the older benchmark cannot directly qualify the v2 pilot's questions.

## 4. Security is optional and explicitly bounded

Leave the new security evaluator off initially. Preserve existing project-required gates. If requested, define relevant requirements from the actual changed code and trust boundaries, select excerpts explicitly, enable separate artifact-sharing permission, and use `observe --security-check` with the documented security packet. The check is advisory even when enabled. Report unavailable or indeterminate honestly; do not claim that a passing excerpt assessment proves the whole app secure.

## 5. Produce the handback

Deliver the consolidated app slice and its tests, with a concise reconciliation record. Include the implemented delegation integration and any remaining native-host boundary. Export HTML and JSON from real runs, identifying synthetic fixtures separately.

The handback should show quality/gate results, scoped evidence counts, effective and suggested decisions, actual paired comparisons, optional security coverage, router/worker/review/retry/fallback cost coverage and latency. Incomplete completion or cost data must stay explicit. Do not present avoided runs as realized savings or claim total cost per accepted task when the denominator/workload is incomplete.

Use `templates/acceptance-checklist.md` to record which app and pilot checks actually passed. Do not close the whole consolidation merely because the offline demo or one slice passes. Keep the remaining product migration work explicit.
