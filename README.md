# Ultra Delegation

Let a capable coordinator plan and verify the work while smaller models handle bounded tasks. Learn which model, thinking setting, and prompt work for each task family, then reuse that evidence.

**Active routing and recovery:** after project setup, Jev selects workers immediately, including on an empty history. Native bake-offs, one targeted repair, and eligible fallbacks continue toward an independently accepted result. No qualification gate or routing shadow rollout is required. See the [workflow](.agents/skills/ultra-delegation/references/pilot-workflow.md) and [current validation status](docs/repository-trial-validation.md).

**Development release candidate: 1.3.0-rc.7.** Python 3.10 or newer. The offline helper and HTTP adapter have no required Python package dependencies; read-only credential lookup uses the native macOS Keychain utility or optional `keyring` on Windows/Linux. Host execution requires an installed agent host and access to its models. See the [compatibility matrix](docs/compatibility.md) for tested capabilities and limits.

For a repository trial, start with the [agent walkthrough](.agents/skills/ultra-delegation/references/repository-trial.md). It covers packet preparation, active routing, native execution, review, recovery, and HTML/JSON reporting. The user supplies an ordinary task; the agent maintains the internal files.

## Proof of concept — use with care

This is an experimental proof of concept, not production-ready automation. It can make incorrect routing decisions, produce bad code, consume paid model usage, or cause unintended changes through your agent host. Use a disposable project or a backed-up Git checkout, limit host permissions, and review changes before accepting them. Do not use it for unattended production, security-critical, or destructive work. Guardrails are cooperative checks, not a sandbox or a guarantee against data loss, disclosure, or resource overload. Provided as-is under the MIT license.

The maintainer reports successful use in **Codex and Claude Code**. These are real-world smoke reports, not a qualification of every model, thinking setting, platform, or task. Feedback and reproducible bug reports are welcome. OpenCode remains experimental; local model execution is disabled by default and unsupported in this beta.

## What it does

- Routes work using project preferences, verified local outcomes, and compatible imported learning.
- Compares models, thinking budgets, or prompts while changing one variable at a time.
- Requires acceptance gates and coordinator review before learning from success.
- Produces quality and cost reports with measured, estimated, and unavailable values distinguished.
- Exports sanitized aggregate recommendations for reuse across projects, with local verification on import.
- Checkpoints coordinator context and blocks further delegation when its supplied context observations indicate critical risk.

The Python helper makes deterministic bookkeeping decisions. Your agent host executes workers and supplies observations. A configured model is not proof that it is available, affordable, or effective for your project.

## Install

Repository: [ultradotdev/ultra-delegate-skill](https://github.com/ultradotdev/ultra-delegate-skill). Download the installable skill archive and its SHA-256 checksum from the [releases page](https://github.com/ultradotdev/ultra-delegate-skill/releases), when available, or build from a reviewed source checkout as shown below. Verify the checksum before extraction. The archive contains one `ultra-delegation/` folder, including its license.

For a repository-local Codex installation, extract that folder into `.agents/skills/` in the target project. For a personal installation, place it in `${CODEX_HOME:-~/.codex}/skills/`. If `ultra-delegation` already exists, preserve the previous folder before replacing it. Start a fresh task after installation and confirm the selected skill path, especially if both project and personal copies exist.

Claude Code and OpenCode setup is described in [host instructions](.agents/skills/ultra-delegation/references/hosts.md). Their templates are optional and require checking against the installed host version. Copying a template does not qualify a host as verified.

To build the archive from a reviewed source checkout:

```sh
python3 scripts/build_release.py --output-dir dist
python3 scripts/build_release.py --source --output-dir dist
```

The first command packages the installable skill. The second creates a clean source ZIP containing the public documentation, tests, CI, and skill. Both use explicit file allowlists and exclude development history and personal configuration. The source ZIP can be extracted and initialized as a new public repository; do not push the private development history.

## First use

For active Jev routing, ask the agent to follow the [repository walkthrough](.agents/skills/ultra-delegation/references/repository-trial.md), using your existing credential locator. Default selection uses dated efficiency hints; choose `strongest_fit` if preferred. Automatic bake-offs compare cold or recently failing selections. Security checks are optional, off by default. Summary sharing and artifact sharing remain separate permissions.

For the offline legacy helper, from a project with the repository-local skill installed:

```sh
python3 .agents/skills/ultra-delegation/scripts/ultra_delegation.py --root .ultra-delegation init
python3 .agents/skills/ultra-delegation/scripts/ultra_delegation.py --root .ultra-delegation validate
```

Then ask your agent:

> Use Ultra Delegation for this task. Discover the models and thinking controls available in this host. Keep local models disabled. Delegate only independently testable work, verify the result, and report quality plus any defensible cost or latency figures. Keep trivial tasks with the coordinator.

For an experiment:

> Use Ultra Delegation to compare two available remote worker models on one bounded patch proposal at the same supported thinking setting. Define gates before execution, evaluate both, and record the outcome. Do not claim savings when telemetry is unavailable.

Inspect `--help` and the [CLI reference](.agents/skills/ultra-delegation/references/cli.md) for ranking, recording, reports, catalog promotion, import/export, and guards. Cortex is optional; the fallback is project-local JSON evidence. Import recommendations as priors, then verify them in your environment.

## Jev v2 project pilot

The [repository workflow](.agents/skills/ultra-delegation/references/repository-trial.md) provides a Python CLI and importable functions for batched routing, native-host handoff, independently assessed outcome learning, and self-contained HTML + JSON telemetry. Security assessment is optional and advisory, off by default; evaluator failures are recorded without blocking ordinary outcome recording. Existing mandatory project tests remain authoritative.

Start with an offline synthetic demonstration:

```sh
python3 .agents/skills/ultra-delegation/scripts/pilot.py --root /tmp/ultra-pilot-demo demo
```

Use a fresh output directory. The command prints paths to HTML and JSON reports and never reads credentials or calls an API. The [pilot guide](.agents/skills/ultra-delegation/references/pilot.md) describes the Yarn consolidation test drive, explicit live opt-in, existing credential locators, packet preview, outcome forms, and native dispatch rechecks. [Generated question documentation](.agents/skills/ultra-delegation/references/pilot-questions.md) stays synchronized in CI. No live quality, security accuracy, savings or thresholds are qualified by the synthetic demo.

The first iteration keeps Python 3.10+ and a versioned JSON boundary so the future Yarn app, or a later Rust CLI, can consume the same explicit contracts. The older router and benchmark below remain available for comparison.

## Legacy optional Jev routing and judging

Jev can select suitable host-native worker profiles or nominate controlled experiments. Routing supports off, shadow, and explicitly enabled active modes; judging is shadow-only and never changes acceptance or promotions. Both default to off. Sending selected code/output excerpts requires a separate opt-in from sending task summaries.

The adapter reads an existing OS credential entry or `TYPESAFE_API_KEY`. Configure the existing service/account names if needed; it never creates, changes, or deletes credentials. The ordinary helper remains offline. See the [Jev setup, packet contracts and qualification guide](.agents/skills/ultra-delegation/references/jev.md). Active routing quality and judge quality require live qualification on relevant tasks; mocked tests establish implementation behavior only.

The [generated question reference](.agents/skills/ultra-delegation/references/jev-questions.md) exposes the exact questions and how code consumes them. CI checks it against the production payload builders. The [adaptive shortlist](.agents/skills/ultra-delegation/references/shortlist.md) combines unproven shipped discovery seeds with validated local results. The [quantitative benchmark](.agents/skills/ultra-delegation/references/jev-benchmark.md) produces standard JSON and Markdown artifacts from independently assessed downstream outcomes, with a calibration/test split and explicit limits on performance claims.

## Local models and resource budgets

Local execution is **disabled by default**, including when upgrading an existing policy. Model exclusions and an optional allowlist apply before routing. Enabling local execution requires explicit user intent; imported evidence cannot enable it.

Even when enabled, a local route must pass fresh resource checks and have enforced context/output bounds, a scoped cancellation mechanism, runtime observation, and a concurrency lease. Default budgets reserve at least 25% of RAM or 4 GiB and 20% of discrete VRAM or 1 GiB; local work starts with at most 8,192 context tokens, 2,048 output tokens, one request, and five minutes. Unified memory must not be counted twice.

**This beta does not ship a verified local execution adapter.** OpenCode local execution remains unsupported until the necessary controls are exercised. The resource gate consumes observations; it is not an operating-system resource sandbox and does not guarantee protection from overload. Direct Ollama execution, server startup, and model downloads are outside this release.

## Privacy and measurements

Keep project policy under version control. Evidence, run artifacts, and reports belong in ignored `.ultra-delegation/` paths. Global catalog writes require explicit promotion. Exports carry generalized aggregates, not project source, prompts, screenshots, or full results. Allowed fields and recognizable-secret checks reduce leakage; review free text before sharing because no filter can identify every secret.

Cost estimates need dated prices and complete usage. Subscription usage is not an API invoice. Local inference has unknown monetary cost unless configured. Experiment overhead is separate from projected future savings. There is no universal savings claim for this beta.

## Develop and uninstall

```sh
python3 -m unittest discover -s tests -v
python3 scripts/build_release.py --check
```

See [contributing](CONTRIBUTING.md), the [demo guide](docs/demo.md), and [Ultra.dev handoff](docs/ultra-dev-handoff.md).

To uninstall, remove only the installed `ultra-delegation` skill folder and any worker template you explicitly installed, then start a fresh host session. Project evidence and your global catalog are separate data and remain until you choose to remove them. MIT licensed; see [LICENSE](LICENSE).

For agent-operated repository trials, use the [current walkthrough](.agents/skills/ultra-delegation/references/repository-trial.md). It includes active routing, configurable efficiency hints, native execution, review/recovery and HTML/JSON reports. See [current validation](docs/repository-trial-validation.md) for exactly what has been exercised.
