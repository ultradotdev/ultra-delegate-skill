#!/usr/bin/env python3
"""Optional Jev decisions. Never executes workers or changes acceptance evidence."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ultra_delegation as ud
import jev_transport as transport
from evidence import PROFILE, validate_outcome, validate_public_value, sanitize_learning
from jev_contract import DEFAULT_JEV_POLICY, PRICE, RUBRIC, event_record, validate_policy
from jev_questions import route_questions, judge_questions, ROUTING_QUESTION_VERSION, JUDGING_QUESTION_VERSION


def hash_value(value):
    return hashlib.sha256(ud.canonical(value).encode()).hexdigest()


class PacketError(ValueError):
    """Fixed diagnostic codes without echoing input data."""


def require(condition, code):
    if not condition: raise PacketError(code)


def fields(value, allowed, required=()):
    require(isinstance(value, dict) and not set(value) - set(allowed) and set(required) <= set(value), "invalid-input-fields")


def text(value):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= 4096, "invalid-input-text")
    validate_public_value(value)
    return value


def read_packet(path):
    if path == "-":
        data = sys.stdin.buffer.read(1024 * 1024 + 1)
    else:
        with Path(path).open("rb") as f: data = f.read(1024 * 1024 + 1)
    require(len(data) <= 1024 * 1024, "input-too-large")
    try: return json.loads(data, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError): raise PacketError("invalid-input-json") from None


def run_id(value):
    ud.guard_run_dir(Path("."), value)
    return value


def validate_route(packet):
    fields(packet, {"run_id", "summary", "task", "requirements", "context", "candidates", "records", "snapshot", "experiment"},
           {"run_id", "summary", "task", "requirements", "context", "candidates", "snapshot"})
    run_id(packet["run_id"]); text(packet["summary"])
    require(isinstance(packet["requirements"], list) and 0 < len(packet["requirements"]) <= 24, "invalid-requirements")
    for item in packet["requirements"]: text(item)
    require(isinstance(packet["task"], dict) and isinstance(packet["context"], dict) and isinstance(packet["snapshot"], dict), "invalid-context")
    task = packet["task"]
    require(all(task.get(k) for k in ("task_family", "operation", "risk", "coupling", "language", "validation", "tools")), "incomplete-task-signature")
    validate_public_value(task); validate_public_value(packet["context"]); validate_public_value(packet["snapshot"])
    candidates = packet["candidates"]
    require(isinstance(candidates, list) and len(candidates) <= 128, "invalid-candidates")
    ids = set()
    for c in candidates:
        fields(c, {"profile", "description", "user_selected", "imported_prior", "source"}, {"profile", "description"})
        fields(c["profile"], PROFILE)
        ud.validate_profile(c["profile"]); validate_public_value(c["profile"]); text(c["description"])
        require(type(c.get("user_selected", False)) is bool, "invalid-user-selection")
        pid = ud.profile_id(c["profile"])
        require(pid not in ids, "duplicate-profile"); ids.add(pid)
        if "imported_prior" in c: sanitize_learning(c["imported_prior"])
    records = packet.get("records", [])
    require(isinstance(records, list), "invalid-evidence")
    for record in records:
        validate_outcome(record)
        ud.validate_profile(record["profile"])
    if "experiment" in packet:
        fields(packet["experiment"], {"variable", "isolation", "max_candidates"}, {"variable", "isolation"})
        require(packet["experiment"]["variable"] in ("model", "thinking", "prompt_profile"), "invalid-experiment-variable")
        require(packet["experiment"]["isolation"] in ("read_only", "patch_proposal"), "invalid-experiment-isolation")
        n = packet["experiment"].get("max_candidates", 3)
        require(type(n) is int and 2 <= n <= 3, "invalid-experiment-size")
    return packet


def route_ranking(packet, policy):
    return ud.rank_candidates(packet["task"], packet["context"], packet["candidates"], [validate_outcome(r) for r in packet.get("records", [])], policy)["ranked"]


def context_allowed(packet, policy, root=None):
    allowed = ud.evaluate_guard(packet["snapshot"], policy)["delegation_allowed"]
    if root is not None:
        saved = ud.guard_run_dir(root, packet["run_id"]) / "guard-state.json"
        if saved.exists() and not ud.read_json(saved).get("delegation_allowed", False): return False
    return allowed


def retain_task(packet, policy):
    task = packet["task"]
    retained = policy.get("orchestrator", {}).get("retain", ["architecture", "integration", "security_sensitive", "tightly_coupled", "final_verification"])
    return (task["risk"] != "low" or task["coupling"] != "low" or
            task["operation"] in retained or task["task_family"] in retained)


def base_event(kind, packet, policy):
    p = policy["jev"]
    e = {"schema": "ultra-delegation-jev-v1", "run_id": packet["run_id"], "created_at": ud.now(),
         "kind": kind, "mode": p["routing" if kind == "route" else "judging"],
         "status": "skipped", "action": "coordinator", "selected_profile_id": None,
         "baseline_profile_id": None, "recommended_action": "coordinator", "recommended_profile_id": None,
         "nominated_profile_ids": [], "reason_codes": [], "input_hash": hash_value(packet),
         "policy_hash": hash_value(policy), "model": p["model"], "rubric_version": p["rubric_version"],
         "question_hash": None, "question_version": ROUTING_QUESTION_VERSION if kind == "route" else JUDGING_QUESTION_VERSION,
         "probabilities": {}, "usage": None, "attempts": 0,
         "latency_ms": 0, "estimated_cost_usd": None, "cost_kind": "unavailable", "price_date": None,
         "disagreement": None}
    e["id"] = hash_value({"input": e["input_hash"], "policy": e["policy_hash"], "kind": kind, "at": time.time_ns()})
    return e


def inference(payload, event, policy, key=None, call=None):
    event["question_hash"] = hash_value(payload["questions"])
    started = time.monotonic()
    try:
        transport.encoded_payload(payload)
        if key is None: key, _ = transport.credential(policy["jev"]["credential_ref"], service=policy["jev"]["credential_service"])
        result, meta = (call or transport.request)(payload, key)
        event.update({k: meta[k] for k in ("attempts", "latency_ms")})
        probabilities, usage = transport.validate_response(payload, result)
        event.update(probabilities=probabilities, usage=usage)
        # Retried calls may have been billed even if their response was lost.
        if event["model"] == PRICE["model"] and event["attempts"] == 1:
            event.update(estimated_cost_usd=usage["input_tokens"] * PRICE["input_per_million_usd"] / 1_000_000,
                         cost_kind="estimated", price_date=PRICE["date"])
        return result["answers"]
    except transport.ServiceError as error:
        event.update(status="unavailable", reason_codes=[error.code],
                     attempts=max(event["attempts"], error.attempts), latency_ms=(time.monotonic() - started) * 1000)
        return None


def route_payload(packet, rows, policy):
    by_id = {ud.profile_id(c["profile"]): c for c in packet["candidates"]}
    cards = []
    questions = route_questions(len(rows))
    for i, row in enumerate(rows):
        c = by_id[row["profile_id"]]
        cards.append({"profile_id": row["profile_id"], "description": c["description"], "profile": c["profile"],
                      "evidence_status": row["status"], "stats": row["stats"]})

    return {"model": policy["jev"]["model"], "state": {"summary": packet["summary"], "task": packet["task"],
            "requirements": packet["requirements"], "candidates": cards}, "questions": questions}


def experiment_group(packet, rows, policy):
    spec = packet.get("experiment")
    if not spec: return []
    # Notifications-only nominations are low-risk proposals, never dispatch permission.
    by_id = {ud.profile_id(c["profile"]): c["profile"] for c in packet["candidates"]}
    exp = policy.get("experiments", {})
    allowed_modes = exp.get("notification_isolation", ["read_only", "patch_proposal"])
    if spec["isolation"] not in allowed_modes: return []
    ceiling = {"off": 0, "low": 1, "medium": 2, "high": 3, "xhigh": 4, "max": 5}
    maximum = min(2, ceiling.get(exp.get("notification_max_reasoning", "medium"), -1))
    rows = [r for r in rows if ceiling.get(by_id[r["profile_id"]]["thinking"]["normalized"], 99) <= maximum]
    varying = {"model", "model_revision"} if spec["variable"] == "model" else {spec["variable"]}
    constants = {"task_family", "provider", "model", "model_revision", "host", "thinking", "prompt_profile", "tool_policy"} - varying
    limit = min(spec.get("max_candidates", 3), exp.get("max_notification_candidates", 3), 3)
    for r in rows:
        p = by_id[r["profile_id"]]
        group = [x for x in rows if all(by_id[x["profile_id"]].get(k, by_id[x["profile_id"]].get("model") if k == "model_revision" else None) == p.get(k, p.get("model") if k == "model_revision" else None) for k in constants)]
        if len(group) >= 2 and any(x["tier"] == 1 for x in group):
            return [x["profile_id"] for x in group[:limit]] if limit >= 2 else []
    return []


def route(packet, policy, root=None, dry_run=False, key=None, call=None):
    validate_route(packet)
    e = base_event("route", packet, policy)
    ranking = route_ranking(packet, policy)
    e["ranking"] = ranking
    rows = [r for r in ranking if r["eligible"]]
    baseline = rows[0] if rows else None
    e["baseline_profile_id"] = baseline["profile_id"] if baseline else None
    def stop(reason):
        e["reason_codes"] = [reason]
        return e
    if not context_allowed(packet, policy, root): return stop("context-stop")
    if retain_task(packet, policy): return stop("coordinator-owned")
    if not rows: return stop("no-eligible-candidates")
    if baseline["tier"] >= 4:
        e.update(action="route", selected_profile_id=baseline["profile_id"], recommended_action="route", recommended_profile_id=baseline["profile_id"])
        return stop("user-or-project-choice")
    if e["mode"] == "off": return stop("routing-disabled")
    if not policy["jev"]["share_summaries"]: return stop("summary-sharing-disabled")
    if len(rows) > 12: return stop("broader-comparison-required")
    payload = route_payload(packet, rows, policy)
    transport.encoded_payload(payload)
    if dry_run:
        return {"dry_run": True, "payload": payload, "ranking": ranking, "input_hash": e["input_hash"], "policy_hash": e["policy_hash"]}
    answers = inference(payload, e, policy, key, call)
    if answers is None: return e
    if not context_allowed(packet, policy, root):
        e.update(status="abstained", reason_codes=["context-stop"])
        return e
    threshold = policy["jev"]["suitability_threshold"]
    e["uncertainty"] = {"ambiguity_probability": answers["ambiguous"]["noul"], "coordinator_probability": answers["retain"]["noul"], "threshold": threshold}
    if answers["ambiguous"]["noul"] > 1 - threshold or answers["retain"]["noul"] > 1 - threshold:
        e.update(status="abstained", reason_codes=["uncertain-or-coordinator-owned"])
    else:
        suitable = [r for i, r in enumerate(rows) if answers[f"fit_{i}"]["noul"] >= threshold]
        established = [r for r in suitable if r["tier"] >= 2]
        if established:
            chosen = established[0]  # Pure ranking already sorts evidence tier, then cost.
            e.update(status="ok", recommended_action="route", recommended_profile_id=chosen["profile_id"], reason_codes=["suitable-evidence-backed-profile"])
        else:
            nominations = experiment_group(packet, suitable, policy)
            if nominations:
                e.update(status="ok", recommended_action="experiment", nominated_profile_ids=nominations, reason_codes=["controlled-experiment-required"])
            else:
                e.update(status="abstained", reason_codes=["insufficient-suitable-evidence"])
    if e["mode"] == "active":
        e.update(action=e["recommended_action"], selected_profile_id=e["recommended_profile_id"])
    else:
        # A provisional baseline is not an automatic executable route.
        if baseline["tier"] >= 2:
            e.update(action="route", selected_profile_id=baseline["profile_id"])
        e["disagreement"] = (e["recommended_action"], e["recommended_profile_id"]) != (e["action"], e["selected_profile_id"])
    e["pending_verification"] = bool(next((r["pending_verification"] for r in rows if r["profile_id"] == e["selected_profile_id"]), False))
    return e


def validate_judge(packet, policy):
    fields(packet, {"run_id", "requirements", "candidates", "model", "rubric_version"},
           {"run_id", "requirements", "candidates", "model", "rubric_version"})
    run_id(packet["run_id"])
    require(packet["model"] == policy["jev"]["model"] and packet["rubric_version"] == policy["jev"]["rubric_version"], "judge-version-mismatch")
    require(isinstance(packet["requirements"], list) and 0 < len(packet["requirements"]) <= 24, "invalid-requirements")
    for r in packet["requirements"]: text(r)
    require(isinstance(packet["candidates"], list) and 1 <= len(packet["candidates"]) <= 3, "invalid-judge-candidates")
    for c in packet["candidates"]:
        fields(c, {"excerpts", "gates", "validation_summary", "reference_score", "reference_acceptable"}, {"excerpts", "gates", "validation_summary"})
        require(isinstance(c["excerpts"], list) and 1 <= len(c["excerpts"]) <= 12, "invalid-excerpts")
        for excerpt in c["excerpts"]: text(excerpt)
        text(c["validation_summary"])
        require(isinstance(c["gates"], list) and 1 <= len(c["gates"]) <= 24, "observed-gates-required")
        mandatory = False
        for g in c["gates"]:
            fields(g, {"id", "mandatory", "passed"}, {"id", "mandatory", "passed"})
            text(g["id"])
            require(type(g["mandatory"]) is bool and type(g["passed"]) is bool, "invalid-gate-result")
            mandatory |= g["mandatory"]
        require(mandatory, "mandatory-gate-required")
        if "reference_score" in c: require(transport.number(c["reference_score"], 0, 100), "invalid-reference-score")
        if "reference_acceptable" in c: require(type(c["reference_acceptable"]) is bool, "invalid-reference-verdict")
    return packet


def judge_payload(packet, policy):
    candidates = [{k: c[k] for k in ("excerpts", "gates", "validation_summary")} for c in packet["candidates"]]
    questions = judge_questions(len(candidates), RUBRIC)
    return {"model": packet["model"], "state": {"requirements": packet["requirements"], "candidates": candidates}, "questions": questions}


def judge(packet, policy, dry_run=False, key=None, call=None, root=None):
    validate_judge(packet, policy)
    if root is not None:
        earlier = ud.read_jsonl(root / "jev" / "decisions.jsonl")
        require(all(row.get("model") == packet["model"] and row.get("rubric_version") == packet["rubric_version"]
                    for row in earlier if row.get("kind") == "judge" and row.get("run_id") == packet["run_id"]), "judge-run-version-changed")
    e = base_event("judge", packet, policy)
    if e["mode"] == "off" or not policy["jev"]["share_artifacts"]:
        e["reason_codes"] = ["judging-disabled" if e["mode"] == "off" else "artifact-sharing-disabled"]
        return e
    payload = judge_payload(packet, policy)
    transport.encoded_payload(payload)
    if dry_run: return {"dry_run": True, "payload": payload, "input_hash": e["input_hash"], "policy_hash": e["policy_hash"]}
    answers = inference(payload, e, policy, key, call)
    if answers is None: return e
    e.update(status="ok", reason_codes=["shadow-only"], shadow_scores={}, reference_comparison={})
    disagreements = []
    for i, c in enumerate(packet["candidates"]):
        enough = answers[f"enough_{i}"]["noul"] >= policy["jev"]["suitability_threshold"]
        scores = {d: answers[f"{d}_{i}"]["score"] * 25 for d in RUBRIC}
        gates = all(g["passed"] for g in c["gates"] if g["mandatory"])
        score = sum(scores.values()) / len(scores) if enough else None
        suggest = (score >= policy["quality_floor"] and gates) if score is not None else None
        e["shadow_scores"][f"candidate_{i}"] = {"score": score, "dimensions": scores, "sufficient_evidence": enough,
                                                  "mandatory_gates_passed": gates, "suggested_acceptable": suggest}
        if "reference_acceptable" in c:
            comparison = {"disagreed": suggest != c["reference_acceptable"] if suggest is not None else None,
                          "false_acceptance": suggest is True and c["reference_acceptable"] is False,
                          "abstained": suggest is None}
            if score is not None and "reference_score" in c: comparison["absolute_score_error"] = abs(score - c["reference_score"])
            e["reference_comparison"][f"candidate_{i}"] = comparison
            if comparison["disagreed"] is not None: disagreements.append(comparison["disagreed"])
    e["disagreement"] = any(disagreements) if disagreements else None
    return e


def recheck(packet, decision, policy, root):
    validate_route(packet)
    event = event_record(decision)
    saved = ud.read_jsonl(root / "jev" / "decisions.jsonl")
    require(any(row == event for row in saved), "decision-not-recorded-or-changed")
    require(decision["mode"] == policy["jev"]["routing"] and decision["status"] in ("ok", "skipped", "abstained"), "decision-mode-or-status-invalid")
    require(decision["kind"] == "route" and decision["action"] == "route", "decision-not-executable")
    require(decision["input_hash"] == hash_value(packet) and decision["policy_hash"] == hash_value(policy), "decision-inputs-changed")
    age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(decision["created_at"])).total_seconds()
    require(0 <= age <= 300, "decision-expired")
    require(context_allowed(packet, policy, root) and not retain_task(packet, policy), "context-or-task-stop")
    rows = route_ranking(packet, policy)
    selected = next((r for r in rows if r["profile_id"] == decision["selected_profile_id"]), None)
    require(selected is not None and selected["eligible"] and selected["tier"] >= 2, "profile-no-longer-qualified")
    require(not any(r["eligible"] and r["tier"] >= 4 and r["profile_id"] != selected["profile_id"] for r in rows), "user-or-project-choice-changed")
    return {"dispatch_allowed": True, "profile_id": selected["profile_id"], "execution": "host-owned", "pending_verification": selected["pending_verification"]}


def write_event(root, result):
    e = event_record(result)
    target = root / "jev"
    require(not target.is_symlink(), "ledger-directory-symlink")
    # Existing projects may predate the helper's ignore entry.
    ignore = root.parent / ".gitignore"
    require(not ignore.is_symlink(), "ignore-file-symlink")
    lines = ignore.read_text().splitlines() if ignore.exists() else []
    entry = f"{root.name}/jev/"
    if entry not in lines: ud.write_text(ignore, "\n".join(lines + [entry]) + "\n")
    ud.append_jsonl(target / "decisions.jsonl", e)


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, '{"error": "invalid-command-arguments"}\n')


def parser():
    p = SafeParser(description=__doc__)
    p.add_argument("--root")
    subs = p.add_subparsers(dest="command", required=True)
    a = subs.add_parser("auth"); a.add_argument("action", choices=("status", "check"))
    c = subs.add_parser("configure")
    c.add_argument("--routing", choices=("off", "shadow", "active"))
    c.add_argument("--judging", choices=("off", "shadow"))
    c.add_argument("--share-summaries", choices=("yes", "no"))
    c.add_argument("--share-artifacts", choices=("yes", "no"))
    c.add_argument("--credential-service"); c.add_argument("--credential-ref"); c.add_argument("--model"); c.add_argument("--suitability-threshold", type=float)
    for name in ("route", "judge"):
        s = subs.add_parser(name); s.add_argument("--input", required=True)
        g = s.add_mutually_exclusive_group(); g.add_argument("--dry-run", action="store_true"); g.add_argument("--write", action="store_true")
    s = subs.add_parser("recheck"); s.add_argument("--input", required=True); s.add_argument("--decision", required=True)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        root = ud.root_from(args)
        policy = ud.load_policy(root)
        if args.command == "auth":
            result = transport.auth(args.action, policy["jev"]["credential_ref"], policy["jev"]["model"], service=policy["jev"]["credential_service"])
        elif args.command == "configure":
            raw = ud.read_json(ud.policy_path(root), {})
            updates = {k: getattr(args, k) for k in DEFAULT_JEV_POLICY if hasattr(args, k) and getattr(args, k) is not None}
            for k in ("share_summaries", "share_artifacts"):
                if k in updates: updates[k] = updates[k] == "yes"
            raw["jev"] = validate_policy({**policy["jev"], **updates})
            ud.write_json(ud.policy_path(root), raw)
            result = {"jev": raw["jev"], "credentials_stored": False}
        elif args.command == "recheck":
            result = recheck(read_packet(args.input), read_packet(args.decision), policy, root)
        else:
            packet = read_packet(args.input)
            if args.command == "route": result = route(packet, policy, root, args.dry_run)
            else: result = judge(packet, policy, args.dry_run, root=root)
            if args.write: write_event(root, result)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except transport.ServiceError as e:
        print(json.dumps({"error": e.code}), file=sys.stderr)
    except PacketError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
    except (ValueError, TypeError, KeyError, OSError, ud.UserError):
        # Inputs can contain credentials or project content. Do not echo exception text.
        print(json.dumps({"error": "invalid-input-or-local-state"}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
