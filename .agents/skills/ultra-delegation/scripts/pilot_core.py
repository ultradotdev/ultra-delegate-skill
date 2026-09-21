"""Pure contracts, evidence, and routing for the experimental v2 project pilot."""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
import re

import jev_transport as transport
from pilot_questions import ROUTING_THRESHOLDS

SCHEMA = "ultra-pilot-policy-v1"
DEFAULTS = {
    "schema": SCHEMA, "mode": "off", "share_summaries": False,
    "share_artifacts": False, "security_check": False,
    "model": "jev-1.13.0", "credential_service": transport.SERVICE,
    "credential_ref": "default", "baseline_id": None, "pin_id": None,
    "excluded_models": [], "quarantined_configurations": [], "shortlist_limit": 8, "allowed_risks": ["low"],
    "minimum_groups": 5, "minimum_success_lower_bound": 0.70,
    "evidence_days": 90, "capability_age_seconds": 300,
    "quality_floor": 80, "dimension_floor": 70,
    "thresholds": copy.deepcopy(ROUTING_THRESHOLDS),
}
KINDS = {"coding", "research", "writing", "data", "planning", "mixed", "other"}
DIMENSIONS = ("coverage", "correctness", "maintainability", "clarity")
COST_COMPONENTS = ("preparation", "worker", "review", "retry", "fallback")


class PilotError(ValueError):
    """Only stable diagnostic codes should be exposed by the CLI."""


def require(ok, code):
    if not ok:
        raise PilotError(code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value)
        require(parsed.tzinfo is not None, "timezone-required")
        return parsed
    except (TypeError, ValueError):
        raise PilotError("invalid-timestamp") from None


def label(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:+/-]{1,128}", value), "invalid-label")
    # Never accept common credential patterns as telemetry labels.
    require(not re.search(r"(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{20,})", value), "invalid-label")
    return value


def prose(value):
    require(isinstance(value, str) and 0 < len(value.strip()) <= 4096, "invalid-text")
    return value


def fields(value, required, optional=()):
    require(isinstance(value, dict) and set(required) <= set(value)
            and not set(value) - set(required) - set(optional), "invalid-fields")


def labels(value):
    require(isinstance(value, list) and len(value) <= 128, "invalid-label-list")
    for item in value:
        label(item)
    require(len(value) == len(set(value)), "duplicate-label")


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, "invalid-integer")


def amount(value):
    require(value is None or transport.number(value, 0, 1e12), "invalid-number")


def policy(value=None):
    value = {} if value is None else value
    require(isinstance(value, dict) and not set(value) - set(DEFAULTS), "invalid-policy")
    require(isinstance(value.get("thresholds", {}), dict), "invalid-thresholds")
    p = copy.deepcopy(DEFAULTS)
    p.update(value)
    p["thresholds"] = {**DEFAULTS["thresholds"], **value.get("thresholds", {})}
    require(p["schema"] == SCHEMA and p["mode"] in {"off", "shadow", "active"}, "invalid-policy")
    for key in ("share_summaries", "share_artifacts", "security_check"):
        require(type(p[key]) is bool, "invalid-policy")
    require(isinstance(p["model"], str) and re.fullmatch(r"jev-\d+\.\d+\.\d+", p["model"]), "unpinned-model")
    for key in ("credential_service", "credential_ref"):
        require(isinstance(p[key], str) and 0 < len(p[key]) <= 256 and p[key].isprintable(), "invalid-credential-locator")
    for key in ("baseline_id", "pin_id"):
        if p[key] is not None:
            label(p[key])
    labels(p["excluded_models"])
    labels(p["quarantined_configurations"])
    labels(p["allowed_risks"])
    require(set(p["allowed_risks"]) <= {"low", "medium", "high"}, "invalid-risk")
    for key in ("minimum_groups", "evidence_days", "capability_age_seconds", "shortlist_limit"):
        integer(p[key], 1)
    require(p["shortlist_limit"] <= 12, "shortlist-too-large")
    for key in ("quality_floor", "dimension_floor"):
        require(transport.number(p[key], 0, 100), "invalid-quality-floor")
    require(transport.number(p["minimum_success_lower_bound"], 0, 1), "invalid-confidence-floor")
    require(set(p["thresholds"]) == set(DEFAULTS["thresholds"]), "invalid-thresholds")
    require(all(transport.number(v) for v in p["thresholds"].values()), "invalid-thresholds")
    return p


def configuration_id(candidate):
    # Task-specific wording and prompt_version are audit metadata, not learning identity.
    keys = ("provider", "model_revision", "host", "adapter", "effort", "prompt_contract", "tool_policy")
    return "cfg_" + digest({k: candidate[k] for k in keys})[:24]


def validate_packet(packet):
    fields(packet, {"schema", "task_id", "task", "context", "candidates"}, {"synthetic", "group_id", "user_choice_id"})
    require(packet["schema"] == "ultra-pilot-task-v1", "invalid-task-schema")
    label(packet["task_id"])
    label(packet.get("group_id", packet["task_id"]))
    require(type(packet.get("synthetic", False)) is bool, "invalid-synthetic-flag")
    if packet.get("user_choice_id") is not None:
        label(packet["user_choice_id"])
    t = packet["task"]
    fields(t, {"scope_id", "summary", "requirements", "acceptance_gates", "worker_boundary", "intended_use", "risk", "work_kind", "operation", "complexity", "required_tools", "required_modalities", "input_tokens", "output_tokens"})
    for key in ("scope_id", "operation"):
        label(t[key])
    for key in ("summary", "worker_boundary", "intended_use"):
        prose(t[key])
    require(t["risk"] in {"low", "medium", "high"} and t["work_kind"] in KINDS, "invalid-task-kind")
    require(t["complexity"] in {"routine", "complex"}, "invalid-complexity")
    require(isinstance(t["requirements"], list) and 0 < len(t["requirements"]) <= 24, "invalid-requirements")
    for item in t["requirements"]:
        prose(item)
    labels(t["acceptance_gates"])
    require(bool(t["acceptance_gates"]), "acceptance-gate-required")
    for key in ("required_tools", "required_modalities"):
        labels(t[key])
    for key in ("input_tokens", "output_tokens"):
        integer(t[key], 1)
    ctx = packet["context"]
    fields(ctx, {"host", "provider", "observed_at", "delegation_allowed"})
    label(ctx["host"]); label(ctx["provider"]); timestamp(ctx["observed_at"])
    require(type(ctx["delegation_allowed"]) is bool, "invalid-context-guard")
    require(isinstance(packet["candidates"], list) and 0 < len(packet["candidates"]) <= 128, "invalid-candidates")
    seen, configs = set(), set()
    for c in packet["candidates"]:
        fields(c, {"id", "provider", "model", "model_revision", "host", "adapter", "effort", "prompt_contract", "tool_policy", "capability_description", "scope_envelope", "available", "tools", "modalities", "context_window", "max_output_tokens", "execution_location", "estimate_usd"}, {"prompt_version", "roles"})
        for key in ("id", "provider", "model", "model_revision", "host", "adapter", "effort", "prompt_contract", "tool_policy"):
            label(c[key])
        if "prompt_version" in c:
            label(c["prompt_version"])
        for key in ("capability_description", "scope_envelope"):
            prose(c[key])
        for key in ("tools", "modalities"):
            labels(c[key])
        labels(c.get("roles", []))
        require(type(c["available"]) is bool, "invalid-availability")
        for key in ("context_window", "max_output_tokens"):
            if c[key] is not None:
                integer(c[key], 1)
        require(c["execution_location"] in {"remote", "local", "unknown"}, "invalid-location")
        amount(c["estimate_usd"])
        cid = configuration_id(c)
        require(c["id"] not in seen and cid not in configs, "duplicate-candidate")
        seen.add(c["id"]); configs.add(cid)
    return packet


def wilson_lower(passed, n):
    if not n:
        return 0.0
    z = 1.959963984540054
    phat = passed / n
    return max(0.0, (phat + z*z/(2*n) - z*math.sqrt(phat*(1-phat)/n + z*z/(4*n*n))) / (1 + z*z/n))


def evidence_for(candidate, packet, outcomes, p, clock):
    cid, t = configuration_id(candidate), packet["task"]
    groups = {}
    costs = []
    for o in outcomes:
        if (o["configuration_id"] != cid or o["scope_id"] != t["scope_id"]
                or o.get("operation") != t["operation"] or o.get("risk") != t["risk"]
                or o.get("work_kind") != t["work_kind"]
                or o.get("complexity") != t["complexity"]
                or o["group_id"] == packet.get("group_id", packet["task_id"])
                or o["synthetic"] != packet.get("synthetic", False)):
            continue
        age = (clock - timestamp(o["created_at"])).total_seconds()
        if not 0 <= age <= p["evidence_days"] * 86400:
            continue
        mandatory = {g["id"] for g in o["gates"] if g["mandatory"]}
        if not set(t["acceptance_gates"]) <= mandatory:
            continue  # Changed acceptance contract requires new applicable evidence.
        accepted = (o["accepted"] and min(o["scores"].values()) >= p["dimension_floor"]
                    and sum(o["scores"].values())/len(DIMENSIONS) >= p["quality_floor"])
        groups.setdefault(o["group_id"], []).append(accepted)
        components = [o["costs"][k]["usd"] for k in ("worker", "review", "retry", "fallback")]
        if all(v is not None for v in components):
            costs.append(sum(components))
    passed = sum(all(values) for values in groups.values())
    lower = wilson_lower(passed, len(groups))
    return {"groups": len(groups), "passed_groups": passed, "failed_groups": len(groups)-passed,
            "lower_bound": lower, "qualified": passed > 0 and len(groups) >= p["minimum_groups"] and lower >= p["minimum_success_lower_bound"],
            "observed_mean_cost_usd": sum(costs)/len(costs) if costs else None,
            "cost_observations": len(costs)}


def prepare(packet, p, outcomes=(), clock=None):
    validate_packet(packet)
    p = policy(p)
    clock = clock or dt.datetime.now(dt.timezone.utc)
    t, ctx = packet["task"], packet["context"]
    age = (clock-timestamp(ctx["observed_at"])).total_seconds()
    rows = []
    for c in packet["candidates"]:
        reasons = []
        if not c["available"]: reasons.append("unavailable")
        if c["host"] != ctx["host"] or c["provider"] != ctx["provider"]: reasons.append("outside-host-provider")
        if c["adapter"] not in {"codex-native", "claude-code-native", "opencode-native"}: reasons.append("unsupported-adapter")
        expected_host = {"codex-native": "codex", "claude-code-native": "claude-code", "opencode-native": "opencode"}.get(c["adapter"])
        if expected_host != c["host"]: reasons.append("adapter-host-mismatch")
        if c["execution_location"] != "remote": reasons.append("unsupported-location")
        if c["model"] in p["excluded_models"]: reasons.append("excluded-model")
        if configuration_id(c) in p["quarantined_configurations"]: reasons.append("quarantined-configuration")
        if not set(t["required_tools"]) <= set(c["tools"]): reasons.append("missing-tools")
        if not set(t["required_modalities"]) <= set(c["modalities"]): reasons.append("missing-modalities")
        if c["context_window"] is None or c["max_output_tokens"] is None: reasons.append("unknown-capacity")
        elif t["input_tokens"]+t["output_tokens"] > c["context_window"] or t["output_tokens"] > c["max_output_tokens"]: reasons.append("context-does-not-fit")
        if not 0 <= age <= p["capability_age_seconds"]: reasons.append("stale-capabilities")
        if not ctx["delegation_allowed"]: reasons.append("context-stop")
        if t["risk"] not in p["allowed_risks"]: reasons.append("risk-outside-policy")
        ev = evidence_for(c, packet, outcomes, p, clock)
        estimate = ev["observed_mean_cost_usd"] if ev["observed_mean_cost_usd"] is not None else c["estimate_usd"]
        rows.append({"id": c["id"], "configuration_id": configuration_id(c), "model": c["model"], "effort": c["effort"],
                     "eligible": not reasons, "reasons": reasons, "shortlisted": False,
                     "estimate_usd": estimate, "evidence": ev})
    by_id = {c["id"]: c for c in packet["candidates"]}
    eligible = [r for r in rows if r["eligible"]]
    def cost_key(r):
        return (r["estimate_usd"] is None, r["estimate_usd"] or 0, -r["evidence"]["lower_bound"], r["configuration_id"])
    ranked = sorted(eligible, key=cost_key)
    baseline = next((r for r in eligible if r["id"] == p["baseline_id"]), None)
    if baseline is None:
        baseline = next((r for r in ranked if r["evidence"]["qualified"]), None)
    override_id = packet.get("user_choice_id") or p["pin_id"]
    override = next((r for r in eligible if r["id"] == override_id), None)
    chosen = []
    def add(row):
        if row is not None and row not in chosen and len(chosen) < p["shortlist_limit"]:
            chosen.append(row)
    add(override); add(baseline)
    for role in ("economical", "specialist", "fallback", "challenger"):
        add(next((r for r in ranked if role in by_id[r["id"]].get("roles", [])), None))
    for row in ranked:
        add(row)
    cards = []
    for row in chosen:
        row["shortlisted"] = True
        c = by_id[row["id"]]
        cohorts = []
        if row["evidence"]["groups"]:
            cohorts.append({"task_description": f"Independently reviewed {t['operation']} tasks in scope {t['scope_id']}; task kind {t['work_kind']}, risk {t['risk']}. Both accepted and failed groups are retained."})
        cards.append({"id": row["configuration_id"], "capability_description": c["capability_description"], "scope_envelope": c["scope_envelope"], "evidence_cohorts": cohorts})
    return {"rows": rows, "shortlist": chosen, "cards": cards, "baseline": baseline,
            "override": override, "override_missing": override_id is not None and override is None}


def recommendation(packet, prepared, answers, p):
    t, th = packet["task"], p["thresholds"]
    def result(action, reason, row=None, nominees=()):
        return {"action": action, "configuration_id": row["configuration_id"] if row else None,
                "reason_codes": [reason], "nominees": list(nominees)}
    if answers["missing_requirement"]["noul"] > th["missing_requirement"]:
        return result("clarify", "missing-or-uncertain-requirement")
    if answers["coordinator_coupling"]["noul"] > th["coordinator_coupling"]:
        return result("repackage", "coordinator-dependency")
    impact = answers["failure_impact"]["probabilities"]
    if float(impact["3"]) > th["severe_impact"] and t["risk"] != "high":
        return result("coordinator", "impact-metadata-conflict")
    if sum(float(impact[k]) for k in ("2", "3")) > th["demand"] and t["risk"] == "low":
        return result("coordinator", "impact-metadata-conflict")
    # These semantic demands cannot manufacture missing discovered tools or scope evidence.
    kind = answers["work_kind"]["choice"]
    if answers["work_kind"]["confidence"] >= th["demand"] and kind not in {t["work_kind"], "mixed", "other"} and t["work_kind"] not in {"mixed", "other"}:
        return result("repackage", "task-kind-conflict")
    extended = (sum(float(answers["reasoning_depth"]["probabilities"][k]) for k in ("2", "3")) >= th["demand"]
                or answers["context_synthesis"]["noul"] >= th["demand"]
                or (t["work_kind"] in {"coding", "mixed"} and answers["code_interaction"]["noul"] >= th["demand"]))
    # Pilot evidence is scoped by explicit contract. Complex work needs a scope marked for it.
    if extended and t["complexity"] != "complex":
        return result("repackage", "complex-scope-required")
    by_cfg = {configuration_id(c): c for c in packet["candidates"]}
    qualified, nominees = [], []
    for i, row in enumerate(prepared["shortlist"]):
        c = by_cfg[row["configuration_id"]]
        if answers["external_information"]["noul"] >= th["demand"] and "external-retrieval" not in c["tools"]:
            continue
        if answers[f"operation_match_{i}"]["noul"] < th["operation_match"] or answers[f"scope_exceeded_{i}"]["noul"] > th["scope_exceeded"]:
            continue
        comparable = all(answers[f"evidence_comparable_{i}_{j}"]["noul"] >= th["evidence_comparable"] for j in range(len(prepared["cards"][i]["evidence_cohorts"])))
        if row["evidence"]["qualified"] and comparable:
            qualified.append(row)
        else:
            nominees.append(row["configuration_id"])
    if qualified:
        chosen = min(qualified, key=lambda r: (r["estimate_usd"] is None, r["estimate_usd"] or 0, -r["evidence"]["lower_bound"], r["configuration_id"]))
        return result("route", "scoped-evidence-and-semantic-match", chosen)
    if nominees:
        return result("experiment", "reviewed-trial-required", nominees=nominees)
    return result("coordinator", "no-suitable-candidate")


def validate_cost(value):
    fields(value, {"usd", "kind"})
    amount(value["usd"])
    require(value["kind"] in {"measured", "estimated", "unknown"}, "invalid-cost-kind")
    require((value["usd"] is None) == (value["kind"] == "unknown"), "inconsistent-cost")
    return value


def assess_outcome(raw, decision, p):
    fields(raw, {"decision_id", "configuration_id", "artifact_hash", "reviewer_id", "reviewer_kind", "review_accepted", "gates", "scores", "costs", "latency_ms"}, {"prompt_version"})
    require(raw["decision_id"] == decision["id"], "decision-mismatch")
    require(raw["configuration_id"] in {c["configuration_id"] for c in decision["candidates"] if c["eligible"]}, "unknown-outcome-candidate")
    require(isinstance(raw["artifact_hash"], str) and re.fullmatch(r"[a-f0-9]{64}", raw["artifact_hash"]), "invalid-artifact-hash")
    label(raw["reviewer_id"])
    require(raw["reviewer_kind"] in {"human", "frontier", "synthetic"}, "invalid-reviewer")
    require(type(raw["review_accepted"]) is bool, "invalid-review-verdict")
    fields(raw["scores"], set(DIMENSIONS))
    require(all(transport.number(v, 0, 100) for v in raw["scores"].values()), "invalid-quality-score")
    gates = raw["gates"]
    require(isinstance(gates, list) and 0 < len(gates) <= 64, "invalid-gates")
    seen = set()
    for g in gates:
        fields(g, {"id", "mandatory", "passed"}); label(g["id"])
        require(type(g["mandatory"]) is bool and type(g["passed"]) is bool, "invalid-gate")
        require(g["id"] not in seen, "duplicate-gate"); seen.add(g["id"])
    require(any(g["mandatory"] for g in gates), "mandatory-gate-required")
    require(set(decision["acceptance_gates"]) <= {g["id"] for g in gates if g["mandatory"]}, "missing-required-gates")
    fields(raw["costs"], set(COST_COMPONENTS))
    for c in raw["costs"].values(): validate_cost(c)
    amount(raw["latency_ms"])
    if "prompt_version" in raw: label(raw["prompt_version"])
    accepted = (raw["review_accepted"] and all(g["passed"] for g in gates if g["mandatory"])
                and min(raw["scores"].values()) >= p["dimension_floor"]
                and sum(raw["scores"].values()) / len(DIMENSIONS) >= p["quality_floor"])
    o = {**copy.deepcopy(raw), "schema": "ultra-pilot-outcome-v1", "created_at": now(), "accepted": accepted,
         "task_id": decision["task_id"], "group_id": decision["group_id"], "scope_id": decision["scope_id"],
         "operation": decision["operation"], "risk": decision["risk"], "work_kind": decision["work_kind"],
         "complexity": decision["complexity"],
         "synthetic": decision["synthetic"] or raw["reviewer_kind"] == "synthetic", "policy_hash": digest(p)}
    o["id"] = "out_" + digest({"decision": decision["id"], "configuration": raw["configuration_id"]})[:24]
    return o
