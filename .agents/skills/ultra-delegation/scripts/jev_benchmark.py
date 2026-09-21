#!/usr/bin/env python3
"""Offline, independently labeled downstream routing replay. Never calls a service."""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jev
import jev_qualification as fixtures
from jev_contract import RUBRIC, validate_policy

SCHEMA = "ultra-delegation-benchmark-v1"
DIMENSIONS = tuple(RUBRIC)
MAX_INPUT_BYTES = 64 * 1024 * 1024


def need(value, code):
    if not value:
        raise ValueError(code)


def fields(value, required, optional=()):
    need(isinstance(value, dict) and set(required) <= set(value) <= set(required) | set(optional), "invalid-benchmark-fields")


def read_dataset(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    need(len(raw) <= MAX_INPUT_BYTES, "benchmark-input-too-large")
    try:
        return json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise ValueError("invalid-benchmark-json") from None


def label(value):
    need(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value), "invalid-benchmark-label")
    return value


def number(value, maximum=1e12):
    need(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum, "invalid-benchmark-number")
    return value


def cost(value):
    fields(value, ("kind", "usd"))
    need(value["kind"] in ("measured", "estimated", "unknown"), "invalid-cost-kind")
    if value["kind"] == "unknown":
        need(value["usd"] is None, "unknown-cost-must-be-null")
    else:
        number(value["usd"])
    return value


def combine_cost(values):
    if any(v["kind"] == "unknown" for v in values):
        return {"kind": "unknown", "usd": None}
    return {"kind": "estimated" if any(v["kind"] == "estimated" for v in values) else "measured",
            "usd": sum(v["usd"] for v in values)}


def assess(observation, rubric):
    """Predeclared per-dimension floors prevent compensating for missing requirements."""
    return (all(g["passed"] for g in observation["gates"] if g["mandatory"])
            and not observation["critical_failures"]
            and all(observation["scores"][d] >= rubric["minimum_scores"][d] for d in DIMENSIONS)
            and statistics.mean(observation["scores"].values()) >= rubric["quality_floor"])


def validate(data):
    fields(data, ("schema", "dataset_id", "synthetic", "policy", "rubric", "thresholds", "risk_target", "cases"))
    need(data["schema"] == SCHEMA and type(data["synthetic"]) is bool, "invalid-benchmark-schema")
    label(data["dataset_id"])
    need(isinstance(data["policy"], dict), "invalid-benchmark-policy")
    validate_policy(data["policy"].get("jev", {}))
    need(data["policy"].get("jev", {}).get("routing") == "active", "benchmark-needs-active-replay-policy")
    fields(data["rubric"], ("version", "minimum_scores", "quality_floor"))
    label(data["rubric"]["version"])
    fields(data["rubric"]["minimum_scores"], DIMENSIONS)
    for n in [data["rubric"]["quality_floor"], *data["rubric"]["minimum_scores"].values()]:
        number(n, 100)
    fields(data["risk_target"], ("max_false_acceptance_upper", "minimum_labeled_groups"))
    number(data["risk_target"]["max_false_acceptance_upper"], 1)
    need(type(data["risk_target"]["minimum_labeled_groups"]) is int and data["risk_target"]["minimum_labeled_groups"] > 0, "invalid-minimum-sample")
    thresholds = data["thresholds"]
    need(isinstance(thresholds, list) and 1 <= len(thresholds) <= 20, "invalid-thresholds")
    for n in thresholds:
        need(number(n, 1) > .5, "invalid-threshold")
    need(len(set(thresholds)) == len(thresholds), "duplicate-threshold")
    need(isinstance(data["cases"], list) and 1 <= len(data["cases"]) <= 10000, "invalid-cases")
    ids, groups = set(), {}
    for case in data["cases"]:
        fields(case, ("id", "group_id", "split", "packet", "capture", "preparation_cost", "observations"))
        label(case["id"]); label(case["group_id"])
        need(case["id"] not in ids, "duplicate-case")
        ids.add(case["id"])
        need(case["split"] in ("calibration", "test"), "invalid-split")
        need(groups.setdefault(case["group_id"], case["split"]) == case["split"], "group-leaks-across-splits")
        jev.validate_route(case["packet"])
        label(case["packet"]["task"]["task_family"])
        cost(case["preparation_cost"])
        capture = case["capture"]
        if capture is not None:
            fields(capture, ("payload_hash", "response", "latency_ms", "cost"))
            need(isinstance(capture["payload_hash"], str) and re.fullmatch(r"[a-f0-9]{64}", capture["payload_hash"]), "invalid-capture-hash")
            number(capture["latency_ms"]); cost(capture["cost"])
        ids_in_packet = {jev.ud.profile_id(c["profile"]) for c in case["packet"]["candidates"]}
        need(isinstance(case["observations"], list), "invalid-observations")
        seen = set()
        for obs in case["observations"]:
            fields(obs, ("profile_id", "artifact_hash", "gates", "scores", "critical_failures", "reviewer", "costs", "latency_ms"))
            pid = obs["profile_id"]
            need(pid in ids_in_packet and pid not in seen, "invalid-observation-profile")
            seen.add(pid)
            need(isinstance(obs["artifact_hash"], str) and re.fullmatch(r"[a-f0-9]{64}", obs["artifact_hash"]), "invalid-artifact-hash")
            fields(obs["reviewer"], ("id", "independent", "kind"))
            label(obs["reviewer"]["id"])
            need(obs["reviewer"]["independent"] is True and obs["reviewer"]["kind"] in ("human", "frontier", "synthetic"), "independent-review-required")
            need(data["synthetic"] or obs["reviewer"]["kind"] != "synthetic", "synthetic-label-in-real-data")
            fields(obs["scores"], DIMENSIONS)
            for score in obs["scores"].values():
                number(score, 100)
            need(isinstance(obs["gates"], list) and obs["gates"], "observed-gates-required")
            gate_ids = set()
            for gate in obs["gates"]:
                fields(gate, ("id", "mandatory", "passed")); label(gate["id"])
                need(gate["id"] not in gate_ids, "duplicate-gate")
                gate_ids.add(gate["id"])
                need(type(gate["mandatory"]) is bool and type(gate["passed"]) is bool, "invalid-gate")
            need(any(g["mandatory"] for g in obs["gates"]), "mandatory-gate-required")
            need(isinstance(obs["critical_failures"], list), "invalid-critical-failures")
            for failure in obs["critical_failures"]:
                label(failure)
            fields(obs["costs"], ("worker", "retry", "review"))
            for value in obs["costs"].values():
                cost(value)
            if obs["latency_ms"] is not None:
                number(obs["latency_ms"])
    return data


def replay(case, policy, threshold):
    current = copy.deepcopy(policy)
    current["jev"]["suitability_threshold"] = threshold
    called = False
    def captured(payload, key):
        nonlocal called
        called = True
        record = case["capture"]
        if record is None:
            raise jev.transport.ServiceError("capture-unavailable")
        need(jev.hash_value(payload) == record["payload_hash"], "capture-payload-mismatch")
        return record["response"], {"attempts": 1, "latency_ms": record["latency_ms"]}
    result = jev.route(case["packet"], current, key="offline-replay", call=captured)
    need(result["status"] != "unavailable" or case["capture"] is None, "invalid-captured-response")
    return result, called


def rate(n, d):
    if not d:
        return {"numerator": n, "denominator": d, "rate": None, "wilson_95": None}
    p, z = n / d, 1.959963984540054
    center = (p + z*z/(2*d)) / (1 + z*z/d)
    half = z * math.sqrt(p*(1-p)/d + z*z/(4*d*d)) / (1 + z*z/d)
    return {"numerator": n, "denominator": d, "rate": p, "wilson_95": [max(0, center-half), min(1, center+half)]}


def distribution(values):
    values = sorted(v for v in values if v is not None)
    return {"count": len(values), "median": statistics.median(values) if values else None,
            "p95": values[max(0, math.ceil(.95 * len(values))-1)] if values else None}


def evaluate(cases, data, threshold):
    rows = []
    for case in cases:
        event, called = replay(case, data["policy"], threshold)
        observations = {o["profile_id"]: o for o in case["observations"]}
        eligible = [r for r in event["ranking"] if r["eligible"]]
        costs = {pid: combine_cost(list(o["costs"].values())) for pid, o in observations.items()}
        # Comparator choices also respect deterministic context and coordinator stops.
        stopped = bool(set(event["reason_codes"]) & {"context-stop", "coordinator-owned", "no-eligible-candidates"})
        baseline = None if stopped else event["baseline_profile_id"]
        # Cheapest uses preexisting ranking cost evidence, never downstream test costs.
        priced = [r for r in eligible if r.get("cost_usd") is not None]
        cheapest = min(priced, key=lambda r: (r["cost_usd"], r["profile_id"]))["profile_id"] if priced and not stopped else None
        if "user-or-project-choice" in event["reason_codes"]:
            cheapest = baseline
        overhead = combine_cost([case["preparation_cost"], case["capture"]["cost"] if called and case["capture"] else {"kind": "unknown", "usd": None} if called else {"kind": "measured", "usd": 0}])
        selections = {"jev": event["selected_profile_id"] if event["action"] == "route" else None,
                      "baseline": baseline, "cheapest_eligible": cheapest}
        outcomes = {}
        for strategy, pid in selections.items():
            obs = observations.get(pid)
            outcomes[strategy] = {"profile_id": pid, "acceptable": assess(obs, data["rubric"]) if obs else None,
                                  "total_cost": combine_cost([costs[pid], overhead if strategy == "jev" else case["preparation_cost"]]) if obs else {"kind": "unknown", "usd": None},
                                  "latency_ms": (obs["latency_ms"] + (event["latency_ms"] if strategy == "jev" else 0)) if obs and obs["latency_ms"] is not None else None}
        rows.append({"case_id": case["id"], "group_id": case["group_id"], "family": case["packet"]["task"]["task_family"],
                     "action": event["action"], "reason_codes": event["reason_codes"],
                     "input_hash": event["input_hash"], "policy_hash": event["policy_hash"],
                     "question_hash": event["question_hash"], "probabilities": event["probabilities"], "outcomes": outcomes,
                     "capture_available": not called or case["capture"] is not None,
                     "inference_evaluated": called and case["capture"] is not None,
                     "router_latency_ms": event["latency_ms"] if called and case["capture"] else None,
                     "overhead_cost": overhead,
                     "observed_artifacts": [{"profile_id": o["profile_id"], "artifact_hash": o["artifact_hash"], "reviewer": o["reviewer"],
                                             "scores": o["scores"], "gates": o["gates"], "critical_failures": o["critical_failures"],
                                             "acceptable": assess(o, data["rubric"])} for o in case["observations"]]})
    summary = summarize(rows)
    summary["inference_evaluated"] = summarize([r for r in rows if r["inference_evaluated"]])
    summary["families"] = {family: summarize([r for r in rows if r["family"] == family]) for family in sorted({r["family"] for r in rows})}
    return {"threshold": threshold, "summary": summary, "cases": rows}


def summarize(rows):
    out = {"cases": len(rows), "capture_coverage": rate(sum(r["capture_available"] for r in rows), len(rows)), "strategies": {},
           "router_and_preparation_cost": combine_cost([r["overhead_cost"] for r in rows]) if rows else {"kind": "unknown", "usd": None},
           "router_latency_ms": distribution([r["router_latency_ms"] for r in rows])}
    for strategy in ("jev", "baseline", "cheapest_eligible"):
        selected = [r["outcomes"][strategy] for r in rows if r["outcomes"][strategy]["profile_id"]]
        labeled = [r for r in selected if r["acceptable"] is not None]
        known = [r["total_cost"] for r in selected if r["total_cost"]["kind"] != "unknown"]
        groups = {}
        for row in rows:
            outcome = row["outcomes"][strategy]
            if outcome["profile_id"]:
                groups.setdefault(row["group_id"], []).append(outcome)
        labeled_groups = [items for items in groups.values() if all(item["acceptable"] is not None for item in items)]
        failed_groups = sum(any(not item["acceptable"] for item in items) for items in labeled_groups)
        out["strategies"][strategy] = {
            "group_label_coverage": rate(len(labeled_groups), len(groups)),
            "group_failure_risk": rate(failed_groups, len(labeled_groups)),
            "dispatch_coverage": rate(len(selected), len(rows)), "abstention": rate(len(rows)-len(selected), len(rows)),
            "label_coverage": rate(len(labeled), len(selected)), "quality_pass": rate(sum(r["acceptable"] for r in labeled), len(labeled)),
            "false_acceptance": rate(sum(not r["acceptable"] for r in labeled), len(labeled)),
            "known_cost_count": len(known), "unknown_cost_count": len(selected)-len(known),
            "selected_dispatch_cost": combine_cost([r["total_cost"] for r in selected]) if selected else {"kind": "unknown", "usd": None},
            "total_cost": combine_cost([r["total_cost"] for r in selected]) if selected and len(selected) == len(rows) else {"kind": "unknown", "usd": None},
            "unobserved_fallback_cases": len(rows) - len(selected),
            "known_subset_cost": combine_cost(known) if known else {"kind": "unknown", "usd": None},
            "worker_plus_router_latency_ms": distribution([r["latency_ms"] for r in selected])}
    comparisons = {}
    for strategy in ("baseline", "cheapest_eligible"):
        pairs = [(r["outcomes"]["jev"], r["outcomes"][strategy]) for r in rows]
        labeled = [(a,b) for a,b in pairs if a["acceptable"] is not None and b["acceptable"] is not None]
        priced = [(a,b) for a,b in labeled if a["total_cost"]["kind"] != "unknown" and b["total_cost"]["kind"] != "unknown"]
        passing = [(a,b) for a,b in priced if a["acceptable"] and b["acceptable"]]
        comparisons[strategy] = {"route_disagreement": rate(sum(a["profile_id"] != b["profile_id"] for a,b in pairs), len(pairs)),
            "observed_underroute": rate(sum(not a["acceptable"] and b["acceptable"] for a,b in labeled), len(labeled)),
            "observed_overroute": rate(sum(a["total_cost"]["usd"] > b["total_cost"]["usd"] for a,b in passing), len(passing)),
            "paired_passing_cost_difference_usd": sum(b["total_cost"]["usd"]-a["total_cost"]["usd"] for a,b in passing) if passing else None,
            "paired_passing_cost_count": len(passing),
            "cost_kind": "estimated" if any(a["total_cost"]["kind"] == "estimated" or b["total_cost"]["kind"] == "estimated" for a,b in passing) else "measured" if passing else "unknown"}
    out["comparisons"] = comparisons
    return out


def benchmark(data):
    validate(data)
    calibration = [c for c in data["cases"] if c["split"] == "calibration"]
    test = [c for c in data["cases"] if c["split"] == "test"]
    sweeps = [evaluate(calibration, data, t) for t in sorted(data["thresholds"])]
    # Threshold evidence excludes direct user/pin routes which never consulted Jev.
    usable = [r for r in sweeps if r["summary"]["inference_evaluated"]["strategies"]["jev"]["quality_pass"]["denominator"]
              and r["summary"]["inference_evaluated"]["strategies"]["jev"]["label_coverage"]["rate"] == 1
              and r["summary"]["capture_coverage"]["rate"] == 1]
    def objective(r):
        s = r["summary"]["inference_evaluated"]["strategies"]["jev"]
        g = s["group_failure_risk"]
        return (g["rate"], -(g["denominator"] - g["numerator"]), -r["threshold"])
    target = data["risk_target"]
    safe = [r for r in usable if r["summary"]["inference_evaluated"]["strategies"]["jev"]["group_failure_risk"]["denominator"] >= target["minimum_labeled_groups"]
            and r["summary"]["inference_evaluated"]["strategies"]["jev"]["group_failure_risk"]["wilson_95"][1] <= target["max_false_acceptance_upper"]]
    chosen = min(safe, key=objective)["threshold"] if safe else None
    # Freeze the existing threshold before viewing test data when calibration is insufficient.
    frozen = chosen if chosen is not None else data["policy"]["jev"]["suitability_threshold"]
    heldout = evaluate(test, data, frozen) if test else None
    return {"schema": "ultra-delegation-benchmark-report-v1", "dataset_id": data["dataset_id"],
            "input_hash": jev.hash_value(data), "policy_hash": jev.hash_value(data["policy"]),
            "synthetic": data["synthetic"], "model": data["policy"]["jev"]["model"], "rubric": data["rubric"],
            "status": "synthetic-demo" if data["synthetic"] else "observed-replay" if heldout and heldout["summary"]["capture_coverage"]["rate"] == 1 and heldout["summary"]["strategies"]["jev"]["quality_pass"]["denominator"] else "pending",
            "qualification": "pending", "realized_savings_usd": None,
            "selection_method": "calibration-only, inference-evaluated dispatches only: require minimum fully labeled groups and group Wilson upper risk target, minimize group failure rate, maximize passing groups, then higher threshold",
            "candidate_threshold": chosen if not data["synthetic"] else None, "frozen_test_threshold": frozen,
            "risk_target": target, "deployment_recommendation": None,
            "calibration": sweeps, "test": heldout,
            "limitations": ["Replay comparisons are counterfactual, never realized savings.",
                            "Independent reviewer assertions require external provenance audit.",
                            "Case intervals are descriptive under an IID assumption; threshold safety uses group failure intervals assuming independent groups.",
                            "Latency excludes packet preparation and unobserved coordinator fallback.",
                            "Qualified deployment requires an independently approved sample size and risk target."]}


def markdown(report):
    lines = ["# Jev downstream routing benchmark", "", f"Dataset: `{report['dataset_id']}`. Status: **{report['status']}**.",
             "", f"Qualification: **{report['qualification']}**. Realized savings: **not established**.",
             f"Calibration candidate threshold: `{report['candidate_threshold']}`. Frozen test threshold: `{report['frozen_test_threshold']}`. Deployment recommendation: **none**.",
             "", "| Split | Threshold | Cases | Routed | Independently labeled | Passed | False acceptances |", "|---|---:|---:|---:|---:|---:|---:|"]
    for name, runs in (("calibration", report["calibration"]), ("test", [report["test"]] if report["test"] else [])):
        for run in runs:
            s = run["summary"]["strategies"]["jev"]
            lines.append(f"| {name} | {run['threshold']} | {run['summary']['cases']} | {s['dispatch_coverage']['numerator']} | {s['quality_pass']['denominator']} | {s['quality_pass']['numerator']} | {s['false_acceptance']['numerator']} |")
    lines += ["", "Threshold selection uses only independently labeled groups whose dispatches consulted captured Jev inference. User choices and project pins remain in overall production-policy metrics but cannot qualify a threshold."]
    if report["test"]:
        summary = report["test"]["summary"]
        subset = summary["inference_evaluated"]["strategies"]["jev"]["group_failure_risk"]
        lines += ["", f"Held-out inference-evaluated group failures: {subset['numerator']} / {subset['denominator']}; Wilson 95% interval: {subset['wilson_95']}."]
        lines += ["", "## Untouched test comparison", "", "| Strategy | Pass / labeled dispatches | Failed / labeled groups | Group failure risk Wilson 95% | Total cost | Unknown cost dispatches | Median worker + router ms |", "|---|---:|---:|---|---|---:|---:|"]
        for strategy, row in summary["strategies"].items():
            passed, risk, spend = row["quality_pass"], row["group_failure_risk"]["wilson_95"], row["total_cost"]
            groups = row["group_failure_risk"]
            bounds = f"{risk[0]:.3f} to {risk[1]:.3f}" if risk else "unknown"
            price = f"${spend['usd']:.6f} ({spend['kind']})" if spend["usd"] is not None else "unknown"
            lines.append(f"| {strategy} | {passed['numerator']} / {passed['denominator']} | {groups['numerator']} / {groups['denominator']} | {bounds} | {price} | {row['unknown_cost_count']} | {row['worker_plus_router_latency_ms']['median']} |")
        lines += ["", "All cost differences are paired counterfactual comparisons. Missing costs are excluded from paired differences and remain visible as unknown costs."]
    lines += ["", "The companion JSON contains denominators, Wilson 95% intervals, per-family results, paired comparator costs, unknown costs, latency and reviewer/artifact provenance.", ""]
    lines += [f"- {item}" for item in report["limitations"]]
    return "\n".join(lines) + "\n"


def demo():
    p = fixtures.policy()
    data = {"schema": SCHEMA, "dataset_id": "synthetic-routing-demo-v1", "synthetic": True, "policy": p,
            "rubric": {"version": "downstream-v1", "minimum_scores": {"coverage": 75, "scope": 75, "evidence": 75, "clarity": 50}, "quality_floor": 80},
            "thresholds": [.8, .9, .95], "risk_target": {"max_false_acceptance_upper": .1, "minimum_labeled_groups": 30}, "cases": []}
    zero = {"kind": "measured", "usd": 0}
    for i in range(8):
        packet = fixtures.route_fixture()
        packet["run_id"] = f"demo-{i}"
        if i % 2:
            packet["task"]["task_family"] = "python-empty-string-review"
            packet["summary"] = "Review a Python function checking whether a string is empty."
            packet["requirements"] = ["Check empty and nonempty strings", "Do not edit files"]
            for candidate in packet["candidates"]:
                candidate["profile"]["task_family"] = packet["task"]["task_family"]
        # Varied independent groups, with deliberately defective and uncertain cases.
        if i % 4 == 3:
            packet["summary"] = "The desired behavior is ambiguous; no expected output was supplied."
        rows = [r for r in jev.route_ranking(packet, p) if r["eligible"]]
        payload = jev.route_payload(packet, rows, p)
        answers = {name: {"type": "noul", "noul": .7 if name == "ambiguous" and i % 4 == 3 else 0 if name in ("retain", "ambiguous") else (.85 if name == "fit_0" and i % 4 == 1 else .98)} for name in payload["questions"]}
        observations = []
        for j, row in enumerate(rows):
            scores = dict.fromkeys(DIMENSIONS, 100)
            if j == 0 and i % 4 == 1:
                scores["coverage"] = 25
            observations.append({"profile_id": row["profile_id"], "artifact_hash": jev.hash_value({"fixture": i, "worker": j}),
                "gates": [{"id": "syntax", "mandatory": True, "passed": True}], "scores": scores,
                "critical_failures": ["incorrect-behavior"] if i % 4 == 3 else [],
                "reviewer": {"id": "authored-synthetic-reference-v1", "independent": True, "kind": "synthetic"},
                "costs": {"worker": {"kind": "measured", "usd": .01*(j+1)}, "retry": zero, "review": zero}, "latency_ms": 100*(j+1)})
        if i % 4 == 2:
            observations[0]["costs"]["worker"] = {"kind": "unknown", "usd": None}
        data["cases"].append({"id": f"case-{i}", "group_id": f"group-{i}", "split": "calibration" if i < 4 else "test", "packet": packet,
            "preparation_cost": zero, "capture": {"payload_hash": jev.hash_value(payload), "response": {"model": p["jev"]["model"], "answers": answers, "usage": {"input_tokens": 100, "output_tokens": 10}},
                "latency_ms": 20+i, "cost": {"kind": "estimated", "usd": .0000042}}, "observations": observations})
    return data


def main():
    parser = jev.SafeParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path)
    source.add_argument("--demo", action="store_true")
    parser.add_argument("--output-prefix", required=True, type=Path)
    parser.add_argument("--emit-demo-input", type=Path)
    args = parser.parse_args()
    try:
        data = demo() if args.demo else read_dataset(args.input)
        result = benchmark(data)
        if args.emit_demo_input:
            need(args.demo, "emit-demo-requires-demo")
            with args.emit_demo_input.open("x", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        paths = [Path(str(args.output_prefix) + suffix) for suffix in (".json", ".md")]
        need(not any(p.exists() for p in paths), "output-already-exists")
        with paths[0].open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, allow_nan=False)
        with paths[1].open("x", encoding="utf-8") as f:
            f.write(markdown(result))
        print(json.dumps({"status": result["status"], "qualification": result["qualification"], "candidate_threshold": result["candidate_threshold"]}))
    except (ValueError, KeyError, TypeError, OSError):
        print("benchmark-invalid-or-unavailable", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
