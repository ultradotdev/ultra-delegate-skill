# Beta qualification — 1.2.0-beta.1

Qualification date: 2026-09-04. This is a scoped implementation report, not a certification of every host or model.

## Executed checks

- 78 passing dependency-free unit and integration tests on macOS with Python 3.14.6. Coverage includes canonical/legacy evidence, gates and project floors, model/thinking/prompt isolation, cost completeness and cached/thinking tokens, trust-but-verify imports, quarantine, freshness, output safety, and local exclusions.
- Simulated resource-pressure and timeout tests, unified/discrete memory accounting, unknown footprint rejection, cross-process concurrency, and process-exit lease recovery. No machine-exhaustion test or local inference was performed.
- Official `quick_validate.py` skill validation passed. PyYAML was used only by that external validator; the distributed helper remains dependency-free.
- Allowlisted deterministic skill packaging and extracted-archive init/validate tests. The clean source archive excludes existing Git history and unrelated host configuration.

Reproduce from the source archive:

```sh
python3 -B -m unittest discover -s tests -v
python3 -B scripts/build_release.py --check --source
python3 -B scripts/demo_learning.py
```

[Release CI](https://github.com/ultradotdev/ultra-delegate-skill/actions/runs/33914545619) passed on Linux with Python 3.10, 3.12, and 3.14, including tests and both packaging checks. These are automated helper checks, not model benchmarks.

The maintainer reports successful real-world use in Codex in another repository and in Claude Code. These reports support releasing a proof of concept; they do not supply exact model revisions, thinking settings, cost, latency, or controlled comparison evidence.

## Delegation value report

This implementation used Codex-native subagents for bounded evidence, resource-control, packaging, and safety-review tasks. The coordinator integrated the work and ran the combined deterministic checks. Review found and repaired imported-prior gate-count, confidence, and exact-profile identity defects.

Worker profiles inherited the coordinator configuration; this was **not** a controlled cheaper-model or thinking-budget bakeoff. Token cost, experiment savings, latency comparisons, and break-even count are **unavailable**. No preferred model recommendation was created from this implementation work.

## Known experimental areas

- Clean-context host/model/thinking comparisons with real accepted code changes across Codex, Claude Code, and OpenCode. Supplied templates and documentation remain experimental.
- End-to-end Cortex graph reinforcement and reuse.
- Any local execution adapter. Preflight and monitor decisions are tested, but actual runtime limits and owned-request cancellation are not implemented. Local execution remains disabled by default and unsupported even after policy opt-in.
- The automated learning demonstration uses explicitly synthetic fixtures. It verifies bookkeeping and portability, not model quality or savings.

The proof-of-concept release permits these scoped claims with the README disclaimer. Further host qualification is follow-up work, not a requirement to publish this experimental beta. Do not advertise unexercised combinations as verified or use synthetic reports as performance evidence.

## Publication boundary

A clean source snapshot has been pushed to the private review branch, and the beta was installed locally for Codex testing. The original development history and unrelated Cortex/host configuration were excluded. Public visibility is a separate owner-controlled decision. See [release audit](release-audit.md) for the content and history scan scope.
