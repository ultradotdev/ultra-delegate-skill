# Demand signals and independent review

The routing questions describe the submitted bounded task. Their answers help
rank eligible configurations and select review checks. They do not grant worker
authority, prove a model's success probability, create an automatic complexity
stop, or replace independent acceptance.

The active flow is:

1. Apply host/provider, availability, user-choice/pin, exclusions, quarantine,
   risk, tools, modalities, capacity, and delegation-guard checks.
2. Ask the registered routing questions in one batch when live Jev routing is
   enabled.
3. Use reasoning, code-interaction, and context-synthesis signals to describe
   task demands and required review.
4. Select the primary configuration and ordered eligible alternatives, preserving
   an explicit user choice unless the caller explicitly supplies alternatives.
5. Recheck before every native attempt and accept only independent reviewed
   outcomes under the unchanged acceptance contract.

Sparse history is normal. An eligible configuration can be selected immediately;
there is no qualification minimum, promotion checkpoint, or coverage target before
routing. Existing reviewed outcomes influence later ordering and bake-off choices.
Configuration-specific records remain distinct from related evidence; a prompt
contract, native effort, or tool-policy change is a different configuration.

## Demand-to-review mapping

| Demand | Signal | Mandatory review gate |
| --- | --- | --- |
| `reasoning` | Sum of the two highest routing reasoning-level probabilities | `review-reasoning`: independently check how the result resolves relevant constraints or competing explanations. |
| `code_interaction` | Probability of behavior spanning functions or components; not applicable to non-code work | `review-code-interaction`: trace behavior through touched interfaces and tests or source evidence. |
| `context_synthesis` | Probability of combining separate supplied facts | `review-context-synthesis`: verify the combined claims against supporting and contradictory supplied evidence. |

The policy's `demand_bands` map each signal to `absent`, `uncertain`, or
`required`. Required and uncertain demands add the corresponding review gate to
an active decision's immutable acceptance contract. They do not add tools,
authority, source material, or an extra worker call. A route with missing
requirements or unavailable required tools still goes to clarification,
repackaging, or the coordinator.

## Evidence and acceptance

Reviewed learning records are scoped by configuration, task scope, operation,
risk, complexity, work kind, acceptance contract, time, and independent group.
The current task group never supplies its own prior evidence. A failure remains
in its group; a subsequent repair or variant cannot manufacture an independent
success. Canceled comparisons are preserved as canceled.

Positive demand evidence requires the reviewer to list `reviewed_demands` and to
pass the matching mandatory demand gates. Do not copy Jev signals into an outcome.
An accepted outcome without those tags is still scoped generic evidence. Worker
self-scores and Jev judgments are not authoritative acceptance labels.

Acceptance requires the independent reviewer verdict, all declared mandatory
gates, each quality floor, and no critical defect. Critical defects include
materially incorrect behavior, data loss, authorization bypass, secret exposure,
or another result the coordinator finds unacceptable. An optional judge or
security evaluator is advisory and cannot accept its own routed output.

## Recovery implications

A failure records concrete validation findings. At most one repair is planned for
the same configuration when the coordinator supplies a specific findings hash.
Otherwise the workflow uses a never-attempted ordered alternative, rechecking it
against current eligibility. Do not weaken gates, silently change requirements,
or attribute a comparison result to a model alone when effort or tools differ.
See [pilot-workflow.md](pilot-workflow.md) for the event sequence.

Question wording, answer types, and runtime use are generated in
[pilot-questions.md](pilot-questions.md). Versions and hashes support audit and
replay; they are not a claim that current host capabilities or a future provider
revision are unchanged.
