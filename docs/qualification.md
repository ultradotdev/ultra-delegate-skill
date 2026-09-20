# Jev project pilot qualification: 1.3.0-rc.3

The first iteration is Python 3.10+ with local metadata ledgers and HTML/JSON telemetry. New tests exercise batched question contracts, scoped group evidence, independent acceptance gates, shadow versus active behavior, unavailable service, dispatch rechecks, redacted responses, optional nonblocking security evaluation, output escaping, and archive portability. The synthetic Yarn demo covers proposals, accepted/failed observations, confidence accumulation, security unavailability and pending results.

No real Yarn source has been evaluated by this candidate. No live Jev request, native worker bake-off, security-accuracy benchmark or threshold qualification was performed. The report's synthetic observations and prices are illustrative. Browser visual inspection of the generated local HTML was blocked by the browser URL policy; source/escaping and report-generation behavior are covered by automated checks instead.

Local validation: all 196 tests pass on macOS Python 3.14 and from the extracted source archive; all six archive checks also pass in the isolated optional-keyring environment. Python 3.10 grammar checks pass for 34 Python files. Generated references, reproducible skill/source packaging checks and the official skill validator pass. An independent forward test exercised the documented offline CLI workflow, rejected an incomplete outcome form, and confirmed recheck, security-off and pending-cost behavior. Actual Python 3.10 execution and new remote CI remain pending; historical results below do not establish this candidate's live quality.

# Jev evaluation infrastructure qualification: 1.3.0-rc.2

Date: 2026-09-20. This is local implementation qualification, not live routing-quality evidence.

- All 158 tests pass locally on macOS Python 3.14 and from the extracted source archive. Python 3.10 grammar checks pass; actual candidate remote Python/OS CI remains pending.
- Six archive checks pass with site packages disabled and with optional keyring installed. The official skill validator passes.
- Generated references are checked against the production payload builders and current field projection.
- The standard benchmark runs offline with synthetic captures and independently labeled downstream observations supplied by the operator. Its demo remains synthetic and qualification pending.
- Threshold selection uses calibration data only; held-out labels cannot change the selected threshold. Missing captures, outcomes, or costs remain explicit.
- Downstream per-dimension floors and critical-defect vetoes prevent high clarity from compensating for missing requirements.
- Standing discovery seeds require exact host/model/effort availability. Matching reviewed outcomes can change ranking; stale/failed results require retesting. Normalized records preserve latest-failure behavior when composing a Jev packet.
- Capture tests use fake credentials and transports only. Existing/missing/unwritable output targets are rejected before requests; no real credential-store or endpoint operation was performed.
- A Terra medium read-only review found a collector output-preflight defect; output is now reserved before a paid request. No remaining concrete findings were reported after correction. An independent forward test used the documented commands to generate question docs, a benchmark report, and the standing shortlist without credentials or network access.

No live Jev call or worker bake-off was run for this candidate. No threshold or model has been qualified by this work. No personal skill installation or credential was modified. Candidate CI has not run remotely.

Reproduce the synthetic report:

```sh
python3 .agents/skills/ultra-delegation/scripts/jev_benchmark.py --demo --output-prefix /tmp/jev-routing-demo
python3 .agents/skills/ultra-delegation/scripts/jev_docs.py --check
python3 -B -m unittest discover -s tests -v
python3 scripts/build_release.py --check
python3 scripts/build_release.py --source --check
```

The preceding release candidate subsequently passed all 120 tests across Python 3.10/3.12/3.14 and optional-keyring packaging jobs on Linux/macOS/Windows in [PR 2](https://github.com/ultradotdev/ultra-delegate-skill/pull/2). Those results are historical and do not establish the new candidate's remote compatibility.

---

# Jev candidate qualification: 1.3.0-rc.1

Date: 2026-09-18. This candidate adds an external decision adapter while preserving the offline helper. The previous beta report follows as historical evidence, not a claim that its CI has run on this candidate.

## Candidate checks

- All 119 dependency-free tests pass locally on macOS Python 3.14, including existing regression tests and mocked Jev routing, judge, credential, transport and ledger tests.
- Extracted skill archives run with site packages disabled and in a separate temporary environment with keyring 25.7.0 installed. This tests packaging/import compatibility, not real Keychain reads or cross-platform native-store operation.
- Credential lifecycle is user-owned: tests reject all mutation commands before lookup, prove existing service/account entries are read without writes, and verify missing entries never trigger creation.
- An owned delayed transport process is terminated under a shortened test deadline. Mock HTTP checks cover retry caps, authentication errors, malformed responses, redirects and size limits.
- Official skill validation passes using PyYAML only in the isolated validation environment.
- A Codex-native Terra medium read-only review examined the adapter boundaries. Follow-up changes bound dispatch rechecks to saved decisions and kept cleanup within the request budget. Imported-prior first-use routing remains intentional and explicitly pending verification, consistent with the existing trust-but-verify contract.
- An independent Terra medium forward test exercised keyless CLI configuration, routing/judging previews, safe missing-credential behavior and mock experiment/judge behavior. Its profile-location documentation finding was corrected with an explicit requirement and complete minimal packet.
- Optional-keyring archive checks are configured for Linux, macOS and Windows CI. New remote CI results are pending; local success does not qualify all operating systems or Python versions.

## Pending qualification

No real TypeSafe endpoint request, live routing-quality benchmark, or live judge-quality benchmark was performed. No credential was requested, saved, or read from the user's OS store. The opt-in synthetic runner reports `pending` until explicitly run with access. Synthetic authored labels are not a substitute for representative independent review and held-out task families.

No installed personal skill or external provider configuration was modified. No worker was dispatched through Jev. Worker gates, acceptance and promotion remain coordinator-owned. Review cost and latency comparisons are unavailable; no savings claim is made.

Reproduce:

```sh
python3 -B -m unittest discover -s tests -v
python3 scripts/build_release.py --check
python3 scripts/build_release.py --source --check
python3 .agents/skills/ultra-delegation/scripts/jev_qualification.py
```

---

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
