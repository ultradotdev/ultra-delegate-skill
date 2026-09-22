"""Pure contracts, evidence, and routing for the experimental v2 project pilot."""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import itertools
import json
import math
import re
from urllib.parse import urlsplit

import jev_transport as transport
from pilot_questions import ROUTING_THRESHOLDS, DEMAND_BANDS

SCHEMA = "ultra-pilot-policy-v2"
DEFAULTS = {
    "schema": SCHEMA, "mode": "off", "share_summaries": False,
    "share_artifacts": False, "security_check": False,
    "allow_host_managed_output": False,
    "model": "jev-1.13.0", "credential_service": transport.SERVICE,
    "credential_ref": "default", "baseline_id": None, "pin_id": None,
    "excluded_models": [], "quarantined_configurations": [], "shortlist_limit": 8, "allowed_risks": ["low"],
    "workflow": {}, "bakeoff": "auto", "selection_preference": "efficiency_hints",
    "evidence_days": 90, "capability_age_seconds": 300,
    "quality_floor": 80, "dimension_floor": 70,
    "thresholds": copy.deepcopy(ROUTING_THRESHOLDS),
    "demand_bands": copy.deepcopy(DEMAND_BANDS),
}
DECISION_POLICY_VERSION = "pilot-selection-v6"
DEMAND_GATES = {"reasoning": "review-reasoning", "code_interaction": "review-code-interaction",
                "context_synthesis": "review-context-synthesis"}

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
    require(p["schema"] == SCHEMA and p["mode"] in {"off", "active"}, "invalid-policy")
    require(isinstance(p["selection_preference"], str) and p["selection_preference"] in {"efficiency_hints", "strongest_fit"}, "invalid-selection-preference")
    require(isinstance(p["bakeoff"], str) and p["bakeoff"] in {"auto", "on", "off"}, "invalid-bakeoff")
    for key in ("share_summaries", "share_artifacts", "security_check", "allow_host_managed_output"):
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
    for key in ("evidence_days", "capability_age_seconds", "shortlist_limit"):
        integer(p[key], 1)
    require(p["shortlist_limit"] <= 12, "shortlist-too-large")
    for key in ("quality_floor", "dimension_floor"):
        require(transport.number(p[key], 0, 100), "invalid-quality-floor")
    fields(p["workflow"], set(), {"max_attempts", "max_concurrency", "max_elapsed_seconds"})
    for limit in p["workflow"].values():
        if limit is not None: integer(limit, 1)
    require(set(p["thresholds"]) == set(DEFAULTS["thresholds"]), "invalid-thresholds")
    require(all(transport.number(v) for v in p["thresholds"].values()), "invalid-thresholds")
    bands = value.get("demand_bands", {})
    require(isinstance(bands, dict) and set(bands) <= set(DEMAND_GATES), "invalid-demand-band")
    p["demand_bands"] = copy.deepcopy(DEMAND_BANDS)
    for tag, band in bands.items():
        fields(band, {"absent", "required"})
        require(all(transport.number(v) for v in band.values()) and band["absent"] < band["required"], "invalid-demand-band")
        p["demand_bands"][tag] = copy.deepcopy(band)
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
        fields(c, {"id", "provider", "model", "model_revision", "host", "adapter", "effort", "prompt_contract", "tool_policy", "capability_description", "scope_envelope", "available", "tools", "modalities", "context_window", "max_output_tokens", "execution_location", "estimate_usd"}, {"prompt_version", "roles", "output_limit_source", "efficiency_hint"})
        require(c.get("output_limit_source", "explicit") in {"explicit", "native-host"}, "invalid-capacity-source")
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
        validate_efficiency_hint(c.get("efficiency_hint"))
        cid = configuration_id(c)
        require(c["id"] not in seen and cid not in configs, "duplicate-candidate")
        seen.add(c["id"]); configs.add(cid)
    return packet


def validate_efficiency_hint(hint):
    """Relative research metadata never doubles as a monetary estimate."""
    if hint is None:
        return
    fields(hint, {"rank", "basis", "source_url", "checked_on"})
    integer(hint["rank"]); label(hint["basis"])
    try:
        source = urlsplit(hint["source_url"])
        require(source.scheme == "https" and bool(source.hostname) and not source.username
                and not source.password and not source.query and not source.fragment
                and isinstance(hint["source_url"], str) and len(hint["source_url"]) <= 2048
                and hint["source_url"].isprintable()
                and not any(ch.isspace() for ch in hint["source_url"]), "invalid-efficiency-source")
        # Require the portable ISO date shape, not Python's additional accepted forms.
        require(isinstance(hint["checked_on"], str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", hint["checked_on"]), "invalid-efficiency-date")
        dt.date.fromisoformat(hint["checked_on"])
    except (ValueError, TypeError, AttributeError):
        raise PilotError("invalid-efficiency-hint") from None


def efficiency_metadata(hint, clock):
    if hint is None:
        return None
    age = (clock.date() - dt.date.fromisoformat(hint["checked_on"])).days
    return {"rank": hint["rank"], "basis": hint["basis"], "checked_on": hint["checked_on"],
            "status": "current" if 0 <= age <= 180 else "future" if age < 0 else "stale"}


def wilson_lower(passed, n):
    if not n:
        return 0.0
    z = 1.959963984540054
    phat = passed / n
    return max(0.0, (phat + z*z/(2*n) - z*math.sqrt(phat*(1-phat)/n + z*z/(4*n*n))) / (1 + z*z/n))


def demand_key(demands):
    return "+".join(sorted(demands))


def demand_profile(task, answers, p):
    """Describe task demands without rewriting its authoritative kind or complexity."""
    values = {"reasoning": sum(float(answers["reasoning_depth"]["probabilities"][k]) for k in ("2", "3")),
              "code_interaction": answers["code_interaction"]["noul"],
              "context_synthesis": answers["context_synthesis"]["noul"]}
    profile = {}
    for tag, value in values.items():
        if tag == "code_interaction" and task["work_kind"] not in {"coding", "mixed"}:
            profile[tag] = "not-applicable"
        else:
            profile[tag] = ("required" if value >= p["demand_bands"][tag]["required"] else
                            "absent" if value <= p["demand_bands"][tag]["absent"] else "uncertain")
    return profile


def task_family(task):
    """Broad retrieval index, never a statistical admission gate."""
    operation = task["operation"].lower()
    if "review" in operation or "audit" in operation:
        return "review"
    if "test" in operation:
        return "tests"
    return "implementation" if task.get("work_kind") in {"coding", "mixed"} else task.get("work_kind", "other")


def matching_outcomes(candidate, packet, outcomes, p, clock):
    """Reuse broad relevant history; keep exact configuration provenance."""
    cid, task = configuration_id(candidate), packet["task"]
    for o in outcomes:
        if o.get("provenance") == "imported-unverified":
            continue
        if (o["configuration_id"] != cid or task_family(o) != task_family(task)
                or o["group_id"] == packet.get("group_id", packet["task_id"])
                or o["synthetic"] != packet.get("synthetic", False)):
            continue
        age = (clock - timestamp(o["created_at"])).total_seconds()
        if 0 <= age <= p["evidence_days"] * 86400:
            yield o


def historical_cohort(records, evidence):
    if not records:
        return []
    # These are retained outcome metadata, not a restatement of the new task.
    origin = records[0]
    domains = sorted({o["scope_id"] for o in records})
    coverage = {tag: len({o["group_id"] for o in records if tag in o.get("reviewed_demands", [])})
                for tag in DEMAND_GATES}
    description = (f"Broad {task_family(origin)} history across {len(domains)} scopes; first example scope {origin['scope_id']}; operation {origin['operation']}; "
                   f"kind {origin['work_kind']}; risk {origin['risk']}; complexity {origin['complexity']}. Other scopes: {', '.join(domains[:4])}. "
                   f"Independent groups {evidence['groups']}; passing {evidence['passed_groups']}; "
                   f"failed {evidence['failed_groups']}. Reviewer-confirmed demand coverage counts: "
                   + ", ".join(f"{tag}={n}" for tag, n in coverage.items())
                   + ". Missing coverage earns no positive demand credit; failures are retained.")
    if any(o.get("provenance") == "imported-unverified" for o in records):
        description += " Contains imported unverified observations; local independent review is still required."
    return [{"task_description": description}]


def evidence_for(candidate, packet, outcomes, p, clock, required_demands=()):
    return summarize_evidence(list(matching_outcomes(candidate, packet, outcomes, p, clock)), p, required_demands)


def summarize_evidence(records, p, required_demands=()):
    groups = {}
    costs = {}
    retained = []
    for o in records:
        accepted = (o["accepted"] and all(g["passed"] for g in o["gates"] if g["mandatory"])
                    and min(o["scores"].values()) >= p["dimension_floor"]
                    and sum(o["scores"].values())/len(DIMENSIONS) >= p["quality_floor"])
        # Demand inference is not evidence that a worker exercised that capability.
        # Only independently confirmed coverage with mandatory review gates earns
        # positive credit. Keep matching failures conservatively, even untagged.
        if accepted and required_demands:
            reviewed = o.get("reviewed_demands", [])
            passed_gates = {g["id"] for g in o["gates"] if g["mandatory"] and g["passed"]}
            if not (set(required_demands) <= set(reviewed)
                    and {DEMAND_GATES[x] for x in required_demands} <= passed_gates):
                continue
        retained.append(o)
        groups.setdefault(o["group_id"], []).append(accepted)
        components = [o["costs"][k]["usd"] for k in ("worker", "review", "retry", "fallback")]
        costs.setdefault(o["group_id"], []).append(sum(components) if all(v is not None for v in components) else None)
    complete_costs = [sum(v) for v in costs.values() if all(x is not None for x in v)]
    passed = sum(all(values) for values in groups.values())
    lower = wilson_lower(passed, len(groups))
    return {"groups": len(groups), "passed_groups": passed, "failed_groups": len(groups)-passed,
            "lower_bound": lower, "support": "observed" if groups else "unobserved",
            "recent_failure": bool(retained) and not all(groups[max(retained, key=lambda o: o["created_at"])["group_id"]]),
            "observed_mean_cost_usd": sum(complete_costs)/len(complete_costs) if complete_costs else None,
            "cost_observations": len(complete_costs)}


def prepare(packet, p, outcomes=(), clock=None):
    validate_packet(packet)
    p = policy(p)
    clock = clock or dt.datetime.now(dt.timezone.utc)
    t, ctx = packet["task"], packet["context"]
    age = (clock-timestamp(ctx["observed_at"])).total_seconds()
    rows, compatible_records = [], {}
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
        host_output = (p["allow_host_managed_output"] and c.get("output_limit_source") == "native-host"
                       and c["host"] == "codex" and c["provider"] == "openai" and c["adapter"] == "codex-native"
                       and c["execution_location"] == "remote")
        if c["context_window"] is None or (c["max_output_tokens"] is None and not host_output):
            reasons.append("unknown-capacity")
        if c["context_window"] is not None and t["input_tokens"]+t["output_tokens"] > c["context_window"]:
            reasons.append("context-does-not-fit")
        if c["max_output_tokens"] is not None and t["output_tokens"] > c["max_output_tokens"]:
            reasons.append("context-does-not-fit")
        if host_output and c["max_output_tokens"] is None and "complete-output" not in t["acceptance_gates"]:
            reasons.append("missing-completeness-gate")
        if not 0 <= age <= p["capability_age_seconds"]: reasons.append("stale-capabilities")
        if not ctx["delegation_allowed"]: reasons.append("context-stop")
        if t["risk"] not in p["allowed_risks"]: reasons.append("risk-outside-policy")
        records = list(matching_outcomes(c, packet, outcomes, p, clock))
        compatible_records[configuration_id(c)] = records
        ev = summarize_evidence(records, p)
        estimate = ev["observed_mean_cost_usd"] if ev["observed_mean_cost_usd"] is not None else c["estimate_usd"]
        demand_evidence = {demand_key(tags): summarize_evidence(records, p, tags)
                           for count in range(1, len(DEMAND_GATES)+1)
                           for tags in itertools.combinations(DEMAND_GATES, count)}
        rows.append({"id": c["id"], "configuration_id": configuration_id(c), "model": c["model"], "effort": c["effort"],
                     "eligible": not reasons, "reasons": reasons, "shortlisted": False,
                     "output_limit_source": "native-host" if host_output and c["max_output_tokens"] is None else "explicit",
                     "max_output_tokens": c["max_output_tokens"], "context_window": c["context_window"],
                     "input_budget_tokens": t["input_tokens"], "output_budget_tokens": t["output_tokens"],
                     "estimate_usd": estimate, "efficiency_hint": efficiency_metadata(c.get("efficiency_hint"), clock),
                     "evidence": ev, "demand_evidence": demand_evidence})
    by_id = {c["id"]: c for c in packet["candidates"]}
    eligible = [r for r in rows if r["eligible"]]
    def cost_key(r):
        return (r["estimate_usd"] is None, r["estimate_usd"] or 0, -r["evidence"]["lower_bound"], r["configuration_id"])
    ranked = sorted(eligible, key=cost_key)
    baseline = next((r for r in eligible if r["id"] == p["baseline_id"]), None)
    if baseline is None:
        baseline = next(iter(ranked), None)
    override_id = packet.get("user_choice_id") or p["pin_id"]
    override = next((r for r in eligible if r["id"] == override_id), None)
    chosen = []
    def add(row):
        if row is not None and row not in chosen and len(chosen) < p["shortlist_limit"]:
            chosen.append(row)
    add(override); add(baseline)
    for role in ("economical", "specialist", "fallback", "challenger"):
        pool = [r for r in ranked if role in by_id[r["id"]].get("roles", [])]
        if role == "challenger" and pool:
            # Stable per-task rotation avoids a permanent pair without hidden RNG.
            pool.sort(key=lambda r: digest([packet["task_id"], r["configuration_id"]]))
        add(next(iter(pool), None))
    for row in ranked:
        add(row)
    cards = []
    for row in chosen:
        row["shortlisted"] = True
        c = by_id[row["id"]]
        records = compatible_records[row["configuration_id"]]
        cohorts = historical_cohort(records, row["evidence"])
        cards.append({"id": row["configuration_id"], "capability_description": c["capability_description"], "scope_envelope": c["scope_envelope"], "evidence_cohorts": cohorts})
    return {"rows": rows, "shortlist": chosen, "cards": cards, "baseline": baseline,
            "override": override, "override_missing": override_id is not None and override is None}


def recommendation(packet, prepared, answers, p):
    t, th = packet["task"], p["thresholds"]
    profile = demand_profile(t, answers, p)
    demands = sorted(k for k, v in profile.items() if v in {"required", "uncertain"})
    fit_demands = sorted(k for k, v in profile.items() if v == "required")
    assessments = []
    kind = answers["work_kind"]
    diagnostics = (["work-kind-disagreement"] if kind["confidence"] >= th["demand"]
                   and kind["choice"] not in {t["work_kind"], "mixed", "other"}
                   and t["work_kind"] not in {"mixed", "other"} else [])
    def result(action, reason, row=None, nominees=()):
        return {"action": action, "configuration_id": row["configuration_id"] if row else None,
                "reason_codes": [reason], "nominees": list(nominees), "alternatives": [],
                "demand_profile": profile, "required_demands": demands,
                "review_requirements": [DEMAND_GATES[k] for k in demands],
                "candidate_assessments": assessments, "diagnostics": diagnostics,
                "selection_basis": {"preference": p["selection_preference"], "method": "not-selected", "tie_breakers": []}}
    if answers["missing_requirement"]["noul"] > th["missing_requirement"]:
        return result("clarify", "missing-or-uncertain-requirement")
    if answers["coordinator_coupling"]["noul"] > th["coordinator_coupling"]:
        return result("repackage", "coordinator-dependency")
    impact = answers["failure_impact"]["probabilities"]
    if float(impact["3"]) > th["severe_impact"] and t["risk"] != "high":
        return result("coordinator", "impact-metadata-conflict")
    if sum(float(impact[k]) for k in ("2", "3")) > th["demand"] and t["risk"] == "low":
        return result("coordinator", "impact-metadata-conflict")
    # Work-kind classification is diagnostic. Reasoning, interaction and synthesis
    # choose applicable evidence and review, never a blanket complexity stop.
    by_cfg = {configuration_id(c): c for c in packet["candidates"]}
    suitable = []
    for i, row in enumerate(prepared["shortlist"]):
        c = by_cfg[row["configuration_id"]]
        evidence = (row.get("demand_evidence", {}).get(demand_key(demands)) if demands else row["evidence"])
        if evidence is None:
            evidence = {"groups": 0, "passed_groups": 0, "failed_groups": 0, "lower_bound": 0.0,
                        "support": "unobserved", "observed_mean_cost_usd": None, "cost_observations": 0}
        fits = {tag: answers[f"{tag}_fit_{i}"]["noul"] for tag in DEMAND_GATES}
        fit = min([answers[f"operation_match_{i}"]["noul"]] + [fits[tag] for tag in fit_demands])
        assessment = {"configuration_id": row["configuration_id"], "status": "excluded",
                      "reason_codes": [], "evidence": evidence, "fit_probabilities": fits,
                      "applicable_fits": fit_demands, "assessed_fit": fit}
        assessments.append(assessment)
        if answers["external_information"]["noul"] >= th["demand"] and "external-retrieval" not in c["tools"]:
            assessment["reason_codes"] = ["missing-retrieval-tool"]
            continue
        if answers[f"operation_match_{i}"]["noul"] < th["operation_match"]:
            assessment["reason_codes"] = ["operation-match-insufficient"]
            continue
        if answers[f"scope_exceeded_{i}"]["noul"] > th["scope_exceeded"]:
            assessment["reason_codes"] = ["candidate-scope-exceeded-or-uncertain"]
            continue
        # Uncertain task demand is a review obligation, not evidence that the
        # worker needs a capability. Gate expected fit for required dimensions.
        inadequate = [tag for tag in fit_demands if fits[tag] < th[tag + "_fit"]]
        if inadequate:
            assessment["reason_codes"] = [tag.replace("_", "-") + "-fit-insufficient" for tag in inadequate]
            continue
        comparable = all(answers[f"evidence_comparable_{i}_{j}"]["noul"] >= th["evidence_comparable"] for j in range(len(prepared["cards"][i]["evidence_cohorts"])))
        assessment.update(status="suitable", reason_codes=["semantic-match-with-history" if evidence.get("groups", 0) and comparable else "semantic-match-without-history"])
        # History informs selection, never authorizes it or blocks a cold start.
        used = evidence if comparable else {"groups": 0, "lower_bound": 0, "recent_failure": False}
        assessment["evidence"] = used
        cost = used.get("observed_mean_cost_usd")
        suitable.append({**row, "evidence": used, "assessed_fit": fit, "estimate_usd": cost if cost is not None else c["estimate_usd"]})
    if suitable:
        comparable_costs = all(r["estimate_usd"] is not None for r in suitable)
        hints = [r.get("efficiency_hint") for r in suitable]
        comparable_hints = (all(h and h["status"] == "current" for h in hints)
                            and len({h["basis"] for h in hints if h}) == 1)
        method = "reviewed-outcomes-and-fit"
        tie_breakers = ["recent-comparable-failure"]
        if p["selection_preference"] == "efficiency_hints":
            if comparable_costs:
                method = "comparable-cost-estimates"
                tie_breakers.append("estimate-usd")
            elif comparable_hints:
                method = "dated-efficiency-hints"
                tie_breakers.append("efficiency-rank")
        tie_breakers += ["reviewed-outcome-lower-bound", "assessed-fit", "configuration-id"]
        def preference(r):
            history = r["evidence"]
            economy = (r["estimate_usd"] if method == "comparable-cost-estimates" else
                       r["efficiency_hint"]["rank"] if method == "dated-efficiency-hints" else 0)
            return (history.get("recent_failure", False), economy,
                    -history.get("lower_bound", 0), -r["assessed_fit"], r["configuration_id"])
        ranked = sorted(suitable, key=preference)
        answer = result("route", "jev-semantic-selection", ranked[0])
        answer["alternatives"] = [r["configuration_id"] for r in ranked[1:]]
        answer["selection_basis"] = {"preference": p["selection_preference"], "method": method,
                                     "tie_breakers": tie_breakers}
        return answer
    if assessments and all(a["reason_codes"] == ["missing-retrieval-tool"] for a in assessments):
        return result("repackage", "external-information-unavailable")
    return result("coordinator", "no-suitable-candidate")


def validate_cost(value):
    fields(value, {"usd", "kind"})
    amount(value["usd"])
    require(value["kind"] in {"measured", "estimated", "unknown"}, "invalid-cost-kind")
    require((value["usd"] is None) == (value["kind"] == "unknown"), "inconsistent-cost")
    return value


def observation_role(decision, configuration_id_value):
    selected = decision.get("action") == "route" and configuration_id_value == decision.get("selected_configuration_id")
    nominated = decision.get("action") == "experiment" and configuration_id_value in decision.get("nominated_configuration_ids", [])
    alternative = configuration_id_value in decision.get("alternative_configuration_ids", [])
    if decision.get("mode") == "active":
        require(selected or nominated or alternative, "outcome-outside-decision")
    return "selected-route" if selected else "nominated-trial" if nominated else "coordinator-reviewed-comparison"


def assess_outcome(raw, decision, p):
    fields(raw, {"decision_id", "configuration_id", "artifact_hash", "reviewer_id", "reviewer_kind", "review_accepted", "gates", "scores", "costs", "latency_ms"}, {"prompt_version", "reviewed_demands", "request_id", "attempt_id", "attempt_kind", "critical_defects", "worker_id"})
    require(raw["decision_id"] == decision["id"], "decision-mismatch")
    require(raw["configuration_id"] in {c["configuration_id"] for c in decision["candidates"] if c["eligible"]}, "unknown-outcome-candidate")
    role = observation_role(decision, raw["configuration_id"])
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
    reviewed_demands = raw.get("reviewed_demands", [])
    labels(reviewed_demands)
    require(set(reviewed_demands) <= set(DEMAND_GATES), "invalid-reviewed-demands")
    require({DEMAND_GATES[k] for k in reviewed_demands} <= {g["id"] for g in gates if g["mandatory"]},
            "missing-demand-review-gates")
    fields(raw["costs"], set(COST_COMPONENTS))
    for c in raw["costs"].values(): validate_cost(c)
    amount(raw["latency_ms"])
    if "prompt_version" in raw: label(raw["prompt_version"])
    defects = raw.get("critical_defects", [])
    labels(defects)
    attempt_fields = {"request_id", "attempt_id", "attempt_kind"}
    require(not (attempt_fields & set(raw)) or attempt_fields <= set(raw), "incomplete-attempt-link")
    for k in attempt_fields & set(raw): label(raw[k])
    if "attempt_kind" in raw:
        require(raw["attempt_kind"] in {"initial", "comparison", "repair", "fallback"}, "invalid-attempt-kind")
    if decision.get("decision_policy_version") == DECISION_POLICY_VERSION and not decision["synthetic"]:
        require(raw["reviewer_kind"] != "synthetic", "synthetic-review-for-real-task")
        require(bool(raw.get("worker_id")), "missing-worker-id")
    if "worker_id" in raw:
        label(raw["worker_id"])
        require(raw["worker_id"] != raw["reviewer_id"], "worker-cannot-review-self")
    accepted = (not defects and raw["review_accepted"] and all(g["passed"] for g in gates if g["mandatory"])
                and min(raw["scores"].values()) >= p["dimension_floor"]
                and sum(raw["scores"].values()) / len(DIMENSIONS) >= p["quality_floor"])
    o = {**copy.deepcopy(raw), "schema": "ultra-pilot-outcome-v1", "created_at": now(), "accepted": accepted,
         "task_id": decision["task_id"], "group_id": decision["group_id"], "scope_id": decision["scope_id"],
         "operation": decision["operation"], "risk": decision["risk"], "work_kind": decision["work_kind"],
         "complexity": decision["complexity"], "reviewed_demands": sorted(reviewed_demands),
         "observation_role": role, "critical_defects": defects, "task_family": task_family(decision),
         "synthetic": decision["synthetic"] or raw["reviewer_kind"] == "synthetic", "policy_hash": digest(p)}
    o["id"] = "out_" + digest({"decision": decision["id"], "configuration": raw["configuration_id"], "attempt": raw.get("attempt_id")})[:24]
    return o
