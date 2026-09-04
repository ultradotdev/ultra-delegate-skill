# Compatibility: 1.2.0-beta.1

Status applies to this release, not every future host/model revision. A successful helper test is not a successful host execution test.

| Surface | Status | What is established | Remaining qualification |
| --- | --- | --- | --- |
| Python helper on macOS, Python 3.14.6 | Verified within test scope | Standard-library bookkeeping, resource policy, clean packaging checks | Other Python versions await CI; see [qualification](qualification.md) |
| Codex native remote workers | Experimental | Host instructions and configuration example | Clean-context code-change, model/effort comparison, and learning reuse on recorded host version |
| Claude Code native remote workers | Experimental | Documented custom subagent template | Actual host execution and available effort controls |
| OpenCode remote workers | Experimental | Documented subagent template | Actual host execution, configured provider, and variant controls |
| OpenCode local models | Unsupported | Local policy defaults to disabled; conservative preflight contract | Enforced monitor, scoped cancellation, bounds, lease, and successful bounded task |
| Direct Ollama or other cross-runtime adapter | Unsupported | No automatic runtime switch | Separate explicitly enabled adapter work |
| Cortex integration | Experimental | Sanitized records can enter shared ranking/reporting | End-to-end graph read/write and recommendation trace |

Capability states have different meanings: **configured** means a setting exists, **discovered** means the active host reports it, and **exercised** means a recorded run used it successfully. `doctor` cannot transform supplied claims into execution proof.

Every verified row must link a sanitized qualification artifact containing release hash, host/runtime version, model revision, native thinking setting, gates, outcomes, and measurement provenance. Partial success should describe the exact exercised behavior, not upgrade an entire provider.

Context guards are cooperative. They evaluate supplied observations and cannot interrupt a host that stops invoking the model. Local policy checks likewise do not supervise processes: without an enforcing runtime integration, local routes remain unsupported even if the machine appears to have ample memory.
