# Complete the Codex Jev router with recovery and continuous learning

## Summary

Finish the Python implementation as a complete Codex workflow: prepare a task, use Jev to select native workers immediately, validate their results, recover automatically from unsuccessful attempts, learn from reviewed outcomes, and explain the complete request through HTML and JSON reports.

The initial workflows are bounded code reviews, targeted test changes, and bounded bug fixes. Jev becomes active on the first run after project setup. An eligible worker does not need prior local successes before it can be selected.

This plan supersedes the earlier qualification-first design. Remove routing shadow mode, validated promotion checkpoints, minimum observation counts for dispatch, and statistical failure-rate or coverage targets as release gates. Versions remain for traceability, replay, and compatibility. Benchmarks measure performance without becoming prerequisites for ordinary routing.

The success criterion is an accepted result for the user's request, not merely a completed worker call. A failed attempt starts recovery. Requirements and acceptance criteria stay fixed throughout recovery. Genuine blockers or exhausted viable approaches must be reported clearly; the workflow must not promise that every task is solvable or retry indefinitely.

## Implementation

### 1. One authoritative router, active from the outset

Consolidate runtime behavior around the current pilot, reusing the offline ranking, read-only credentials, secure transport, and response validation components. Retire the earlier Jev router as an active implementation while preserving historical records and useful fixtures.

The primary flow is:

**Hard checks → shortlist → one Jev batch → select primary and alternatives → execute → validate → recover if needed → accept → learn.**

- Preserve hard checks for availability, host/provider scope, effort, tools, modality, permissions, exclusions, quarantine, context fit, and lifecycle stops. Recheck before every dispatch, including repairs and fallback workers.
- Preserve eligible user choices and project pins. Recovery cannot silently override an explicit model restriction; use permitted alternatives or return the conflict to the coordinator.
- Ask independent atomic questions in one batch about task demands, missing requirements, coordinator dependencies, candidate operation/scope fit, and relevant history when available.
- Demand signals guide candidate suitability and required review. They must not become blanket complexity vetoes. Sparse or absent history is normal and must not itself force an experiment-only action or block routing.
- Code combines Jev's answers into a primary configuration, ranked alternatives, reasons, and review requirements. Prefer suitable economical options when costs are comparable; unknown costs remain unknown and use a declared fallback preference instead of a cheapest-route claim.
- Missing essential requirements, unavailable tools, or an actual coordinator dependency can still require clarification or repackaging. Jev cannot grant authority or change acceptance criteria.
- A Jev service failure is recorded explicitly and hands the original ranking to the coordinator/offline path. It is not evidence that a worker is unsuitable and must not silently end the request.
- Generate question wording, payload examples, applicability, and signal-to-decision documentation from the runtime registry. CI checks drift and unused signals.

The configured workflow has an offline option and active Jev routing. There is no routing shadow rollout stage. Diagnostic replays remain clearly labeled as replays.

### 2. Native execution and automatic recovery

Add a resumable execution protocol around native Codex tools. Python prepares and validates plans; the coordinating agent launches native workers and records the actual execution. Use isolated worktrees for edits and comparisons.

Separate request state from attempt state. A request remains in progress while recovery is possible. Each attempt records its parent request, decision, configuration, base revision, artifact hashes, validation, reviewer, usage availability, elapsed time, and whether it was initial work, a comparison, repair, or fallback.

When an attempt fails:

1. Classify the failure and retain concrete validation findings. Distinguish an output defect from a transient execution problem, incomplete output, scope violation, or missing requirement.
2. Use an already accepted bake-off result if one exists.
3. Allow at most one targeted repair on the same configuration for a specific fixable defect. Supply the findings and unchanged acceptance contract. Do not blindly rerun the same failed inputs.
4. If repair is inappropriate or unsuccessful, move to an eligible alternative. Higher native effort is a distinct configuration and must be supported by discovery.
5. Ask Jev again when failure evidence materially changes the task assessment. Otherwise use the prepared fallback order without an unnecessary inference call.
6. Escalate to coordinator execution or repackaging when viable alternatives are exhausted. Report a real blocker if completion cannot proceed.

Revalidate repaired artifacts independently. Do not weaken tests, hide failed attempts, or count eventual acceptance as first-attempt success.

Make dispatch/resume idempotent, reconcile uncertain launches before creating duplicates, and cancel only owned runs. Keep integration, merging, publication, and final acceptance with the coordinator. Preserve the explicit native host-managed-output option without inventing token ceilings, immutable model revisions, usage data, or sandbox guarantees.

### 3. Bake-offs improve delivery and learning

Retain automatic bake-offs as part of the configured workflow. The default comparison runs two eligible configurations from the broader pool in isolated workspaces, against the same requirements and acceptance checks. The pair can change on every task; this does not restore a permanent two-model strategy.

- Use comparisons especially on cold starts, competing recommendations, recent failures, and promising alternatives. Routine tasks with useful, consistent history may use one worker while retaining fallbacks.
- Run comparison workers concurrently when the host supports it; otherwise run sequentially.
- If one candidate passes and another fails, deliver the accepted result. An unsuccessful comparison does not make the request unsuccessful.
- A running comparison must not unnecessarily delay an accepted result. Finish it only when useful for learning within project limits; otherwise cancel it and record it as canceled, not failed or accepted.
- If multiple results are accepted, prefer stronger reviewed quality, then lower comparable full-path cost. Never merge incompatible candidate patches automatically.
- If none passes, continue the recovery loop using the observed failures.
- Distinguish whole-configuration comparisons from single-variable experiments. Do not attribute a result solely to model quality when effort or tools also changed.

Project attempt, concurrency, and elapsed-time limits are optional. Dollar ceilings require enforceable information; estimates and unknown native usage cannot satisfy them. Budget configuration is not a prerequisite or a new approval workflow. Exhausted limits hand the request back to the coordinator with its current artifacts and findings.

### 4. Broad evidence and immediate learning

Ship a versioned standing catalog intersected with current native discovery. Build a shortlist with baseline, economical, specialist, fallback, and rotating challenger roles. Default to eight candidates, maximum twelve, within the existing payload bound. Catalog descriptions are initial capability hypotheses, not demonstrated performance.

Use broad history categories: review, tests, and implementation. Retrieve relevant examples using task-demand tags rather than creating mandatory qualification buckets for every combination of risk, complexity, prompt, tool, and model setting.

- Keep exact worker configuration and provenance in every record. Present configuration-specific results alongside relevant related history, identifying transfer assumptions rather than pretending configurations are identical.
- Use independent reviewed outcomes immediately in subsequent candidate summaries, shortlist ordering, and comparison decisions. There is no promotion checkpoint or minimum success count before routing.
- Keep Jev proposition probabilities separate from observed success rates, evidence volume, and uncertainty. Neither is a correctness guarantee.
- Preserve failures, repairs, canceled comparisons, and unresolved attempts. Linked retries and variants must not manufacture independent successes.
- Treat prompt wording versions as audit metadata. Material changes to the execution contract, tools, or capabilities affect relevance; they do not automatically make every model unusable until requalified.
- Support audit, correction/retraction, quarantine/retest, and sanitized import/export. Label imported results and their provenance. Worker self-scores and Jev judgments cannot become authoritative success labels.

Local learning uses the tool's own ledger. Do not automatically scan or send repository files or conversation history.

### 5. Acceptance, judging, and security

Acceptance requires passing mandatory tests and scope checks, independent coordinator/frontier review, the declared quality floors, and no critical defects. Review coverage, correctness, maintainability, and clarity. Missing review remains pending.

Critical defects include materially incorrect behavior, data loss, authorization bypass, secret exposure, or another defect that makes the deliverable unacceptable regardless of its average score. Tests passing alone do not establish full acceptance.

Retain optional Jev artifact evaluation as an advisory aid to reviewing and comparing outputs. It is separate from routing and requires artifact-sharing permission. Blind worker identity and price, pin the rubric/model within comparisons, and support insufficient evidence. Jev cannot accept its own routed worker's result or supply its own ground truth.

Keep the optional security evaluator off by default and advisory. Distinguish disabled, unavailable, insufficient evidence, and findings. Its unavailability does not break ordinary execution; a confirmed critical security defect still blocks acceptance and triggers recovery. Do not label unevaluated outputs secure.

## Telemetry and practical evaluation

Use a single versioned report model for HTML and JSON. The first screen explains the task, Jev's recommendation, actual workers, acceptance results, recovery sequence, final request outcome, and what changed for future routing. Keep probabilities and hashes in expandable audit details.

Report these separately:

- First-attempt success: whether the primary selection passed without repair or fallback.
- Bake-off success: whether an initial comparison produced an accepted result, including when the primary failed.
- Request success: whether the full workflow eventually delivered an accepted result.
- Recovery overhead: extra attempts, review, time, and available costs before acceptance.
- Quality and security findings, unresolved requests, reviewer disagreement, and measurement completeness.

Include preparation, routing, all comparisons, workers, review, repairs, and fallback in workload accounting. Keep measured, estimated, and unknown costs distinct. Counterfactual savings require separate labeling from actual paired observations and realized savings.

Default shareable reports contain sanitized metadata. Rich local explanations or selected excerpts require explicit inclusion. Preserve existing payload limits, credential redaction, and separate routing/artifact-sharing permissions.

Replace the legacy Noul-only benchmark path with a programmatic harness for the actual Choice/Score/Noul pilot. Start with twelve real end-to-end tasks, four in each broad category, plus deterministic fault-injection fixtures for recovery and boundary behavior. These establish workflow behavior, not population-level reliability.

Compare with offline and fixed-worker baselines where actual paired executions exist. Add threshold experiments and independent property labels on a small development/held-out split; keep related variants together and prevent future outcomes from leaking into routing history. Record the order of decisions and observations so changing shortlist behavior can be replayed chronologically.

No hundreds-of-observations campaign, certification threshold, or minimum routing-coverage target gates use or release. Report the actual sample size, limitations, observed performance, and uncertainty. Produce standard HTML/JSON reports and exportable charts suitable for repo trials and the video.

## Verification and delivery

Add specification, unit, integration, and live workflow checks for:

- Immediate routing with an empty history and a new eligible configuration.
- Demand-heavy work choosing a suitable worker without a blanket complexity stop.
- Hard constraints, user choices, pins, changed inputs, dispatch rechecks, and unavailable Jev.
- Primary failure with comparison success; both candidates failing followed by successful fallback; targeted repair success; repeated repair failure causing escalation.
- Unsupported fallback effort, incomplete output, scope violations, genuine blockers, optional limits, cancellation, duplicate events, and resumed requests.
- Acceptance criteria remaining unchanged through all attempts, with critical-defect vetoes and independent review.
- Outcomes affecting the next task without qualification gates; failure-preserving history and no future-data leakage.
- Optional judges/security checks remaining advisory, including adversarial excerpts and candidate-order swaps.
- Reports distinguishing first-attempt, bake-off, and eventual request success, with correct denominators and unknown costs.

Run the full existing suite, generated-document checks, Python 3.10+ compatibility, and reproducible extracted-package tests with and without optional keyring. Update skill instructions and examples to match the new active-routing and recovery behavior; remove obsolete qualification and routing-shadow guidance from the active workflow while preserving historical records as historical.

Implement through reviewable feature branches and PR/CI: routing and evidence simplification; execution and recovery; bake-offs and acceptance; reporting and practical trials; packaging. Preserve unrelated working-tree changes. Do not modify the installed skill or publish automatically.

Defaults remain Python and Codex-native execution, explicit project setup before external calls, separate sharing permissions, and mandatory coordinator acceptance. Read existing credentials only, environment first then the configured secure-store entry. Never create, change, delete, migrate, or prompt for Keychain values. Other execution providers and a Rust rewrite remain outside this iteration.

Rebuild the Yarn handoff package from the verified release candidate with setup, example task packets, native execution/recovery instructions, review criteria, report generation, and the actual test results and limitations. The agent in the Yarn repository should be able to route its first bounded task immediately and continue toward an accepted result if its first worker fails.
