# Jev rebuild checkpoint — 2026-09-28

Baseline: `c77a373` (newer pilot lineage), implementation branch
`codex/jev-minimal-router`. Original checkout at `e2be4e7` remains untouched.

Recoverable, ignored project-local snapshots live in
`.ultra-delegation/rebuild/snapshots/`: all-refs.bundle, original-dirty.patch,
original-status.txt, refs.txt, and archives of the choice runtime, campaign,
both trial trees, original dist and releases. manifest.json records source paths
and SHA-256 hashes. They contain historical evidence, not clean training labels.
No Eva seed exists in this checkout. Cortex tools are unavailable in this chat.

The active replacement will be one skill and one Python helper exposing route,
record, report. Task contracts remain general. Native execution, permissions,
review and integration belong to the coordinator. The helper never launches a
worker or treats a routing response as execution. Test fixtures and experimental
host capture live separately from the installed skill.

Public Codex app-server `model/list` and `thread/read` establish the host pool:
gpt-6-luna, gpt-6-sol, gpt-5.6-terra all support medium. This coordinator's current
configuration is gpt-6-astra/high. The CLI protocol schema (0.156.0) exposes
thread/tokenUsage/updated with cumulative input, cached input, output, reasoning
output, cache-write input and total counts. Native dispatch and a measured
recovery still need to demonstrate end-to-end reconciliation. A public metadata
read is not per-turn inference telemetry. No private session stores were read.

API sources checked: https://docs.typesafe.ai/api,
https://docs.typesafe.ai/primitives/choice,
https://docs.typesafe.ai/models,
https://docs.typesafe.ai/cookbooks/function_calling,
https://developers.openai.com/codex/app-server.

The existing configured TypeSafe credential locator was found in the surviving
trial policy. Its lifecycle remains user-owned; only that configured entry or
TYPESAFE_API_KEY may be read. Keys must never enter artifacts or output.
