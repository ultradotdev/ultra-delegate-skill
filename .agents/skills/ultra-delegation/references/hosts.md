# Host execution

Read only the section for the active host. Discover controls from that installed host before use; documentation and templates are not availability checks. Preserve provider scope, worker tool authority, explicit model exclusions, and current user preferences.

## Codex

Use native subagents with the selected model and supported reasoning setting. Supply the bounded packet and minimum necessary context. Do not launch a separate CLI as a substitute. If the native tool cannot apply an override, report it unavailable.

The optional `assets/hosts/codex-worker.toml` is a read-only proposal agent. Copy it to the project's `.codex/agents/` only when custom agent configuration is wanted. Discover and set `model` and `model_reasoning_effort` together before a controlled experiment. Unset values inherit host configuration. This template follows the [official custom-agent format](https://learn.chatgpt.com/docs/agent-configuration/subagents); verify the installed version accepts it.

## Claude Code

Use the active session's native Agent mechanism. `assets/hosts/claude-worker.md` can be copied to `.claude/agents/ultra-worker.md`. It limits tools to inspection and inherits the selected session model; select an available model in its configuration for experiments. Check native effort support before recording a thinking comparison. The template uses [documented subagent fields](https://code.claude.com/docs/en/sub-agents). Do not interpret a turn limit as a memory or wall-clock limit.

For skill discovery, use the host's skill installation mechanism or copy this skill directory into `.claude/skills/ultra-delegation/` in the target project. A template worker does not automatically load the coordinator skill; provide the packet explicitly.

## OpenCode

Use a configured native subagent, staying with the current provider. `assets/hosts/opencode-worker.md` is an optional read-only proposal template for `.opencode/agents/ultra-worker.md`. It omits a model so the coordinator must discover and verify the inherited or explicitly selected profile. Thinking variants are provider-specific; record the exact native setting and never guess a mapping.

The template follows [OpenCode's agent format](https://opencode.ai/docs/agents/). Install the skill through the active host's skill discovery mechanism; loading the skill does not prove native delegation works on that installation.

Local endpoints remain disabled by default. For this beta, local OpenCode execution is unsupported until an enforcing integration provides fresh resource observations, limits, a cross-project lease, and cancellation scoped to the owned request. Do not infer these capabilities from OpenCode or Ollama merely being installed. Do not call Ollama directly or start/download a model as a fallback.

## Qualification

Report configured, discovered, and successfully exercised controls separately. Record host version, exact model revision, native thinking setting, gates, and unavailable telemetry. A runtime mismatch requires an eligible native alternative or coordinator fallback, never a silent provider switch. Templates intentionally propose changes without edit/shell authority; expand tools only to match a user's authorized packet.
