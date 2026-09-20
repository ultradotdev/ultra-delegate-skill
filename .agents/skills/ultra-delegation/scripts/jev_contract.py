"""Pure Jev policy and decision-ledger contracts. No credentials or network I/O."""
from __future__ import annotations

import math
import re
from evidence import validate_public_value

DEFAULT_JEV_POLICY = {
    "version": 1, "routing": "off", "judging": "off",
    "share_summaries": False, "share_artifacts": False,
    "credential_service": "ultra-delegation.typesafe", "credential_ref": "default", "model": "jev-1.13.0",
    "suitability_threshold": 0.90, "rubric_version": "jev-rubric-v1",
}
RUBRIC = {
    "coverage": ["No requirements covered", "Few requirements covered", "Some requirements covered", "Most requirements covered", "All requirements covered"],
    "scope": ["Entirely outside scope", "Major unrelated changes", "Several unrelated changes", "Minor unnecessary changes", "Changes stay within the requested scope"],
    "evidence": ["Claims contradicted by supplied evidence", "Major unsupported claims", "Mixed supported and unsupported claims", "Most claims supported", "All material claims supported by supplied evidence"],
    "clarity": ["Unintelligible", "Major ambiguities", "Understandable with effort", "Mostly clear", "Clear and unambiguous"],
}
PRICE = {"model": "jev-1.13.0", "input_per_million_usd": 0.042,
         "date": "2026-09-18", "source": "https://docs.typesafe.ai/models"}


def validate_policy(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_JEV_POLICY):
        raise ValueError("invalid Jev policy fields")
    p = {**DEFAULT_JEV_POLICY, **value}
    if type(p["version"]) is not int or p["version"] != 1:
        raise ValueError("unsupported Jev policy version")
    if p["routing"] not in ("off", "shadow", "active") or p["judging"] not in ("off", "shadow"):
        raise ValueError("invalid Jev mode")
    if any(type(p[k]) is not bool for k in ("share_summaries", "share_artifacts")):
        raise ValueError("Jev sharing settings must be boolean")
    for field in ("credential_service", "credential_ref"):
        value = p[field]
        if not isinstance(value, str) or not value.strip() or len(value) > 256 or not value.isprintable():
            raise ValueError("invalid Jev credential locator")
    if not isinstance(p["model"], str) or not re.fullmatch(r"jev-[0-9]+\.[0-9]+\.[0-9]+", p["model"]):
        raise ValueError("Jev model must be a pinned revision")
    n = p["suitability_threshold"]
    if isinstance(n, bool) or not isinstance(n, (float, int)) or not math.isfinite(n) or not 0.5 < n <= 1:
        raise ValueError("Jev suitability threshold must be greater than 0.5 and at most 1")
    if p["rubric_version"] != "jev-rubric-v1":
        raise ValueError("unsupported Jev rubric version")
    return p


# Projection is intentionally narrow: no task summaries, excerpts or provider bodies.
EVENT_KEYS = {
    "schema", "id", "run_id", "created_at", "kind", "mode", "status", "action",
    "selected_profile_id", "baseline_profile_id", "recommended_action", "recommended_profile_id",
    "nominated_profile_ids", "reason_codes", "input_hash", "policy_hash", "model", "rubric_version",
    "question_hash", "uncertainty", "probabilities", "shadow_scores", "usage", "latency_ms", "attempts",
    "estimated_cost_usd", "cost_kind", "price_date", "disagreement", "reference_comparison",
}


def event_record(result):
    event = {k: v for k, v in result.items() if k in EVENT_KEYS}
    validate_event(event)
    return event


def validate_event(event):
    validate_public_value(event)
    if not isinstance(event, dict) or set(event) - EVENT_KEYS or event.get("schema") != "ultra-delegation-jev-v1":
        raise ValueError("invalid Jev event")
    for key in ("id", "input_hash", "policy_hash", "question_hash"):
        if event.get(key) is not None and not re.fullmatch(r"[a-f0-9]{64}", event[key]):
            raise ValueError("invalid Jev event hash")
    for key in ("selected_profile_id", "baseline_profile_id", "recommended_profile_id"):
        if event.get(key) is not None and not re.fullmatch(r"udp_[a-f0-9]{24}", event[key]):
            raise ValueError("invalid Jev profile id")
    for pid in event.get("nominated_profile_ids", []):
        if not isinstance(pid, str) or not re.fullmatch(r"udp_[a-f0-9]{24}", pid):
            raise ValueError("invalid nominated profile id")
    for key in ("action", "recommended_action"):
        if event.get(key) not in (None, "route", "experiment", "coordinator"):
            raise ValueError("invalid Jev action")
    if event.get("kind") not in ("route", "judge") or event.get("mode") not in ("off", "shadow", "active"):
        raise ValueError("invalid Jev event mode")
    if event.get("status") not in ("ok", "skipped", "unavailable", "abstained"):
        raise ValueError("invalid Jev event status")
    # All persisted text must be machine labels, never arbitrary response prose.
    def labels(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", k): raise ValueError("invalid event label")
                labels(x)
        elif isinstance(v, list):
            for x in v: labels(x)
        elif isinstance(v, str) and not re.fullmatch(r"[A-Za-z0-9_.:+-]{1,128}", v):
            raise ValueError("invalid event text")
    labels(event)
    return event


def summarize_events(events):
    rows = [validate_event(e) for e in events]
    def group(kind):
        r = [e for e in rows if e["kind"] == kind]
        calls = [e for e in r if e.get("attempts", 0) > 0]
        prices = [e.get("estimated_cost_usd") for e in calls]
        return {"events": len(r), "api_attempts": sum(e.get("attempts", 0) for e in r),
                "latency_ms": sum(e.get("latency_ms", 0) for e in r),
                "estimated_cost_usd": sum(prices) if prices and all(p is not None for p in prices) else None,
                "cost_kind": "estimated" if prices and all(p is not None for p in prices) else "unavailable",
                "shadow_disagreements": sum(e.get("disagreement") is True for e in r),
                "unavailable": sum(e["status"] == "unavailable" for e in r)}
    return {"routing": group("route"), "judging": group("judge"),
            "savings_attribution": "unavailable", "worker_savings_exclude_jev_overhead": True}
