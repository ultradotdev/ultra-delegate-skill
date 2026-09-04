# Ultra.dev release handoff

Product: **Ultra Delegation**, public beta **1.2.0-beta.1**.

Position this release as an **experimental proof of concept**, not production-ready automation. Link the README warning prominently. The maintainer reports it works in Codex and Claude Code; do not imply exhaustive host/model qualification or guaranteed savings.

Intended repository: [ultradotdev/ultra-delegate-skill](https://github.com/ultradotdev/ultra-delegate-skill). Confirm the repository and release are public before putting download links on the site. This document is copy guidance, not proof of publication.

Suggested description:

> Keep planning and verification with a capable coordinator while delegating bounded work to suitable worker models. Compare models and thinking budgets, record quality and available cost data, and carry verified recommendations between projects.

Highlight portable learning, controlled experiments, honest reporting, and local models excluded by default. Link installation to the README and support claims to the versioned compatibility matrix.

Requirements: Python 3.10+, a supported agent host, and access to that host's models. MIT licensed. Cortex is optional. Pricing and latency depend on the host and models; no universal savings percentage is established.

Limitations for launch copy:

- Codex and Claude Code have maintainer-reported working use; detailed host/model combinations remain experimental. OpenCode has no confirmed execution report for this release.
- The deterministic helper does not launch models or connect directly to provider APIs.
- Local OpenCode execution is unsupported until monitoring, scoped cancellation, bounds, and resource checks are exercised. Direct Ollama is deferred.
- Context guards depend on host observations and cannot recover a host already trapped in pre-sampling compaction.
- Privacy filters do not guarantee that every secret is detected in arbitrary free text.

Use the final qualification report and archive SHA-256 when announcing the release. Website implementation, publishing, and video production are separate workflows.
