# Current repository-trial iteration: 1.3.0-rc.7

See [RC7 validation](repository-trial-validation.md) for the current status.
The historical RC6 record below describes its original trial; it does not
establish performance of the new questions or selection preference.

# Compatibility: 1.3.0-rc.6

RC6 uses active routing from the first eligible task after project setup; it has
no minimum-observation, qualification, or shadow-rollout gate. The scoped live
routing check recorded 12 of 12 `clarify` actions with question wording v4. With
the same task data and a two-question wording revision (v5), it recorded 11
`route` actions and one `no-suitable-candidate` result.

The [active recovery validation](active-recovery-validation.md) and its
[recorded results](active-recovery-results.json) cover 12 task cards and 11
accepted native requests. Six primary attempts succeeded; three primary failures
were accepted through a comparison, and two required later recovery. One preserves
a coordinator dispatch mismatch corrected to Luna; the other records an A-to-B-to-A
portability defect that Luna fixed after both initial results missed it. The record
contains eight native invocations and 23 task attempts, including the mismatch.
They are correlated development batches, not independent reliability evidence.
Security and artifact judges were off. Worker and review costs remain unknown, so
there is no savings or calibration claim.

The historical entries below describe earlier candidates or host reports. Status
does not generalize to every future host/model revision. A successful helper test
is not a successful host execution test.

| Surface | Status | What is established | Remaining qualification |
| --- | --- | --- | --- |
| Python helper | Current local coverage | 304 tests pass; six optional-keyring archive checks pass | All 304 extracted tests pass with and without optional keyring; consult PR CI checks; not a guarantee of runtime-host behavior; see [qualification](qualification.md) |
| Jev decision adapter | Active pilot; bounded live recovery record | RC6 v4/v5 routing and the recorded recovery outcomes above | Representative task quality, independent reliability, real endpoint cost, calibration, and credential-store coverage |
| Codex native remote workers | Bounded RC6 execution record | Eleven accepted requests under the recorded coordinator workflow | Exact model/effort combinations and general performance remain unqualified |
| Claude Code native remote workers | User-reported working; proof of concept | Maintainer reports successful use | Exact host version, model, effort settings, and performance remain unqualified |
| OpenCode remote workers | Experimental | Documented subagent template | Actual host execution, configured provider, and variant controls |
| OpenCode local models | Unsupported | Local policy defaults to disabled; conservative preflight contract | Enforced monitor, scoped cancellation, bounds, lease, and successful bounded task |
| Direct Ollama or other cross-runtime adapter | Unsupported | No automatic runtime switch | Separate explicitly enabled adapter work |
| Cortex integration | Experimental | Sanitized records can enter shared ranking/reporting | End-to-end graph read/write and recommendation trace |

Capability states have different meanings: **configured** means a setting exists, **discovered** means the active host reports it, and **exercised** means a recorded run used it successfully. `doctor` cannot transform supplied claims into execution proof.

Every verified row must link a sanitized validation artifact containing release
hash, host/runtime version, model revision, native thinking setting, gates,
outcomes, and measurement provenance. “Qualification” in historical material
describes its old evidence record; it is not an RC6 routing prerequisite. Partial
success should describe the exact exercised behavior, not upgrade an entire
provider.

Context guards are cooperative. They evaluate supplied observations and cannot interrupt a host that stops invoking the model. Local policy checks likewise do not supervise processes: without an enforcing runtime integration, local routes remain unsupported even if the machine appears to have ample memory.
