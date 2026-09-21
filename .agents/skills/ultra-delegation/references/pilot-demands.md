# Demand-based candidate evaluation

The task questions describe the work. They do not name a model, establish worker
success probability, or grant execution authority. The selector uses their
answers to test individual candidates against independently observed evidence.
This is `pilot-selection-v3`, with generated question contract `pilot-routing-v3`.
The underlying atomic question wording remains unchanged by this correction.

## Corrected flow

1. Apply discovered host, provider, permissions, exclusions, quarantine, risk,
   tools, capacity and context checks. Eligible user choices and pins retain
   their existing precedence and bypass Jev optimization.
2. Ask the same independent questions in one batch.
3. Missing essential requirements, unsupplied coordinator decisions and inferred
   impact conflicts retain their explicit clarification/coordinator branches.
4. Derive a demand profile for reasoning, code interaction and context synthesis.
   Keep the coordinator's authoritative task kind and complexity unchanged.
5. For each shortlisted candidate, check semantic operation/scope fit, reachable
   retrieval tools, and independently reviewed evidence covering the demands.
6. Select an applicable qualified candidate using the existing cost ordering, or
   propose a controlled reviewed trial when suitable candidates lack evidence.
   If all candidates lack required retrieval, return `repackage` with
   `external-information-unavailable`; Jev cannot grant a new tool.
7. Record the decision, applicable evidence and required review checks. Recheck
   before native dispatch. An experiment proposal does not authorize execution.

A high interaction or synthesis probability no longer means “stop because this
routine task is complex.” A high reasoning demand likewise does not select a
provider effort label. Work-kind disagreement appears as a nonblocking
`work-kind-disagreement` diagnostic, preserving the authoritative evidence scope.

## Independent bands and review requirements

Each demand has a separately configurable policy entry:

```json
{
  "demand_bands": {
    "reasoning": {"absent": 0.30, "required": 0.70},
    "code_interaction": {"absent": 0.30, "required": 0.70},
    "context_synthesis": {"absent": 0.30, "required": 0.70}
  }
}
```

Values at or below `absent` are absent; values at or above `required` are required;
values between are uncertain. Both required and uncertain demands require
matching evidence and review. These are experimental operating points, not
calibrated correctness guarantees. The original 0.70 positive boundary is
unchanged. The new explicit uncertainty band prevents an ambiguous demand from
being treated as known absent. Other semantic gates retain their existing
cutoffs and do not claim full independent three-way calibration.

| Demand tag | Signal | Mandatory review gate and meaning |
| --- | --- | --- |
| `reasoning` | Sum of probabilities for the two highest described reasoning levels | `review-reasoning`: independently verify how the deliverable resolves constraints or competing explanations against the requirements. |
| `code_interaction` | Probability of reasoning across functions/components; unused for non-code tasks | `review-code-interaction`: trace relevant behavior across the touched interfaces and check it against tests or source evidence. |
| `context_synthesis` | Probability of combining separated facts | `review-context-synthesis`: check that combined claims accurately reflect the supplied evidence, including relevant contradictions. |

These gates constrain acceptance, not the host's tools or capabilities. For active
recommendations they join the task's predeclared mandatory gates, including for
experiment outcomes. For shadow recommendations they remain separately recorded
advice; the configured baseline's acceptance requirements do not change.

## What counts as evidence

The existing exact configuration, scope, operation, risk, complexity, work-kind,
freshness and independent-group filters still apply. Within that domain, a
successful observation receives positive demand credit only when:

- the independent reviewer explicitly recorded the relevant `reviewed_demands`;
- the corresponding review gates were mandatory and passed;
- existing quality floors and all mandatory gates still pass.

Independence is a coordinator responsibility, recorded through reviewer identity
and human/frontier provenance. The CLI validates those fields and gates; it cannot
prove who actually performed a review. Never treat a worker’s self-score as an
independent assessment.

Outcome forms default to `reviewed_demands: []`. A reviewer may confirm a subset
of inferred demands or add a capability actually exercised. Never fill these
from Jev predictions automatically. An accepted outcome without confirmed tags
remains generic scoped evidence; it does not qualify demand-heavy tasks. Old
observations are not retroactively relabeled. Synthetic review cannot qualify a
real task.

Matching-scope failures are retained conservatively even without demand tags.
A failed group cannot be hidden by adding a successful variant. This deliberately
favors retesting when the available failure evidence is ambiguous. Changed task
acceptance contracts still use the existing compatibility filter.

Active outcomes are admitted only for the selected route or nominated experiment
configurations. A blocked active decision cannot accumulate worker evidence, and
an active comparison must be part of a nominated trial. Off/shadow mode retains
coordinator-owned, independently reviewed comparisons of eligible candidates;
these are labeled `coordinator-reviewed-comparison` and receive demand credit only
with explicit reviewed tags and mandatory gates. Recording an observation never
authorizes execution.

The one aggregate historical cohort card now derives from matching recorded
outcome metadata: scope/operation/kind/risk/complexity, passing and failing group
counts, and reviewer-confirmed demand coverage counts. A new task label alone
cannot create a history card. Exact metadata matching remains the transfer
boundary; this is not free-form semantic retrieval across unrelated task families.
The comparability question is an additional check, not proof of historical demand
coverage. Numeric filtering and group confidence remain in code.

## Reports and versioning

Decisions expose `demand_profile`, `required_demands`, `review_requirements` and
`candidate_assessments`. Each candidate assessment identifies applicable evidence
and whether the candidate is qualified, needs a trial, or was excluded. The
pre-inference generic evidence remains separate. HTML names workers and separates
router advice from effective routing and observed results; hashes/probabilities
remain in the audit details. Action disagreements are counted separately from
recommendations of a different model.

Saved decisions include a selection-policy version. Recheck rejects decisions
from an older rule even if the input file did not change. Reevaluate; do not edit
a saved decision or overwrite past outcomes. The policy, packet and evidence
hash checks remain in place. Question references are generated from the runtime
registry and checked in tests/CI.

## Original-trial replay

Using exactly the original trial payload and recorded Jev answers, the old rule
returned `repackage`: interaction 0.81 and synthesis 0.76 crossed the 0.70 boundary.
The corrected rule proposes reviewed trials for Terra medium and Luna medium,
with interaction and synthesis review gates. Neither candidate had sufficient
prior applicable evidence at that decision. Shadow execution would still retain
the configured Terra baseline.

This is a deterministic counterfactual replay, with no new request, worker run,
accepted outcome or quality claim. It isolates the policy change by holding the
payload and answers fixed. The original actual trial remains recorded as it ran.

## Remaining gaps against the broader design

| Area | Current pilot limit |
| --- | --- |
| Threshold qualification | Bands are experimental. Held-out task groups and downstream outcomes must evaluate unnecessary trials and under-routing. |
| Full-path optimization | Candidate ordering uses available worker/review/retry/fallback cost observations or supplied estimates. It has no complete expected-cost or latency model. Unknown costs remain unknown; a route is not proof of global cost optimality. |
| Semantic transfer | One exact-metadata cohort is supported. Broader historical descriptions, independent retrieval evaluation and cross-scope transfer are not implemented. |
| Uncertainty outside demand signals | Existing missing-requirement, coupling, impact, tool and candidate cutoffs remain; universal per-signal abstention bands are not implemented. |
| Trial execution | Proposals still require coordinator planning, native execution and independent acceptance. Automatic bake-off scheduling is not implemented. |

This correction restores the designed role of demand signals. It does not claim
the full proposed router or its performance has been qualified.
