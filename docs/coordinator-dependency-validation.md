# Coordinator dependency experiment — 2026-09-22

Question version `pilot-routing-v8` distinguishes a missing prerequisite decision
from later coordinator review, acceptance, integration or deployment. The default
`coordinator_coupling` cutoff changes from **0.20 to 0.40**, with a stop only when
the probability is strictly above the cutoff. Selection version is
`pilot-selection-v7`. Explicit project cutoffs remain unchanged; the new default
applies when no value is supplied. The suitability threshold stays **0.85**.
These are experimental operating thresholds, not probabilities of worker success.

The question remains one independent Noul proposition in the existing batch.
It does not consume answers to other questions. The exact wording, payload
examples and consumption documentation are generated from
[the runtime registry](../.agents/skills/ultra-delegation/references/pilot-questions.md).
Host permissions, eligibility, missing-requirement checks, review and recovery are
unchanged. Old saved decisions require reevaluation because question and policy
versions changed. No installed skill or saved project policy was modified.

## What was actually evaluated

1. Before inference, author twelve controls and independently review their labels.
   Six were development controls and six held out from cutoff selection. Compare
   original/revised wording in separate full-batch calls with five native profiles.
2. Select **0.25** from the six development controls using a frozen rule: minimize
   false dependency clearances, then unnecessary blocks; ties stay nearest 0.20.
   All six later controls were correctly classified. Preserve this first freeze.
3. Reevaluate the twelve exposed worker tasks with and without Epoch metadata.
   These 24 arms are regressions, not fresh held-out tasks. At 0.25, six complete
   task arms still hit the dependency stop. At 0.40, none did.
4. Treat all exposed cases as development evidence and freeze **0.40**, the
   smallest tested cutoff with no dependency errors in the available regression
   cases and exposed controls. Then independently label eight fresh controls and
   run them once. **8/8** were correct: four actionable tasks cleared (0.09–0.16)
   and four missing-decision tasks stopped (0.80–0.91). These explicit authored
   cases support a bounded gate check, not broad quality or safety calibration.

No threshold was silently retuned on purported held-out results: the first
iteration and its remaining blocks are preserved, and the second iteration has a
separate freeze and fresh confirmation. The question wording stayed fixed between
these two iterations. Each new API payload was attempted once. One invalid
response is retained as unavailable; it was not replaced with a successful retry.

## Routing and observed outputs

| Wording / cutoff | Routed arms / 24 | Dependency stops | Selected outputs accepted |
| --- | ---: | ---: | ---: |
| Original / 0.20 | 7 | 17 | 5/7 |
| Original / 0.40 | 19 | 0 | 17/19 |
| Revised / 0.20 | 11 | 10 | 9/11 |
| Revised / 0.25 | 13 | 6 | 11/13 |
| Revised / 0.40 | 19 | 0 | 17/19 |

The **cutoff is the principal coverage improvement**. These data do not establish
that the wording improves downstream quality. Revised wording makes the intended
boundary explicit. Separate inference calls can also change other answers; only
cutoff replays within a wording reuse identical captured probabilities.

Final revised routing has three `no-suitable-candidate` stops, one
`missing-or-uncertain-requirement` stop and one invalid response. The 19 routed
arms select **10 unique task/configurations**: nine accepted outputs and one
rejected Luna Python review. Research arms share outcomes, so 17/19 is not nineteen
independent successes. Outputs come from the completed 60-cell matrix, matched by
exact task/configuration; there were no additional native executions here.
Higher routing coverage does not eliminate failed outputs. Independent review,
comparison and recovery remain necessary.

## Cost, provenance and limits

There were **56 new Jev calls: 55 validated and one unavailable**. Successful calls
sum to approximately **$0.01213 by the pinned token-price estimate**; the invalid
response is unpriced. Summed request latency was about **13.2 seconds**, excluding
preparation, credential lookup, native execution and review. Native billing and
savings are unavailable. Security checks were off.

The small authored controls are deliberately explicit and easier than naturally
ambiguous requests. No reliability confidence interval, security guarantee, or
minimum qualification count follows from them. All original worker cases were
already exposed. Synthetic controls and routing replays are not exported as
worker learning. Reference labels and findings were not sent to Jev. Prepared
routing bodies stayed within the unchanged 24 KiB limit (maximum 24,485 bytes).

[Sanitized results](coordinator-dependency-results.json) contain the paired
summaries, probability controls, freezes, usage and limitations. Full local HTML,
payload previews, hashed protocols, captured validated answers and independent
reference reviews remain in the evaluation directory. The original benchmark and
its failures are preserved separately.

## Implementation validation

All **379 tests pass** locally and from the extracted source archive with site
packages disabled and with keyring 25.7.0 installed. Generated references match
runtime definitions. Installable/source archives pass deterministic packaging
checks; all 62 packaged Python files parse with Python 3.10 grammar. Remote CI
remains the source of execution results for other supported Python/OS versions.
Independent review found no blocking code or evidence-accounting issues. The
portable Yarn bundle includes the current runtime and both validation reports.
