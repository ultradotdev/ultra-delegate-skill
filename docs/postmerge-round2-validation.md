# Second test round

PRs #4 and #5 merged into `main` at `3fe6cb0259058cc4b5d600c905f8bc687b23a1da` after green CI. The approved administrator override satisfied the review exception; CI was not bypassed.

| Check | Result |
| --- | --- |
| Merged baseline suite | 304 passed |
| Live Jev routing | One approved-payload repeat, Terra medium selected, Sol medium comparison |
| Native task | Both workers accepted after separate coordinator review and test reruns; no recovery needed |
| New recovery edge cases | 4 passed on merged code; 1 future-timestamp case failed, then passed after the fix |
| Expanded suite | 312 passed, also from the extracted source with site packages disabled |

Both workers independently produced two CLI tests for duplicate dispatch events and wrong observed configurations. The selected Terra tests are retained as `tests/test_pilot_event_cli.py`. `tests/test_pilot_recovery_cli.py` adds fresh-process restart checks, comparison ordering, exhausted limits, terminal acceptance, and future-dated evidence checks. All automated fixtures are simulated and use no provider credentials or calls.

The timestamp finding concerns a manually altered outcome or a clock anomaly: recovery previously allowed a same-request record dated in the future. Such a record already earned no learning credit. The new check blocks dispatch until evidence timestamps are valid. Normal observations stamp the current time and continue to work.

Jev reported one HTTP attempt and approximately 255 ms latency. Router cost was approximately $0.000084, a token-based estimate; native-worker and reviewer costs are unavailable. The live task reused an earlier approved development packet with identical candidate capability descriptions and an empty evidence ledger. It is not held-out quality evidence or proof of optimal model choice. Security and artifact judging were disabled.

The native workers tested the unmodified merged snapshot. The timestamp repair and eight added regression tests were validated separately on `codex/jev-postmerge-tests`. Local HTML/JSON telemetry retains both accepted attempts; private ledgers and worker artifacts are not packaged.
