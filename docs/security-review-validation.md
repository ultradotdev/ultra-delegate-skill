# Task boundaries and optional security review — RC 1.3.0-rc.8

Every newly prepared task now needs explicit allowed changes/actions, protected behavior/data, coordinator decisions, applicable security requirements (or explained non-applicability), and granted authorization. The prepared worker contract and review bind to the packet/contract hash. Old records remain readable; old packets must be prepared again before new dispatch.

Security screening remains **off by default**, with no scanner installation or integration. `workflow-security --dry-run` previews selected excerpts, exact boundaries, requirement questions, and observed checks. Live screening requires separate artifact-sharing permission. User-managed credentials are read only.

One independent violation Noul and one evidence-sufficiency Noul are asked per requirement. Defaults remain **0.20 / 0.80 / 0.90**, as experimental operating bands. These are not vulnerability severity or task-success probabilities. A flagged or security-sensitive artifact needs independent review before outcome publication. Confirmed critical defects or mandatory requirement violations reject the attempt through existing comparison/repair/fallback recovery. Unresolved concerns need explicit disposition. Unrelated pre-existing vulnerabilities are recorded separately. Technical service failure alone does not fail independently accepted work.

## Live signal checks

Independent source review and deterministic execution established the references before Jev calls. The review corrected two scope assumptions: trusted authenticated request identity, and no attacker-controlled concurrent filesystem mutation for the path-confinement example. Three vulnerable/safe pairs formed development; the fourth pair and two robustness cases were held out.

| Test | Result |
|---|---|
| Development, original 0.90 evidence cutoff | All 3 defects flagged; 2/3 safe cases unnecessarily sent for follow-up |
| Development replay at 0.80 evidence cutoff | Same saved probabilities; all 3 defects flagged and 0/3 safe cases flagged |
| Held-out, 0.80 cutoff frozen before calls | Defect and missing-context case flagged; both safe cases clear |
| Four actual native-worker repairs | Independent functional/security checks passed for all four |
| Jev screening of repaired outputs at frozen 0.80 | Three clear; diagnostics repair requested more evidence |
| Independent native follow-up | Dismissed diagnostics concern after source inspection and a toy-token test |

The qualification run froze **0.80 for evidence sufficiency** after development and before held-out inference. **The shipped default remains 0.90.** The study is too small and too narrowly authored to call either cutoff calibrated. The violation and strong-concern cutoffs did not encounter borderline live probabilities, so their numeric boundaries are unit-tested, not empirically established by this run.

There were **14 live Jev calls**: ten frozen fixture inputs and four actual fixed artifacts. A single Sol medium invocation handled four separately bounded toy functions; an independent Terra medium invocation handled the flagged diagnostic follow-up. These test security signals and review behavior, not best-model selection. Native billing is unavailable. Jev token-derived prices are estimates; no savings claim is made. The machine-readable [results](security-review-results.json) preserve initial false alarms, the development-only rule replay, evaluator provenance, and follow-up disposition.

## Reproduce

From the source archive, run `python3 scripts/security_qualification.py prepare --root /tmp/security-check`. Independently review the frozen references, fill the generated reference-review file, then run `development --live`, `freeze`, and `heldout --live` using that same root. `--credential-locator` accepts service/account names only; `--bands` supplies experimental band overrides to `freeze`. Exact payload previews precede calls. Missing credentials leave qualification pending. Omit `--live` to test the harness with labeled mocks; mock results are not calibration evidence. Interrupted reservations do not repay automatically.

## Verification

Focused tests cover boundary completeness and authorization, independent atomic questions, exact cutoff inclusivity, sharing, redaction, policy/artifact changes, confirmed/dismissed/unresolved findings, interruption, duplicate review, repair reassessment, pending reports, and preserved failure evidence on export. Ten authored fixtures have deterministic reference checks. The complete local suite passes (437 tests), including the review-found policy-change and duplicate-submission regressions. Generated question/catalog checks and reproducible archive checks pass. Both extracted-source suites also pass all 437 tests: isolated Python without site packages, and isolated Python with keyring installed. PR CI remains the separate Python 3.10/3.12/3.14 and OS credential-backend check. No live skill installation, publication or merge is performed by this change.
