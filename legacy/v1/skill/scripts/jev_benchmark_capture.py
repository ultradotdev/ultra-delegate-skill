#!/usr/bin/env python3
"""Opt-in routing response collection for the otherwise offline benchmark."""
from __future__ import annotations

import copy
from contextlib import ExitStack
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jev
import jev_benchmark as benchmark
from jev_contract import PRICE


def collect(data, project_policy, live=False, max_calls=20, call=None, get_credential=None, root=None):
    benchmark.validate(data)
    benchmark.need(type(max_calls) is int and 1 <= max_calls <= 10000, "invalid-call-limit")
    result = copy.deepcopy(data)
    summary = {"status": "pending", "live": live, "captured": 0, "existing": 0, "cases": []}
    # The benchmark may evaluate active recommendations while the project stays
    # in shadow. No other dataset policy difference may silently change scope.
    if project_policy["jev"]["routing"] == "off" or not project_policy["jev"]["share_summaries"]:
        summary["reason"] = "routing-or-summary-sharing-disabled"
        return result, summary
    expected = copy.deepcopy(project_policy)
    expected["jev"]["routing"] = "active"
    benchmark.need(jev.hash_value(expected) == jev.hash_value(data["policy"]), "dataset-project-policy-mismatch")
    get_credential = get_credential or jev.transport.credential
    service_call = call or jev.transport.request
    key = None
    for case in result["cases"]:
        preview = jev.route(case["packet"], expected, root=root, dry_run=True)
        if not preview.get("dry_run"):
            summary["cases"].append({"id": case["id"], "status": "no-request", "reason_codes": preview["reason_codes"]})
            continue
        payload = preview["payload"]
        if case["capture"] is not None:
            benchmark.need(case["capture"]["payload_hash"] == jev.hash_value(payload), "stale-existing-capture")
            jev.transport.validate_response(payload, case["capture"]["response"])
            summary["existing"] += 1
            summary["cases"].append({"id": case["id"], "status": "existing"})
            continue
        if not live or summary["captured"] >= max_calls:
            summary["cases"].append({"id": case["id"], "status": "pending", "reason_codes": ["live-not-requested" if not live else "call-limit"]})
            continue
        try:
            if key is None:
                key, _ = get_credential(expected["jev"]["credential_ref"], service=expected["jev"]["credential_service"])
            response, meta = service_call(payload, key)
            _, usage = jev.transport.validate_response(payload, response)
            benchmark.need(all(q["type"] == "noul" for q in payload["questions"].values()), "unsupported-capture-question-type")
            # Retain only the typed values replay needs, never provider prose or
            # arbitrary top-level/answer metadata from a raw response.
            clean = {"model": response["model"], "answers": {
                q: {"type": "noul", "noul": response["answers"][q]["noul"]}
                for q in payload["questions"]}, "usage": usage}
            price = {"kind": "unknown", "usd": None}
            if payload["model"] == PRICE["model"] and meta["attempts"] == 1:
                price = {"kind": "estimated", "usd": usage["input_tokens"] * PRICE["input_per_million_usd"] / 1_000_000}
            case["capture"] = {"payload_hash": jev.hash_value(payload), "response": clean,
                               "latency_ms": meta["latency_ms"], "cost": price}
            summary["captured"] += 1
            summary["cases"].append({"id": case["id"], "status": "captured"})
        except jev.transport.ServiceError as error:
            summary["cases"].append({"id": case["id"], "status": "pending", "reason_codes": [error.code]})
            # Do not fan an auth/network failure out across an entire dataset.
            summary["reason"] = "collection-incomplete"
            return result, summary
    benchmark.validate(result)
    summary["status"] = "pending" if any(c["status"] == "pending" for c in summary["cases"]) else "collected"
    summary["qualification"] = "not-established-by-collection"
    return result, summary


def main(argv=None):
    parser = jev.SafeParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--max-calls", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        benchmark.need(not args.live or args.output is not None, "live-capture-needs-output")
        benchmark.need(args.output is None or not args.output.exists(), "output-already-exists")
        with Path(args.input).open("rb") as handle:
            body = handle.read(64 * 1024 * 1024 + 1)
        benchmark.need(len(body) <= 64 * 1024 * 1024, "dataset-too-large")
        data = json.loads(body, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        root = Path(args.root)
        policy = jev.ud.load_policy(root)
        # Validate all previews before reserving output; no service or credential
        # lookup occurs here. Open output before paid requests to catch filesystem
        # permission errors, missing parents, symlinks and competing writers.
        collect(data, policy, False, args.max_calls, root=root)
        with ExitStack() as stack:
            handle = stack.enter_context(args.output.open("x", encoding="utf-8")) if args.output else None
            result, summary = collect(data, policy, args.live, args.max_calls, root=root)
            if handle:
                # Contains explicit task summaries; publish only sanitized reports.
                json.dump(result, handle, indent=2, allow_nan=False)
        print(json.dumps(summary, indent=2, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError, jev.ud.UserError, jev.transport.ServiceError):
        print('{"error":"invalid-capture-input-or-state"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
