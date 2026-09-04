# Host-Native Execution Boundary

## Phase 1 rule

Execute delegation only with the active host's native worker mechanism and models available to the current provider family. Filter eligibility before ranking candidates. An external recommendation can inform future planning but is ineligible for execution.

## Capability discovery

Discover models, worker controls, and thinking settings from the current host at run time. Do not embed a static catalog or fabricate supported effort values. Record both the native value and a normalized budget when one can be mapped safely.

If a requested setting is unsupported:

1. State the host, provider, and missing setting.
2. Offer available host-native alternatives.
3. Preserve the request in the report as unavailable.
4. Do not use an external command, API, adapter, or silent substitution.

## Codex Phase 1

Use Codex-native subagents and supported OpenAI model or reasoning-effort overrides only. Give each worker a bounded task packet and enforce the coordinator's acceptance gates. Treat external runtimes as outside Phase 1 even when installed locally.

## Future hosts and Phase 2

When installed in another host, apply the same current-host/current-provider default. Add external adapters only after explicit per-project enablement and approval for provider crossing.

Direct Ollama integration is a Phase 2 adapter, not a required OpenCode bridge. It must add capability discovery, isolation, restricted tool execution, cancellation, telemetry, privacy policy, and cost handling before becoming eligible for routing.

## Tool policy

Model selection does not expand tool authority. Give a worker only the tools, workspace paths, and side-effect permissions stated in its task packet. Keep external writes and destructive operations with the coordinator unless explicitly approved.
