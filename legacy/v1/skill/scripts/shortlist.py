#!/usr/bin/env python3
"""Offline preparation of a bounded candidate pool. Never authorizes dispatch."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ultra_delegation as ud
from evidence import PROFILE, validate_outcome, validate_public_value, sanitize_learning

ASSET = Path(__file__).resolve().parents[1] / "assets" / "standing-shortlist.json"
SCHEMA = "ultra-delegation-shortlist-v1"
MAX_INPUT = 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def standing_seeds():
    """Read the versioned shipped seed definitions, not local task evidence."""
    return json.loads(ASSET.read_text(encoding="utf-8"))


def _profile(profile):
    require(isinstance(profile, dict) and not set(profile) - set(PROFILE), "invalid-profile-fields")
    require(all(isinstance(v, str) and v.strip() for k, v in profile.items() if k != "thinking"), "invalid-profile-values")
    ud.validate_profile(profile)
    validate_public_value(profile)
    return ud.profile_id(profile)


def _stamp(record):
    value = record.get("created_at")
    require(isinstance(value, str), "worker-evidence-requires-created-at")
    try:
        stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise ValueError("invalid-evidence-created-at") from None
    require(stamp.tzinfo is not None, "evidence-created-at-needs-timezone")
    return stamp


def build_shortlist(packet, policy=None):
    """Merge exact provided profiles and validated outcomes, then use existing ranker.

    Caller-supplied outcomes must already be independently reviewed worker evidence.
    This validates their contract; it cannot verify that a caller told the truth.
    """
    require(isinstance(packet, dict), "invalid-shortlist-packet")
    require(not set(packet) - {"task", "context", "candidates", "records", "seed_profile", "limit", "policy"}, "invalid-shortlist-fields")
    task, context = packet.get("task"), packet.get("context")
    require(isinstance(task, dict) and isinstance(context, dict), "task-and-context-required")
    require(all(task.get(k) for k in ("task_family", "operation", "risk", "coupling", "language", "validation", "tools")), "incomplete-task-signature")
    validate_public_value(task); validate_public_value(context)
    require(policy is None or "policy" not in packet, "ambiguous-policy-input")
    raw_policy = packet.get("policy", {}) if policy is None else policy
    require(isinstance(raw_policy, dict), "invalid-policy")
    policy = {**copy.deepcopy(ud.DEFAULT_POLICY), **copy.deepcopy(raw_policy)}
    limit = packet.get("limit", 12)
    require(type(limit) is int and 1 <= limit <= 12, "limit-must-be-1-through-12")
    candidates, raw_records = packet.get("candidates", []), packet.get("records", [])
    require(isinstance(candidates, list) and len(candidates) <= 128, "invalid-candidate-pool")
    require(isinstance(raw_records, list) and len(raw_records) <= 1024, "invalid-worker-evidence")
    pool, origins, records, ignored = {}, {}, [], []

    def add(candidate, origin):
        pid = _profile(candidate["profile"])
        if pid in pool:
            previous, incoming = pool[pid]["profile"], candidate["profile"]
            require({"model_revision": previous["model"], **previous} == {"model_revision": incoming["model"], **incoming}, "conflicting-profile-metadata")
        else:
            pool[pid] = copy.deepcopy(candidate)
        origins.setdefault(pid, [])
        if origin not in origins[pid]: origins[pid].append(origin)
        return pid

    for candidate in candidates:
        require(isinstance(candidate, dict) and not set(candidate) - {"profile", "description", "user_selected", "source", "imported_prior"}, "invalid-candidate-fields")
        require("profile" in candidate and isinstance(candidate.get("description"), str) and bool(candidate["description"].strip()), "candidate-profile-and-description-required")
        validate_public_value(candidate["description"])
        if "source" in candidate:
            require(isinstance(candidate["source"], str), "invalid-candidate-source")
            validate_public_value(candidate["source"])
        require(type(candidate.get("user_selected", False)) is bool, "invalid-user-selection")
        if "imported_prior" in candidate:
            candidate = {**candidate, "imported_prior": sanitize_learning(candidate["imported_prior"])}
        pid = _profile(candidate["profile"])
        require(pid not in pool, "duplicate-project-candidate")
        add(candidate, "project-candidate")

    seen_records = set()
    for index, raw in enumerate(raw_records):
        record = validate_outcome(raw)
        pid = _profile(record["profile"])
        require(record.get("profile_id", pid) == pid, "worker-profile-id-mismatch")
        stamp = _stamp(record)
        # Duplicate observations cannot manufacture the minimum sample count.
        identity = record.get("id") or ud.digest(record, 64)
        require(identity not in seen_records, "duplicate-worker-evidence")
        seen_records.add(identity)
        if ud.compatibility(record, task, context)[0] != 1.0:
            ignored.append({"record_index": index, "profile_id": pid, "reason": "task-or-scope-mismatch"})
            continue
        records.append((stamp, index, record))
        add({"profile": record["profile"], "description": "Candidate from supplied worker outcomes for the exact task signature; consult ranked evidence status.", "source": "local-worker-evidence"}, "local-worker-evidence")
    # Freshness and latest failure semantics must not depend on input array order.
    records = [r for _, _, r in sorted(records, key=lambda item: (
        item[0], not ud.all_gates_pass(item[2]) or bool(item[2].get("regression")),
        item[2].get("selections_since_test", 0), item[2].get("id") or ud.digest(item[2], 64)))]

    asset = standing_seeds()
    seed_profile = packet.get("seed_profile")
    if seed_profile is not None:
        require(isinstance(seed_profile, dict) and set(seed_profile) == {"prompt_profile", "tool_policy"}, "seed-profile-needs-prompt-and-tool-policy")
        require(all(isinstance(v, str) and v.strip() for v in seed_profile.values()), "invalid-seed-profile")
        validate_public_value(seed_profile)
        for seed in asset["seeds"]:
            profile = {k: copy.deepcopy(seed[k]) for k in ("host", "provider", "model", "thinking", "execution_location")}
            profile.update(task_family=task["task_family"], model_revision=seed["model"], **seed_profile)
            pid = _profile(profile)
            if pid in pool:
                # A discovery hint cannot override an exact supplied configuration.
                origins[pid].append("standing-seed:" + seed["id"])
            else:
                add({"profile": profile, "description": seed["description"], "source": "standing-seed"}, "standing-seed:" + seed["id"])

    require(len(pool) <= 256, "combined-candidate-pool-too-large")
    # Sort identities before ranking so equal evidence/cost ties are reproducible.
    ranking = ud.rank_candidates(task, context, [pool[p] for p in sorted(pool)], records, policy)["ranked"]
    for row in ranking:
        if pool[row["profile_id"]]["profile"]["task_family"] != task["task_family"]:
            row.update(eligible=False, reason="task family mismatch")
    eligible = [r for r in ranking if r["eligible"]]
    baseline = next((r["profile_id"] for r in eligible if r["tier"] >= 2), None)
    evidence_tier = max((r["tier"] for r in eligible if 2 <= r["tier"] <= 3), default=0)
    protected = {r["profile_id"] for r in eligible if r["tier"] >= 4 or (evidence_tier and r["tier"] == evidence_tier)}
    if baseline: protected.add(baseline)
    # Failed/stale profiles remain visible for controlled retests but lose exploratory priority.
    eligible.sort(key=lambda r: (-r["tier"], r["status"] == "retest-required", r["cost_usd"] is None,
                                 r["cost_usd"] if r["cost_usd"] is not None else float("inf"),
                                 -(r["stats"]["conservative_quality"] or -1), r["profile_id"]))
    overflow = len(protected) > limit
    chosen = [] if overflow else [r["profile_id"] for r in eligible if r["profile_id"] in protected]
    if not overflow:
        chosen += [r["profile_id"] for r in eligible if r["profile_id"] not in protected][:limit-len(chosen)]
    selected = set(chosen)
    rationale = []
    for row in ranking:
        pid = row["profile_id"]
        reason = row["reason"] if not row["eligible"] else "protected-pool-exceeds-limit" if overflow else "protected" if pid in protected else "ranked-in-pool" if pid in selected else "outside-shortlist-limit"
        rationale.append({**row, "included": pid in selected, "protected": pid in protected,
                          "shortlist_reason": reason, "origins": origins[pid]})
    return {"schema": SCHEMA, "status": "coordinator" if overflow or not chosen else "prepared",
            "reason": "protected-pool-exceeds-limit" if overflow else "no-eligible-candidates" if not chosen else "bounded-pool-prepared",
            "dispatch_authorized": False, "evidence_baseline_profile_id": baseline,
            "candidates": [pool[pid] for pid in chosen], "records": records, "ranked": rationale,
            "ignored_records": ignored, "limit": limit, "standing_version": asset["version"],
            "standing_hash": ud.digest(asset, 64), "input_hash": ud.digest(packet, 64), "policy_hash": ud.digest(policy, 64),
            "worker_evidence_count": len(records), "standing_seeds_enabled": seed_profile is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="prepared JSON packet path or - for stdin")
    parser.add_argument("--root", help="optional explicit policy root; no evidence or catalog is read")
    args = parser.parse_args()
    try:
        if args.input == "-": data = sys.stdin.buffer.read(MAX_INPUT + 1)
        else:
            with Path(args.input).open("rb") as handle: data = handle.read(MAX_INPUT + 1)
        require(len(data) <= MAX_INPUT, "input-too-large")
        packet = json.loads(data, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        policy = ud.load_policy(Path(args.root)) if args.root else None
        result = build_shortlist(packet, policy)
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, TypeError, KeyError, OSError, ud.UserError):
        # Invalid data, potentially containing secrets, must not echo into diagnostics.
        print(json.dumps({"status": "invalid", "reason": "invalid-shortlist-input"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
