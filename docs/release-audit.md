# Release review — 1.2.0-beta.1

Date: 2026-09-04. Scope: clean release source, distributable files, and the clean review branch history. The unrelated private development checkout is not part of the publication boundary.

## Content and privacy

- Gitleaks 8.30.1 scanned the clean Git history and source directory with redacted output; no credential leaks were detected.
- Targeted content checks covered personal filesystem paths, email-address patterns, common credential forms, and private-key markers. Matches were inspected as scanner rules or deliberately synthetic tests, not live credentials or personal contact data.
- Release packaging uses an explicit file allowlist, rejects symlink inputs and recognizable secrets/personal paths, and does not include Git metadata or unrelated host configuration.
- At the owner's request, release-branch author and committer metadata use `Keith <hello@ultra.dev>`. The original personal attribution is removed from the rewritten branch history. ZIPs contain no Git metadata. Hosting services may retain old, unreachable commit objects; rewriting branch history is not a guarantee of server-side erasure.

## Correctness scope

- Reviewed routing eligibility, acceptance/promotion checks, import confirmation/quarantine, cost calculation, output containment, and release packaging. The existing 78-test regression suite covers these contracts; it passed from an extracted clean source archive.
- No model/provider execution is performed by the Python helper. Local admission and monitor functions are contracts, not an implemented runtime supervisor.
- Maintainer-reported Codex and Claude Code use is recorded separately from deterministic tests and controlled model comparisons.

This is a bounded pre-release review, not an independent security certification. Pattern scanners cannot detect every secret or identify arbitrary personal information, and tests cannot prove the absence of defects. The README proof-of-concept warning and scoped compatibility matrix remain part of the release.
