# Ultra Delegation

Let a capable coordinator plan and verify the work while smaller models handle bounded tasks. Learn which model, thinking setting, and prompt work for each task family, then reuse that evidence.

**Public beta: 1.2.0-beta.1.** Python 3.10 or newer; no Python package dependencies. Host execution requires an installed agent host and access to its models. See the [compatibility matrix](docs/compatibility.md) for tested capabilities and limits.

## What it does

- Routes work using project preferences, verified local outcomes, and compatible imported learning.
- Compares models, thinking budgets, or prompts while changing one variable at a time.
- Requires acceptance gates and coordinator review before learning from success.
- Produces quality and cost reports with measured, estimated, and unavailable values distinguished.
- Exports sanitized aggregate recommendations for reuse across projects, with local verification on import.
- Checkpoints coordinator context and blocks further delegation when its supplied context observations indicate critical risk.

The Python helper makes deterministic bookkeeping decisions. Your agent host executes workers and supplies observations. A configured model is not proof that it is available, affordable, or effective for your project.

## Install

The intended public repository is [ultradotdev/ultra-delegate-skill](https://github.com/ultradotdev/ultra-delegate-skill); publication is pending. Once published, download the release archive and its SHA-256 checksum from its [releases page](https://github.com/ultradotdev/ultra-delegate-skill/releases). Until then, build from a reviewed source checkout as shown below. Verify the checksum before extraction. The archive contains one `ultra-delegation/` folder, including its license.

For a repository-local Codex installation, extract that folder into `.agents/skills/` in the target project. For a personal installation, place it in `${CODEX_HOME:-~/.codex}/skills/`. If `ultra-delegation` already exists, preserve the previous folder before replacing it. Start a fresh task after installation and confirm the selected skill path, especially if both project and personal copies exist.

Claude Code and OpenCode setup is described in [host instructions](.agents/skills/ultra-delegation/references/hosts.md). Their templates are optional and require checking against the installed host version. Copying a template does not qualify a host as verified.

To build the archive from a reviewed source checkout:

```sh
python3 scripts/build_release.py --output-dir dist
python3 scripts/build_release.py --source --output-dir dist
```

The first command packages the installable skill. The second creates a clean source ZIP containing the public documentation, tests, CI, and skill. Both use explicit file allowlists and exclude development history and personal configuration. The source ZIP can be extracted and initialized as a new public repository; do not push the private development history.

## First use

From a project with the repository-local skill installed:

```sh
python3 .agents/skills/ultra-delegation/scripts/ultra_delegation.py --root .ultra-delegation init
python3 .agents/skills/ultra-delegation/scripts/ultra_delegation.py --root .ultra-delegation validate
```

Then ask your agent:

> Use Ultra Delegation for this task. Discover the models and thinking controls available in this host. Keep local models disabled. Delegate only independently testable work, verify the result, and report quality plus any defensible cost or latency figures. Keep trivial tasks with the coordinator.

For an experiment:

> Use Ultra Delegation to compare two available remote worker models on one bounded patch proposal at the same supported thinking setting. Define gates before execution, evaluate both, and record the outcome. Do not claim savings when telemetry is unavailable.

Inspect `--help` and the [CLI reference](.agents/skills/ultra-delegation/references/cli.md) for ranking, recording, reports, catalog promotion, import/export, and guards. Cortex is optional; the fallback is project-local JSON evidence. Import recommendations as priors, then verify them in your environment.

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
