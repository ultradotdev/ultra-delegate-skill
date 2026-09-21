# Yarn consolidation agent handoff

You are working in the Yarn repository. Consolidate the versions described by the user as the **GPT-6 version** and the **Fable 5.1 version** into one app, with the Ultra Delegation pilot integrated. These names identify source app versions; they are not discovered worker model IDs. This bundle contains the router and its operating contract, not either Yarn codebase.

Read this file, `PLAN.md`, and `RUNBOOK.md`. Then inspect the repository's own instructions, current changes, and both versions. Locate the versions from actual branches/directories/history; do not infer paths or reset existing work. If one cannot be located, ask for that specific missing location and continue investigating the available version.

## Intended result

Produce one coherent Yarn app that preserves the agreed useful behavior from both versions and supports delegation through an explicit application boundary. Use the bundled Python pilot first. Keep its versioned JSON boundary so the implementation can move to Rust later if that becomes worthwhile.

The app's architecture, feature decisions, integration, independent review, and final acceptance remain yours as coordinator. Delegate bounded work through the current agent host's native worker tools. Jev provides routing judgments; it does not run workers. Never claim cross-provider execution, an implemented runtime dispatcher, security certification, or savings that the bundle does not provide.

Begin with a concise inventory and a consolidation plan grounded in the actual code. Choose the first end-to-end slice, specify acceptance checks before dispatch, and implement incrementally within the user's repo task. Do not stop after writing the plan when the necessary inputs and authorization are already present. Preserve unrelated changes and follow the repo's commit/PR practices. Deployment or publication is not implied by this handoff.

## Decisions already made

- Python 3.10+ for the first iteration; no Rust rewrite now.
- Use `runtime/ultra-delegation/scripts/pilot.py`, not the older `jev.py` router for this pilot. Runtime source and the matching test source ZIP are included.
- Broader discovered candidates, deterministic capability checks, then one Jev batch of explicit task and candidate questions. Start with shadow recommendations against an explicitly chosen baseline.
- Learn from independently reviewed, scoped outcomes. Compare real baseline/challenger results to test routing choices. Keep task variants in one independent group. Do not confuse Jev proposition probabilities with worker success rates.
- Prompt wording versions are audit metadata. Material instruction-contract or tool-policy changes separate learned evidence.
- Security evaluation is optional, off by default, and advisory. Its failure must not break normal outcome recording. Existing mandatory project/security tests still apply.
- Credential lifecycle belongs to the user. Read `TYPESAFE_API_KEY` or the configured existing OS credential entry. Never set, delete, migrate, prompt for, print, or put a credential in argv. Configure only its non-secret locator. Keep keys out of browser/client bundles.
- Routing summary sharing and artifact sharing are separate project permissions. Initialize offline, preview the payload, and make live calls only within the user's enabled project settings and authorized scope. A saved key alone does not enable sharing or live evaluation.
- Produce standalone HTML and JSON telemetry from actual runs. Keep synthetic demonstrations separate from real evidence and clearly label unqualified thresholds and unknown costs.

## Read progressively

`PLAN.md` defines workstreams, evidence collection, app integration and completion. `RUNBOOK.md` supplies offline startup and links to exact command contracts. `templates/` has editable worksheets plus the exact runtime-generated packet and default policy. `examples/` contains a synthetic report for orientation only. `MANIFEST.json` and `SHA256SUMS` identify the bundled pilot and file contents.

The pilot at source baseline `eff47efbc55bdf02b6d722cf9628d1858eef2d7a` passed 196 local tests and extracted-source validation. Remote candidate CI, live Jev qualification, Yarn-specific quality, security accuracy, and threshold calibration are pending. That is tooling validation, not proof of good routing on this repo.
