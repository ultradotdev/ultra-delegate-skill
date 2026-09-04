#!/usr/bin/env python3
"""Local-only evidence and reporting helper for the Ultra Delegation skill.

This program deliberately does not execute models, provider CLIs, shell commands, or
network requests.  An agent host supplies candidate results as JSON; this helper makes
the routing, persistence, scoring, reporting, and portable-learning decisions
reproducible.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_resources import evaluate_local, DEFAULT_LOCAL_POLICY
from evidence import normalize_outcome, validate_outcome, validate_public_value, sanitize_learning

SCHEMA = "ultra-delegation-learning-v1"
RELEASE = "1.2.0-beta.1"
LEVELS = {"off", "low", "medium", "high", "xhigh", "max", "custom"}
TASK_SIGNATURE_KEYS = ("task_family", "operation", "language", "language_version", "framework", "framework_major", "framework_version", "risk", "coupling", "validation", "tools")
DEFAULT_CONTEXT_GUARD = {
    "enabled": True,
    "max_observation_age_seconds": 300,
    "elevated_ratio": 0.70,
    "high_ratio": 0.82,
    "critical_ratio": 0.90,
    "minimum_compaction_reduction_ratio": 0.20,
    "repeated_compaction_limit": 2,
    "repeated_compaction_window_minutes": 10,
    "unattended_checkpoint_minutes": 60,
    "checkpoint_on_material_milestone": True,
    "critical_action": "stop_and_handoff",
}
DEFAULT_POLICY = {
    "schema": "ultra-delegation-policy-v1",
    "host_scope": "current", "provider_scope": "current",
    "external_adapters": "disabled",
    "cross_provider_requires": "phase_2_adapter_and_explicit_approval",
    "quality_floor": 80, "global_catalog": True,
    "moving_alias_retest_days": 30, "pinned_revision_retest_days": 90,
    "confirmation_after_selections": 10,
    "minimum_comparable_outcomes": 3,
    "quality_margin": 10.0,
    "cost_reduction_ratio": 0.5,
    "quality_equivalence_points": 2.0,
    "latency_equivalence_ratio": 0.1,
    "import_compatibility_floor": 0.8,
    "models": {}, "pins": [], "exclusions": [], "quarantined_imports": [], "price_table": {},
    "context_guard": DEFAULT_CONTEXT_GUARD,
    "local_execution": DEFAULT_LOCAL_POLICY,
}


class UserError(Exception):
    pass


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any, length: int = 16) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()[:length]


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise UserError(f"missing file: {path}")
    try:
        if path.stat().st_size > 8 * 1024 * 1024: raise UserError("JSON input exceeds 8 MiB")
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise UserError(f"cannot read JSON {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp, path)
    except Exception:
        try: os.unlink(temp)
        except OSError: pass
        raise


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
        os.replace(temp, path)
    except Exception:
        try: os.unlink(temp)
        except OSError: pass
        raise


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    validate_public_value(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    # O_APPEND gives a single write per record on common local filesystems.
    line = canonical(value) + "\n"
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try: os.write(fd, line.encode())
    finally: os.close(fd)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists(): return []
    output = []
    if path.stat().st_size > 8 * 1024 * 1024: raise UserError("ledger exceeds 8 MiB; archive older evidence before continuing")
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if len(line.encode()) > 65536: raise UserError(f"JSONL record {number} exceeds 64 KiB")
        if not line.strip(): continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise UserError(f"invalid JSONL at {path}:{number}: {exc}") from exc
        if not isinstance(item, dict): raise UserError(f"JSONL record {number} is not an object")
        output.append(item)
    return output


def read_records_input(path_value: str | None, fallback: Path) -> list[dict[str, Any]]:
    if not path_value:
        return [normalize_outcome(r) for r in read_jsonl(fallback)]
    path = Path(path_value).resolve()
    if path.suffix == ".jsonl":
        return [normalize_outcome(r) for r in read_jsonl(path)]
    value = read_json(path)
    records = value.get("records") if isinstance(value, dict) else value
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise UserError("records input must be a JSON list, an object with records, or JSONL")
    return [normalize_outcome(r) for r in records]


def root_from(args: argparse.Namespace) -> Path:
    return Path(args.root).resolve() if getattr(args, "root", None) else Path.cwd() / ".ultra-delegation"


def policy_path(root: Path) -> Path: return root / "policy.json"
def evidence_path(root: Path) -> Path: return root / "evidence.jsonl"
def catalog_path() -> Path:
    return Path(os.environ.get("ULTRA_DELEGATION_HOME", str(Path.home() / ".ultra-delegation"))) / "catalog.jsonl"


def load_policy(root: Path) -> dict[str, Any]:
    raw = read_json(policy_path(root), {})
    if not isinstance(raw, dict): raise UserError("policy must be a JSON object")
    policy = DEFAULT_POLICY | raw
    routing = raw.get("routing", {})
    experiments = raw.get("experiments", {})
    promotion_rules = raw.get("promotion", {})
    if isinstance(routing, dict):
        policy.update({
            "quality_floor": routing.get("quality_floor", policy["quality_floor"]),
            "host_scope": routing.get("host_scope", policy["host_scope"]),
            "provider_scope": routing.get("provider_scope", policy["provider_scope"]),
            "external_adapters": routing.get("external_adapters", policy["external_adapters"]),
            "cross_provider_requires": routing.get("cross_provider_requires", policy["cross_provider_requires"]),
            "global_catalog": routing.get("global_catalog", policy["global_catalog"]) != "disabled",
        })
    if isinstance(experiments, dict):
        policy.update(experiments)
    if isinstance(promotion_rules, dict):
        aliases = {
            "moving_alias_stale_days": "moving_alias_retest_days",
            "pinned_revision_stale_days": "pinned_revision_retest_days",
            "selection_retest_interval": "confirmation_after_selections",
        }
        for key, value in promotion_rules.items():
            policy[aliases.get(key, key)] = value
    guard = raw.get("context_guard", {})
    if guard is None: guard = {}
    if not isinstance(guard, dict): raise UserError("context_guard must be a JSON object")
    policy["context_guard"] = {**DEFAULT_CONTEXT_GUARD, **guard}
    local = raw.get("local_execution", {})
    if not isinstance(local, dict): raise UserError("local_execution must be an object")
    policy["local_execution"] = {**DEFAULT_LOCAL_POLICY, **local}
    return policy


def json_arg(value: str, label: str) -> Any:
    try: return json.loads(value)
    except json.JSONDecodeError as exc: raise UserError(f"{label} must be valid JSON: {exc}") from exc


def object_arg(value: str, label: str) -> dict[str, Any]:
    result = json_arg(value, label)
    if not isinstance(result, dict): raise UserError(f"{label} must be a JSON object")
    return result


def validate_profile(profile: dict[str, Any]) -> None:
    required = ["task_family", "provider", "model", "host", "thinking", "prompt_profile", "tool_policy"]
    missing = [key for key in required if not profile.get(key)]
    if missing: raise UserError("profile missing: " + ", ".join(missing))
    thinking = profile["thinking"]
    if not isinstance(thinking, dict) or thinking.get("normalized") not in LEVELS or "native" not in thinking:
        raise UserError("profile.thinking requires normalized level and native setting")


def profile_id(profile: dict[str, Any]) -> str:
    validate_profile(profile)
    identity = {key: profile[key] for key in ("task_family", "provider", "model", "host", "thinking", "prompt_profile", "tool_policy")}
    identity["model_revision"] = profile.get("model_revision", profile["model"])
    return "udp_" + digest(identity, 24)


def matches_rule(profile: dict[str, Any], rule: Any) -> bool:
    if isinstance(rule, str):
        return rule in {profile_id(profile), profile.get("model"), profile.get("provider")}
    if isinstance(rule, dict):
        return all(profile.get(key) == value for key, value in rule.items())
    return False


def eligible(profile: dict[str, Any], context: dict[str, Any], policy: dict[str, Any]) -> tuple[bool, str]:
    """Enforce locality before any quality or cost preferences."""
    if profile.get("provider") != context.get("provider"):
        return False, "provider outside current scope"
    if profile.get("host") != context.get("host"):
        return False, "host outside current scope"
    available_models = context.get("available_models")
    revision = profile.get("model_revision", profile.get("model"))
    if available_models is None:
        return False, "model capabilities unknown"
    if revision not in available_models:
        return False, "model unavailable"
    settings = context.get("thinking_settings", {}).get(revision)
    if settings is None:
        return False, "thinking capabilities unknown"
    if profile["thinking"]["native"] not in settings:
        return False, "thinking setting unavailable"
    if any(matches_rule(profile, rule) for rule in policy.get("exclusions", [])):
        return False, "excluded by policy"
    if profile_id(profile) in policy.get("quarantined_imports", []):
        return False, "quarantined imported profile"
    local = evaluate_local(profile, context, policy)
    if profile.get("execution_location") == "local" and local["eligible"]:
        return False, "unsupported-controls: no verified local execution adapter in this beta"
    return local["eligible"], local.get("status", "eligible")


def metric(record: dict[str, Any], key: str) -> float | None:
    value = record.get("metrics", {}).get(key, record.get(key))
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def all_gates_pass(record: dict[str, Any]) -> bool:
    gates = record.get("gates", [])
    mandatory = [g for g in gates if g.get("mandatory", True)]
    return record.get("accepted") is True and bool(mandatory) and all(g.get("passed") is True for g in mandatory)


def cost(record: dict[str, Any], policy: dict[str, Any] | None = None) -> tuple[float | None, str]:
    value = metric(record, "cost_usd")
    if value is not None: return value, record.get("cost_kind", "measured")
    if policy:
        profile = record.get("profile", {})
        revision = profile.get("model_revision", profile.get("model"))
        prices = policy.get("price_table", {}).get(revision, {})
        usage = record.get("usage", {})
        if prices.get("effective_date") and isinstance(usage, dict):
            inputs, outputs = usage.get("input_tokens"), usage.get("output_tokens")
            cached = usage.get("cached_input_tokens", usage.get("cached_tokens", 0))
            if inputs is None or outputs is None: return None, "unavailable"
            if cached > inputs: return None, "unavailable"
            components = [(inputs - cached, prices.get("input_per_million_usd")),
                          (outputs, prices.get("output_per_million_usd"))]
            if cached: components.append((cached, prices.get("cached_input_per_million_usd")))
            thinking = usage.get("thinking_tokens", 0)
            if thinking:
                included = usage.get("thinking_in_output")
                if included is None: return None, "unavailable"
                if included is False: components.append((thinking, prices.get("thinking_per_million_usd")))
            if any(rate is None for _, rate in components): return None, "unavailable"
            return sum(tokens * rate / 1_000_000 for tokens, rate in components), "estimated"
    return None, "unavailable"


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    records = [r for r in records if metric(r, "quality_score") is not None]
    scores = [metric(r, "quality_score") for r in records]
    scores = [x for x in scores if x is not None]
    costs = [cost(r)[0] for r in records]; costs = [x for x in costs if x is not None]
    latencies = [metric(r, "latency_ms") for r in records]; latencies = [x for x in latencies if x is not None]
    mean = sum(scores) / len(scores) if scores else None
    deviation = math.sqrt(sum((x - mean) ** 2 for x in scores) / (len(scores) - 1)) if len(scores) > 1 else 0.0
    return {"evidence_count": len(records), "pass_count": sum(all_gates_pass(r) for r in records),
            "mean_quality": mean, "quality_stddev": deviation,
            "conservative_quality": mean - deviation if mean is not None else None,
            "mean_cost_usd": sum(costs) / len(costs) if costs else None,
            "mean_latency_ms": sum(latencies) / len(latencies) if latencies else None}


def is_stale(record: dict[str, Any], policy: dict[str, Any], today: dt.datetime | None = None) -> bool:
    stamp = record.get("fresh_at", record.get("created_at"))
    if not stamp: return True
    try: then = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError): return True
    if then.tzinfo is None: return True
    moving_alias = record.get("moving_alias")
    if moving_alias is None:
        profile = record.get("profile", {})
        moving_alias = profile.get("model_revision", profile.get("model")) == profile.get("model")
    days = policy["moving_alias_retest_days"] if moving_alias else policy["pinned_revision_retest_days"]
    age = (today or dt.datetime.now(dt.timezone.utc)) - then
    return age.total_seconds() < -60 or age.days >= days


def promotion(records: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    records = [r for r in records if r.get("failure_kind") != "resource"]
    stats = aggregate(records); floor = float(policy["quality_floor"])
    minimum = int(policy.get("minimum_comparable_outcomes", 3))
    normal = (stats["evidence_count"] >= minimum and stats["pass_count"] == stats["evidence_count"]
              and (stats["conservative_quality"] or -1) >= floor
              and all((metric(r, "quality_score") or 0) >= floor and not r.get("regression")
                      for r in records if metric(r, "quality_score") is not None))
    early = bool(records and records[-1].get("promotion_status") == "early-decisive" and all_gates_pass(records[-1]) and (metric(records[-1], "quality_score") or 0) >= floor)
    status = "locally-proven" if normal else "early-decisive" if early else "provisional"
    return {"status": status, "normal": normal, "early_decisive": early, "stats": stats,
            "confirmation_required": early and not normal}


def compatibility(prior: dict[str, Any], task: dict[str, Any], context: dict[str, Any]) -> tuple[float, list[str]]:
    compared = [(key, prior.get("task_signature", {}).get(key, prior.get(key)), task.get(key)) for key in TASK_SIGNATURE_KEYS if task.get(key) is not None]
    matches = [key for key, a, b in compared if a == b]
    score = len(matches) / len(compared) if compared else 0.0
    profile = prior.get("profile", prior)
    if profile.get("provider") != context.get("provider") or profile.get("host") != context.get("host"):
        return 0.0, matches
    return score, matches


def task_signature_key(record: dict[str, Any]) -> str:
    signature = record.get("task_signature", record)
    return canonical({key: signature.get(key) for key in TASK_SIGNATURE_KEYS})


def comparable_groups(records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault(task_signature_key(record), []).append(record)
    return list(groups.values())


def sanitize(value: Any, key: str = "") -> Any:
    # Exact names avoid accidentally deleting safe fields such as prompt_profile
    # hashes and input_tokens, both needed to compare learned routes.
    forbidden = {"project", "project_name", "path", "paths", "source", "source_code", "prompt", "rendered_prompt", "raw_output", "output", "secret", "credential", "access_token", "api_key", "report", "artifact"}
    if key.lower() in forbidden: return None
    if isinstance(value, dict): return {k: v for k, x in value.items() if (v := sanitize(x, k)) is not None}
    if isinstance(value, list): return [x for x in (sanitize(x, key) for x in value) if x is not None]
    return value


def numeric(value: Any, label: str, *, positive: bool = False) -> float | None:
    if value is None: return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise UserError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result): raise UserError(f"{label} must be finite")
    if positive and result <= 0: raise UserError(f"{label} must be greater than zero")
    if not positive and result < 0: raise UserError(f"{label} must not be negative")
    return result


def timestamp(value: Any, label: str) -> dt.datetime | None:
    if value is None: return None
    if not isinstance(value, str): raise UserError(f"{label} must be an ISO-8601 string")
    try: parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc: raise UserError(f"{label} must be an ISO-8601 string") from exc
    if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def validate_guard_policy(guard: dict[str, Any]) -> list[str]:
    errors = []
    ratios = []
    for key in ("elevated_ratio", "high_ratio", "critical_ratio"):
        value = guard.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 < float(value) <= 1:
            errors.append(f"context_guard.{key} must be in (0, 1]")
        else: ratios.append(float(value))
    if len(ratios) == 3 and ratios != sorted(ratios):
        errors.append("context_guard ratios must be ordered elevated <= high <= critical")
    reduction = guard.get("minimum_compaction_reduction_ratio")
    if not isinstance(reduction, (int, float)) or isinstance(reduction, bool) or not 0 <= float(reduction) <= 1:
        errors.append("context_guard.minimum_compaction_reduction_ratio must be in [0, 1]")
    for key in ("repeated_compaction_limit", "repeated_compaction_window_minutes", "unattended_checkpoint_minutes"):
        value = guard.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) <= 0:
            errors.append(f"context_guard.{key} must be greater than zero")
    if guard.get("critical_action") != "stop_and_handoff":
        errors.append("context_guard.critical_action must be stop_and_handoff")
    return errors


def evaluate_guard(snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    allowed = {"observed_at", "telemetry", "context", "compactions", "checkpoint", "milestone", "history", "active_workers", "unattended"}
    extra = sorted(set(snapshot) - allowed)
    if extra: raise UserError("snapshot contains unsupported fields: " + ", ".join(extra))
    guard = policy["context_guard"]
    snapshot_id = digest({key: value for key, value in snapshot.items() if key != "checkpoint"}, 32)
    if not guard.get("enabled", True):
        return {"skill_release": RELEASE, "risk": "disabled", "reasons": ["context guard disabled by project policy"],
                "delegation_allowed": True, "checkpoint_required": False, "required_action": "continue",
                "telemetry": {"availability": "unavailable"}, "snapshot_id": snapshot_id}

    telemetry = snapshot.get("telemetry", {})
    if not isinstance(telemetry, dict): raise UserError("snapshot.telemetry must be an object")
    availability = telemetry.get("availability")
    if availability not in {None, "measured", "estimated", "unavailable"}:
        raise UserError("snapshot.telemetry.availability must be measured, estimated, or unavailable")
    context = snapshot.get("context", {})
    if not isinstance(context, dict): raise UserError("snapshot.context must be an object")
    used = numeric(context.get("used_tokens"), "snapshot.context.used_tokens")
    window = numeric(context.get("window_tokens"), "snapshot.context.window_tokens", positive=True)
    if (used is None) != (window is None): raise UserError("used_tokens and window_tokens must be supplied together")
    if availability == "unavailable" and used is not None:
        raise UserError("unavailable telemetry cannot include token measurements")
    declared_availability = availability or "unavailable"
    observed = timestamp(snapshot.get("observed_at"), "snapshot.observed_at")
    current = timestamp(now(), "current time")
    maximum_age = numeric(guard.get("max_observation_age_seconds", 300),
                          "context_guard.max_observation_age_seconds", positive=True)
    if maximum_age is None: raise UserError("context_guard.max_observation_age_seconds is required")
    fresh = bool(observed is not None and 0 <= (current - observed).total_seconds() <= maximum_age)
    usable = fresh and declared_availability in {"measured", "estimated"}
    availability = declared_availability if usable else "unavailable"
    history = snapshot.get("history", {})
    if not isinstance(history, dict): raise UserError("snapshot.history must be an object")
    unsupported_history = sorted(set(history) - {"attachment_count", "serialized_bytes", "task_age_minutes"})
    if unsupported_history: raise UserError("snapshot.history contains unsupported fields: " + ", ".join(unsupported_history))
    for key in history:
        numeric(history[key], f"snapshot.history.{key}")
    ratio = used / window if usable and used is not None and window is not None else None
    risk = "unknown" if ratio is None else "critical" if ratio >= float(guard["critical_ratio"]) else "high" if ratio >= float(guard["high_ratio"]) else "elevated" if ratio >= float(guard["elevated_ratio"]) else "healthy"
    reasons = [] if ratio is None else [f"context utilization is {ratio:.3f}"]

    compactions = snapshot.get("compactions", [])
    if not isinstance(compactions, list) or not all(isinstance(item, dict) for item in compactions):
        raise UserError("snapshot.compactions must be a list of objects")
    parsed_compactions = []
    for index, item in enumerate(compactions):
        before = numeric(item.get("before_tokens"), f"snapshot.compactions[{index}].before_tokens", positive=True)
        after = numeric(item.get("after_tokens"), f"snapshot.compactions[{index}].after_tokens")
        stamp = timestamp(item.get("timestamp"), f"snapshot.compactions[{index}].timestamp")
        if before is None or after is None or stamp is None:
            raise UserError("each compaction requires timestamp, before_tokens, and after_tokens")
        history_window = max(maximum_age, float(guard["repeated_compaction_window_minutes"]) * 60)
        if usable and 0 <= (current - stamp).total_seconds() <= history_window and stamp <= observed:
            parsed_compactions.append({"timestamp": stamp, "before": before, "after": after})
    parsed_compactions.sort(key=lambda item: item["timestamp"])
    if parsed_compactions and (current - parsed_compactions[-1]["timestamp"]).total_seconds() <= maximum_age:
        latest = parsed_compactions[-1]
        reduction = (latest["before"] - latest["after"]) / latest["before"]
        post_ratio = latest["after"] / window if window is not None else None
        if reduction < float(guard["minimum_compaction_reduction_ratio"]):
            risk = "critical"; reasons.append(f"latest compaction reduced context by only {reduction:.3f}")
        if post_ratio is not None and post_ratio >= float(guard["critical_ratio"]):
            risk = "critical"; reasons.append(f"post-compaction utilization is {post_ratio:.3f}")
        anchor = timestamp(snapshot.get("observed_at"), "snapshot.observed_at") or latest["timestamp"]
        cutoff = anchor - dt.timedelta(minutes=float(guard["repeated_compaction_window_minutes"]))
        recent = [item for item in parsed_compactions if cutoff <= item["timestamp"] <= anchor]
        stayed_high = window is not None and all(item["after"] / window >= float(guard["high_ratio"]) for item in recent)
        if len(recent) >= int(guard["repeated_compaction_limit"]) and stayed_high:
            risk = "critical"; reasons.append(f"{len(recent)} compactions stayed above the high-risk threshold")

    checkpoint = snapshot.get("checkpoint", {})
    milestone = snapshot.get("milestone", {})
    if not isinstance(checkpoint, dict): raise UserError("snapshot.checkpoint must be an object")
    if not isinstance(milestone, dict): raise UserError("snapshot.milestone must be an object")
    completed = checkpoint.get("completed_for_snapshot") == snapshot_id
    minutes_since = numeric(checkpoint.get("minutes_since"), "snapshot.checkpoint.minutes_since")
    material_milestone = bool(milestone.get("completed", False))
    unattended = bool(snapshot.get("unattended", False))
    milestone_checkpoint = bool(guard.get("checkpoint_on_material_milestone", True) and material_milestone)
    fallback_checkpoint = bool(availability == "unavailable" and unattended and minutes_since is not None
                               and minutes_since >= float(guard["unattended_checkpoint_minutes"]))
    checkpoint_required = risk in {"high", "critical"} or milestone_checkpoint or fallback_checkpoint
    if completed and risk != "critical": checkpoint_required = False
    if risk == "unknown":
        reasons.append("fresh explicitly sourced context token telemetry is unavailable")
    if milestone_checkpoint: reasons.append("material milestone reached")
    if fallback_checkpoint: reasons.append("unattended telemetry fallback elapsed")

    delegation_allowed = risk != "critical" and not checkpoint_required
    if risk == "critical": action = "stop_and_handoff"
    elif checkpoint_required: action = "checkpoint_before_delegation"
    elif risk == "elevated": action = "minimize_inline_payloads"
    else: action = "continue"
    return {
        "skill_release": RELEASE,
        "snapshot_id": snapshot_id,
        "observed_at": snapshot.get("observed_at"),
        "risk": risk,
        "reasons": reasons,
        "context_utilization": {"value": ratio, "availability": availability},
        "delegation_allowed": delegation_allowed,
        "checkpoint_required": checkpoint_required,
        "required_action": action,
        "active_workers": int(numeric(snapshot.get("active_workers", 0), "snapshot.active_workers") or 0),
        "telemetry": {"availability": availability, "declared_availability": declared_availability,
                      "fresh": fresh, "max_observation_age_seconds": maximum_age},
        "enforcement": "cooperative-host-protocol",
    }


HANDOFF_FIELDS = {"objective", "completed", "decisions", "remaining", "validation", "artifact_references", "active_workers", "next_action"}
HANDOFF_LIST_FIELDS = {"completed", "decisions", "remaining", "validation", "artifact_references", "active_workers"}
FORBIDDEN_HANDOFF_KEYS = {"source", "source_code", "prompt", "rendered_prompt", "raw_output", "reasoning", "reasoning_trace", "secret", "credential", "access_token", "api_key", "screenshot", "image"}
SECRET_MARKERS = ("-----BEGIN PRIVATE KEY-----", "sk-", "api_key=", "access_token=", "hooks.slack.com/services/")


def validate_handoff(summary: dict[str, Any]) -> dict[str, Any]:
    validate_public_value(summary)
    extra = sorted(set(summary) - HANDOFF_FIELDS)
    forbidden_extra = [key for key in extra if key.lower() in FORBIDDEN_HANDOFF_KEYS]
    if forbidden_extra: raise UserError("handoff field is forbidden: " + ", ".join(forbidden_extra))
    if extra: raise UserError("handoff contains unsupported fields: " + ", ".join(extra))
    if not isinstance(summary.get("objective"), str) or not summary["objective"].strip():
        raise UserError("handoff.objective must be a non-empty string")
    if len(summary["objective"]) > 2000: raise UserError("handoff.objective is too large")
    for key in HANDOFF_LIST_FIELDS:
        value = summary.get(key, [])
        if not isinstance(value, list) or len(value) > 50: raise UserError(f"handoff.{key} must be a list of at most 50 items")
    def inspect(value: Any, key: str = "") -> None:
        if key.lower() in FORBIDDEN_HANDOFF_KEYS: raise UserError(f"handoff field is forbidden: {key}")
        if isinstance(value, dict):
            for child_key, child in value.items(): inspect(child, str(child_key))
        elif isinstance(value, list):
            for child in value: inspect(child, key)
        elif isinstance(value, str):
            if len(value) > 4000: raise UserError(f"handoff value is too large: {key or 'value'}")
            if any(marker.lower() in value.lower() for marker in SECRET_MARKERS):
                raise UserError("handoff contains a possible secret")
        elif value is not None and not isinstance(value, (int, float, bool)):
            raise UserError(f"handoff contains unsupported value for {key}")
    inspect(summary)
    return summary


def handoff_markdown(run_id: str, summary: dict[str, Any], created_at: str) -> str:
    lines = [f"# Ultra Delegation Handoff: {run_id}", "", f"Release: {RELEASE}", f"Created: {created_at}", "", "## Objective", "", summary["objective"]]
    labels = (("completed", "Completed"), ("decisions", "Decisions"), ("remaining", "Remaining"),
              ("validation", "Validation"), ("artifact_references", "Artifact references"),
              ("active_workers", "Active worker disposition"))
    for key, label in labels:
        lines.extend(["", f"## {label}", ""])
        values = summary.get(key, [])
        if not values: lines.append("- None")
        else:
            for value in values:
                rendered = canonical(value) if isinstance(value, dict) else str(value)
                lines.append(f"- {rendered}")
    lines.extend(["", "## Next action", "", str(summary.get("next_action", "Start a fresh task from this handoff.")), ""])
    return "\n".join(lines)


def report_data(records: list[dict[str, Any]], policy: dict[str, Any], project_scope: bool = False) -> dict[str, Any]:
    stats = aggregate(records)
    accepted = [r for r in records if all_gates_pass(r) and (metric(r, "quality_score") or 0) >= policy["quality_floor"]]
    priced = [r for r in records if cost(r, policy)[0] is not None]
    selected_records = [r for r in accepted if r.get("selected")]
    if not selected_records and len(accepted) == 1: selected_records = accepted
    selected = sum(cost(r, policy)[0] or 0 for r in selected_records) if selected_records and all(cost(r, policy)[0] is not None for r in selected_records) else None
    selected_kinds = {cost(r, policy)[1] for r in selected_records}
    selected_kind = selected_kinds.pop() if len(selected_kinds) == 1 else "unavailable" if not selected_records else "mixed"
    comparator_records = [r for r in records if r.get("comparator")]
    comparator = sum(cost(r, policy)[0] or 0 for r in comparator_records) if comparator_records and all(cost(r, policy)[0] is not None for r in comparator_records) else None
    comparator_kinds = {cost(r, policy)[1] for r in comparator_records}
    baseline_kind = comparator_kinds.pop() if len(comparator_kinds) == 1 else "unavailable" if comparator is None else "mixed"
    if comparator is None:
        for r in records:
            b = metric(r, "baseline_cost_usd")
            if b is not None:
                comparator = b; baseline_kind = r.get("baseline_cost_kind", "estimated"); break
    experiment = sum(cost(r, policy)[0] or 0 for r in priced) if priced and len(priced) == len(records) else None
    experiment_kinds = {cost(r, policy)[1] for r in priced}
    experiment_kind = "unavailable" if experiment is None else experiment_kinds.pop() if len(experiment_kinds) == 1 else "mixed"
    is_experiment = any(r.get("experiment", False) for r in records)
    per_task = comparator - selected if comparator is not None and selected is not None else None
    investment = max(0, experiment - selected) if experiment is not None and selected is not None and is_experiment else 0.0 if selected is not None else None
    break_even = math.ceil(investment / per_task) if investment is not None and per_task and per_task > 0 else None
    realized = 0.0 if is_experiment and per_task is not None else per_task
    if project_scope:
        routine_savings = []
        for record in accepted:
            if record.get("experiment", False): continue
            actual = cost(record, policy)[0]; baseline_value = metric(record, "baseline_cost_usd")
            if actual is not None and baseline_value is not None: routine_savings.append(baseline_value - actual)
        realized = sum(routine_savings) if routine_savings else None
        per_task = None
        break_even = None
    def average_metric(key: str) -> float | None:
        values = [metric(record, key) for record in records]
        values = [value for value in values if value is not None]
        return sum(values) / len(values) if values else None
    performance = {
        "mean_latency_ms": average_metric("latency_ms"),
        "mean_time_to_first_token_ms": average_metric("time_to_first_token_ms"),
        "mean_tokens_per_second": average_metric("tokens_per_second"),
        "mean_tool_turns": average_metric("tool_turns"),
        "total_retries": sum(metric(record, "retries") for record in records) if records and all(metric(r, "retries") is not None for r in records) else None,
        "total_escalations": sum(metric(record, "escalations") for record in records) if records and all(metric(r, "escalations") is not None for r in records) else None,
        "availability": "measured" if any(metric(record, "latency_ms") is not None for record in records) else "unavailable",
    }
    profiles = []
    seen_profiles = set()
    for record in records:
        profile = record.get("profile", {})
        if not profile: continue
        pid = record.get("profile_id") or profile_id(profile)
        if pid in seen_profiles: continue
        seen_profiles.add(pid)
        profiles.append({"profile_id": pid, "model_revision": profile.get("model_revision", profile.get("model")),
                         "host": profile.get("host"), "provider": profile.get("provider"),
                         "thinking": profile.get("thinking"), "prompt_profile": profile.get("prompt_profile"),
                         "tool_policy": profile.get("tool_policy")})
    details = {
        "run_ids": sorted({r.get("run_id") for r in records if r.get("run_id")}),
        "profiles": profiles,
        "baseline_revisions": sorted({r.get("baseline_revision") for r in records if r.get("baseline_revision")}),
        "isolation_modes": sorted({r.get("isolation_mode") for r in records if r.get("isolation_mode")}),
        "verification_commands": sorted({command for r in records for command in r.get("verification_commands", [])}),
        "artifact_hashes": sorted({value for r in records for value in r.get("artifact_hashes", [])}),
        "promotion_statuses": sorted({r.get("promotion_status") for r in records if r.get("promotion_status")}),
        "candidates": [
            {"profile_id": r.get("profile_id") or profile_id(r["profile"]),
             "quality_score": metric(r, "quality_score"), "accepted": all_gates_pass(r),
             "selected": bool(r.get("selected")), "comparator": bool(r.get("comparator"))}
            for r in records if r.get("profile")
        ],
    }
    return {"skill_release": RELEASE, "generated_at": now(), "records": len(records), "quality": stats, "performance": performance,
            "local_execution": {"mode": policy["local_execution"]["mode"], "runtime_support": "unsupported",
                                "results": [r["local_execution"] for r in records if r.get("local_execution")]},
            "cost": {"selected_total_usd": selected, "selected_cost_kind": selected_kind,
                     "experiment_total_usd": experiment if records else None, "experiment_cost_kind": experiment_kind,
                     "comparator_cost_usd": comparator, "baseline_kind": baseline_kind,
                     "experiment_overhead_usd": investment, "realized_savings_usd": realized,
                     "projected_savings_per_task_usd": per_task if is_experiment else None,
                     "break_even_tasks": break_even},
            "details": details,
            "telemetry_note": "Values are unavailable when hosts did not provide them; no values are inferred."}


def markdown_report(data: dict[str, Any], title: str) -> str:
    quality = data["quality"]; cost_data = data["cost"]; performance = data["performance"]; details = data["details"]
    def shown(x: Any) -> str: return "unavailable" if x is None else str(round(x, 3) if isinstance(x, float) else x)
    candidate_scores = ", ".join(f"{candidate['profile_id']}={shown(candidate['quality_score'])}" for candidate in details["candidates"])
    lines = [f"# {title}", "", f"Release: {data.get('skill_release', RELEASE)}", f"Generated: {data['generated_at']}", "",
        "## Quality", f"- Evidence: {quality['evidence_count']}; passing: {quality['pass_count']}",
        f"- Mean / conservative score: {shown(quality['mean_quality'])} / {shown(quality['conservative_quality'])}", "",
        "## Cost and value", f"- Selected cost ({cost_data['selected_cost_kind']}): {shown(cost_data['selected_total_usd'])}",
        f"- Comparator cost ({cost_data['baseline_kind']}): {shown(cost_data['comparator_cost_usd'])}",
        f"- Experiment cost ({cost_data['experiment_cost_kind']}): {shown(cost_data['experiment_total_usd'])}",
        f"- Experiment overhead: {shown(cost_data['experiment_overhead_usd'])}",
        f"- Realized savings: {shown(cost_data['realized_savings_usd'])}",
        f"- Projected savings per task: {shown(cost_data['projected_savings_per_task_usd'])}",
        f"- Break-even tasks: {shown(cost_data['break_even_tasks'])}", "",
        "## Performance", f"- Availability: {performance['availability']}",
        f"- Mean latency (ms): {shown(performance['mean_latency_ms'])}",
        f"- Mean time to first token (ms): {shown(performance['mean_time_to_first_token_ms'])}",
        f"- Mean throughput (tokens/s): {shown(performance['mean_tokens_per_second'])}",
        f"- Mean tool turns: {shown(performance['mean_tool_turns'])}",
        f"- Retries / escalations: {shown(performance['total_retries'])} / {shown(performance['total_escalations'])}",
        "", "## Reproducibility",
        f"- Runs: {', '.join(details['run_ids']) or 'unavailable'}",
        f"- Baselines: {', '.join(details['baseline_revisions']) or 'unavailable'}",
        f"- Isolation: {', '.join(details['isolation_modes']) or 'unavailable'}",
        f"- Profiles: {', '.join(p['profile_id'] for p in details['profiles']) or 'unavailable'}",
        f"- Candidate scores: {candidate_scores or 'unavailable'}",
        f"- Verification: {', '.join(details['verification_commands']) or 'unavailable'}",
        f"- Promotion: {', '.join(details['promotion_statuses']) or 'provisional'}",
        ""]
    local = data.get("local_execution", {})
    lines.extend(["## Local execution", "", f"- Mode: {local.get('mode', 'disabled')}",
                  f"- Runtime support: {local.get('runtime_support', 'unsupported')}",
                  f"- Resource events: {len(local.get('results', []))}", ""])
    guard = data.get("context_guard")
    if guard:
        lines.extend(["## Context guard", f"- Events: {guard['events']}",
                      f"- Latest risk: {guard.get('latest_risk', 'unavailable')}",
                      f"- Delegation allowed: {guard.get('delegation_allowed', 'unavailable')}",
                      f"- Required action: {guard.get('required_action', 'unavailable')}", ""])
    lines.extend([data["telemetry_note"], ""])
    return "\n".join(lines)


def cmd_init(args: argparse.Namespace) -> dict[str, Any]:
    root = root_from(args); root.mkdir(parents=True, exist_ok=True)
    path = policy_path(root)
    if path.exists() and not args.force: raise UserError(f"policy already exists: {path} (use --force to replace)")
    write_json(path, DEFAULT_POLICY)
    ignore_path = root.parent / ".gitignore"
    ignore_entries = [
        f"{root.name}/evidence.jsonl",
        f"{root.name}/runs/",
        f"{root.name}/reports/",
        f"{root.name}/imports/",
    ]
    existing = ignore_path.read_text().splitlines() if ignore_path.exists() else []
    missing = [entry for entry in ignore_entries if entry not in existing]
    if missing:
        content = "\n".join(existing + ([""] if existing and existing[-1] else [])
                            + ["# Ultra Delegation local evidence and generated artifacts"] + missing) + "\n"
        write_text(ignore_path, content)
    return {"root": str(root), "policy": str(path), "gitignore": str(ignore_path),
            "phase_1": "local-only; no provider execution"}


def cmd_validate(args: argparse.Namespace) -> dict[str, Any]:
    root = root_from(args); policy = load_policy(root)
    errors = []
    if policy.get("external_adapters") != "disabled": errors.append("Phase 1 requires external_adapters=disabled")
    if not 0 <= float(policy.get("quality_floor", -1)) <= 100: errors.append("quality_floor must be 0..100")
    errors.extend(validate_guard_policy(policy["context_guard"]))
    if policy["local_execution"].get("mode") not in {"disabled", "ask", "enabled"}:
        errors.append("local_execution.mode must be disabled, ask, or enabled")
    for r in read_jsonl(evidence_path(root)):
        try:
            normalized = normalize_outcome(r)
            validate_profile(normalized["profile"])
            if normalized.get("status") != "imported-prior-pending-verification":
                validate_outcome(normalized)
        except (KeyError, UserError, ValueError, TypeError) as exc: errors.append(str(exc))
    return {"skill_release": RELEASE, "valid": not errors, "errors": errors, "root": str(root)}


def cmd_doctor(args: argparse.Namespace) -> dict[str, Any]:
    context = object_arg(args.context, "context")
    policy = load_policy(root_from(args))
    profiles = context.get("profiles", [])
    results = []
    for profile in profiles:
        validate_profile(profile)
        allowed, reason = eligible(profile, context, policy)
        results.append({"profile_id": profile_id(profile), "eligible": allowed,
                        "reason": reason, "local_execution": evaluate_local(profile, context, policy)})
    return {"skill_release": RELEASE, "host": context.get("host"),
            "capability_source": "host-supplied", "execution_verified": False,
            "local_execution_mode": policy["local_execution"]["mode"],
            "local_runtime_support": "unsupported: monitored execution adapter not shipped",
            "profiles": results, "models_discovered": context.get("available_models"),
            "python": sys.version.split()[0]}


def guard_run_dir(root: Path, run_id: str) -> Path:
    if not run_id or len(run_id) > 100: raise UserError("run-id must contain 1-100 characters")
    if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id):
        raise UserError("run-id must contain only letters, numbers, hyphens, and underscores")
    return safe_child(root / "runs", run_id)


def cmd_guard_evaluate(args: argparse.Namespace) -> dict[str, Any]:
    root = root_from(args)
    result = evaluate_guard(object_arg(args.snapshot, "snapshot"), load_policy(root))
    if args.write:
        if not args.run_id: raise UserError("--run-id is required with --write")
        target = guard_run_dir(root, args.run_id) / "guard-state.json"
        write_json(target, result)
        result["state_path"] = str(target)
    return result


def cmd_guard_checkpoint(args: argparse.Namespace) -> dict[str, Any]:
    if not args.write: raise UserError("guard checkpoint requires --write")
    root = root_from(args); summary = validate_handoff(object_arg(args.summary, "summary"))
    target = guard_run_dir(root, args.run_id); created_at = now()
    prior = read_json(target / "guard-state.json", {})
    snapshot_id = prior.get("snapshot_id")
    if not isinstance(snapshot_id, str) or len(snapshot_id) != 32:
        raise UserError("write a guard evaluation for this run before creating its checkpoint")
    envelope = {"skill_release": RELEASE, "run_id": args.run_id, "created_at": created_at,
                "snapshot_id": snapshot_id, "completed_for_snapshot": snapshot_id,
                "delegation_state": "requires_guard_reevaluation", "summary": summary}
    json_path = target / "handoff.json"; markdown_path = target / "handoff.md"
    write_json(json_path, envelope); write_text(markdown_path, handoff_markdown(args.run_id, summary, created_at))
    return {"skill_release": RELEASE, "run_id": args.run_id, "checkpointed": True,
            "completed_for_snapshot": snapshot_id,
            "paths": [str(markdown_path), str(json_path)], "delegation_allowed": False,
            "next_action": summary.get("next_action", "Start a fresh task from this handoff.")}


def cmd_rank(args: argparse.Namespace) -> dict[str, Any]:
    root = root_from(args); policy = load_policy(root); context = object_arg(args.context, "context")
    task = object_arg(args.task, "task"); candidates = json_arg(args.candidates, "candidates")
    if not isinstance(candidates, list): raise UserError("candidates must be a JSON list")
    if policy.get("global_catalog") and catalog_path().exists():
        candidates += [{"profile": entry.get("profile", {}), "imported_prior": entry, "source": "global"}
                       for entry in (sanitize_learning(r) for r in read_jsonl(catalog_path()))]
    records = read_records_input(getattr(args, "records", None), evidence_path(root)); results = []
    seen = set()
    for candidate in candidates:
        if not isinstance(candidate, dict): raise UserError("each candidate must be an object")
        p = candidate.get("profile", candidate)
        validate_profile(p); pid = profile_id(p)
        same = [r for r in records if (r.get("profile_id") or profile_id(r["profile"])) == pid and compatibility(r, task, context)[0] == 1.0]
        if pid in seen: continue
        seen.add(pid)
        ok, reason = eligible(p, context, policy); state = promotion(same, policy)
        local_verified = any(r.get("status") == "locally-verified" and all_gates_pass(r) and (metric(r, "quality_score") or 0) >= policy["quality_floor"] for r in same)
        retest = bool(same and (is_stale(same[-1], policy) or
                      int(same[-1].get("selections_since_test", 0)) >= policy["confirmation_after_selections"] or
                      same[-1].get("regression", False) or
                      not all_gates_pass(same[-1]) and same[-1].get("status") not in {"imported-prior-pending-verification"}))
        if retest:
            state["normal"] = False
            state["status"] = "retest-required"
            local_verified = False
        quarantined_local = any(r.get("status") == "quarantined" for r in same)
        if quarantined_local and ok:
            ok, reason = False, "quarantined local evidence"
        pending_local_import = not quarantined_local and not retest and bool(same and same[-1].get("status") == "imported-prior-pending-verification" and not same[-1].get("comparison_required"))
        imported = sanitize_learning(candidate["imported_prior"]) if candidate.get("imported_prior") else {}
        comp, matches = compatibility(imported, task, context) if imported else (0.0, [])
        source_stats = imported.get("aggregate", {}) if isinstance(imported, dict) else {}
        imported_ok = bool(imported and comp >= float(policy.get("import_compatibility_floor", .80))
                           and imported.get("profile_id") == pid and profile_id(imported.get("profile", {})) == pid
                           and imported.get("source_passed_gates")
                           and imported.get("promotion") not in {"early-decisive", "provisional"}
                           and imported.get("confidence") not in {"low", "moderate", "medium"}
                           and int(source_stats.get("evidence_count", 0)) >= int(policy.get("minimum_comparable_outcomes", 3))
                           and source_stats.get("pass_count") == source_stats.get("evidence_count")
                           and float(source_stats.get("conservative_quality", -1)) >= float(policy["quality_floor"])
                           and not is_stale(imported, policy))
        pinned = any(matches_rule(p, rule) for rule in policy.get("pins", []))
        tier = 5 if candidate.get("user_selected") else 4 if pinned else 3 if (state["normal"] or local_verified) else (2 if (imported_ok or pending_local_import) and not quarantined_local else 1)
        results.append({"profile_id": pid, "eligible": ok, "reason": reason, "tier": tier,
                        "status": "quarantined" if quarantined_local else "locally-verified" if local_verified else "imported-prior-pending-verification" if pending_local_import else state["status"],
                        "stats": state["stats"], "import_compatibility": comp,
                        "import_matches": matches, "pending_verification": (imported_ok or pending_local_import) and not quarantined_local,
                        "source": candidate.get("source", "provided"),
                        "cost_usd": state["stats"]["mean_cost_usd"] if same else source_stats.get("mean_cost_usd")})
    results.sort(key=lambda x: (not x["eligible"], -x["tier"], x["cost_usd"] is None, x["cost_usd"] if x["cost_usd"] is not None else float("inf"), -(x["stats"]["conservative_quality"] or -1)))
    return {"task": task, "ranked": results, "rule": "locality filter precedes evidence and cost"}


def cmd_experiment_score(args: argparse.Namespace) -> dict[str, Any]:
    experiment = object_arg(args.experiment, "experiment"); candidates = experiment.get("candidates", [])
    context = object_arg(args.context, "context"); policy = load_policy(root_from(args))
    floor = max(float(policy["quality_floor"]), float(experiment.get("quality_floor", policy["quality_floor"])))
    variable = experiment.get("variable")
    if variable not in {"model", "thinking", "prompt_profile"}: raise UserError("experiment.variable must be model, thinking, or prompt_profile")
    if len(candidates) < 2 or len(candidates) > 3: raise UserError("experiments require 2-3 candidates")
    profiles = [candidate.get("profile", {}) for candidate in candidates]
    for candidate, profile in zip(candidates, profiles):
        validate_profile(profile)
        allowed, reason = eligible(profile, context, policy)
        if not allowed:
            raise UserError(f"experiment candidate {candidate.get('id', profile_id(profile))} is ineligible: {reason}")
    identity_keys = {
        "task_family", "provider", "model", "model_revision", "host",
        "thinking", "prompt_profile", "tool_policy",
    }
    varying_keys = {"model", "model_revision"} if variable == "model" else {variable}
    constant_keys = identity_keys - varying_keys
    changed = []
    for key in sorted(constant_keys):
        values = {
            canonical(profile.get(key, profile["model"] if key == "model_revision" else None))
            for profile in profiles
        }
        if len(values) != 1: changed.append(key)
    if changed: raise UserError("one-variable rule violated; also changed " + ", ".join(changed))
    scored = []
    for candidate in candidates:
        result = normalize_outcome(candidate.get("result", {})); score = metric(result, "quality_score")
        scored.append({"id": candidate.get("id"), "passes": all_gates_pass(result), "quality_score": score,
                       "cost_usd": cost(result)[0], "latency_ms": metric(result, "latency_ms")})
    viable = [x for x in scored if x["passes"] and x["quality_score"] is not None and x["quality_score"] >= floor]
    viable.sort(key=lambda x: (x["cost_usd"] is None, x["cost_usd"] if x["cost_usd"] is not None else float("inf"), -(x["quality_score"] or -1)))
    early_reason = None
    if len(viable) == 1:
        early_reason = "only passing candidate"
    elif len(viable) >= 2:
        by_quality = sorted(viable, key=lambda x: -(x["quality_score"] or -1))
        best_quality, next_quality = by_quality[:2]
        quality_lead = (best_quality["quality_score"] or 0) - (next_quality["quality_score"] or 0)
        major_cost_penalty = (best_quality["cost_usd"] is not None and next_quality["cost_usd"] is not None
                              and best_quality["cost_usd"] > 2 * next_quality["cost_usd"])
        if quality_lead >= policy["quality_margin"] and not major_cost_penalty and best_quality["cost_usd"] is not None and next_quality["cost_usd"] is not None:
            viable.remove(best_quality); viable.insert(0, best_quality)
            early_reason = "quality lead"
        else:
            for cheaper in viable:
                for other in viable:
                    if cheaper is other or cheaper["cost_usd"] is None or other["cost_usd"] is None:
                        continue
                    quality_close = abs((cheaper["quality_score"] or 0) - (other["quality_score"] or 0)) <= policy["quality_equivalence_points"]
                    latency_close = (cheaper["latency_ms"] is not None and other["latency_ms"] is not None
                                     and abs(cheaper["latency_ms"] - other["latency_ms"]) / max(other["latency_ms"], 1) <= policy["latency_equivalence_ratio"])
                    if other["cost_usd"] > 0 and cheaper["cost_usd"] <= (1-policy["cost_reduction_ratio"]) * other["cost_usd"] and quality_close and latency_close:
                        viable.remove(cheaper); viable.insert(0, cheaper)
                        early_reason = "equivalent quality and latency at half cost"
                        break
                if early_reason: break
    return {"experiment_id": experiment.get("id", "exp_" + digest(experiment)), "variable": variable,
            "scored": scored, "winner": viable[0]["id"] if viable else None,
            "outcome": "winner" if viable else "inconclusive", "quality_floor": floor,
            "promotion_status": "early-decisive" if early_reason else "provisional",
            "early_decisive_reason": early_reason,
            "confirmation_required": bool(early_reason)}


def cmd_record(args: argparse.Namespace) -> dict[str, Any]:
    root = root_from(args); record = validate_outcome(object_arg(args.record, "record")); validate_profile(record.get("profile", {}))
    if (metric(record, "quality_score") or 0) < load_policy(root)["quality_floor"]:
        record["accepted"] = False
    record = {**record, "schema": "ultra-delegation-evidence-v1", "created_at": record.get("created_at", now()),
              "profile_id": profile_id(record["profile"])}
    append_jsonl(evidence_path(root), record)
    return {"recorded": record["profile_id"], "accepted": all_gates_pass(record), "path": str(evidence_path(root))}


def cmd_report(args: argparse.Namespace) -> dict[str, Any]:
    root = root_from(args); records = read_records_input(getattr(args, "records", None), evidence_path(root))
    if args.report_kind == "run": records = [r for r in records if r.get("run_id") == args.run_id]
    data = report_data(records, load_policy(root), project_scope=args.report_kind == "project"); title = f"Ultra Delegation {args.report_kind.title()} Report"
    guard_paths = []
    if args.report_kind == "run":
        candidate = guard_run_dir(root, args.run_id) / "guard-state.json"
        if candidate.exists(): guard_paths.append(candidate)
    else:
        runs_root = root / "runs"
        if runs_root.exists(): guard_paths = sorted(runs_root.glob("*/guard-state.json"))
    guard_states = [read_json(path) for path in guard_paths]
    if guard_states:
        latest = guard_states[-1]
        data["context_guard"] = {"events": len(guard_states), "latest_risk": latest.get("risk"),
                                 "delegation_allowed": latest.get("delegation_allowed"),
                                 "required_action": latest.get("required_action")}
    output = {"data": data, "markdown": markdown_report(data, title)}
    if args.write:
        report_id = args.run_id or "project"
        guard_run_dir(root, report_id)
        target = safe_child(root / "reports", f"{report_id}.json")
        write_json(target, data); write_text(target.with_suffix(".md"), output["markdown"])
        output["paths"] = [str(target), str(target.with_suffix('.md'))]
    return output


def cmd_catalog_promote(args: argparse.Namespace) -> dict[str, Any]:
    root = root_from(args); pid = args.profile_id; records = [r for r in read_records_input(None, evidence_path(root)) if r.get("profile_id") == pid]
    if not records: raise UserError(f"no local evidence for profile: {pid}")
    policy = load_policy(root)
    groups = comparable_groups(records)
    promotable = [(group, promotion(group, policy)) for group in groups]
    promotable = [(group, state) for group, state in promotable if state["normal"]]
    if not promotable and args.force:
        latest = max(groups, key=lambda group: group[-1].get("created_at", ""))
        promotable = [(latest, promotion(latest, policy))]
    if not promotable:
        raise UserError("profile has no locally proven comparable task group; use --force only for explicit human promotion")
    ids = []
    for group, state in promotable:
        last = group[-1]
        entry = {"schema": SCHEMA, "catalog_id": "cat_" + uuid.uuid4().hex, "created_at": now(), "profile_id": pid,
                 "profile": last["profile"], "task_signature": last.get("task_signature", {}),
                 "aggregate": state["stats"], "promotion": "explicit" if args.force else "normal",
                 "source_passed_gates": state["stats"]["evidence_count"] > 0 and state["stats"]["pass_count"] == state["stats"]["evidence_count"]}
        append_jsonl(catalog_path(), sanitize_learning(entry)); ids.append(entry["catalog_id"])
    return {"promoted": ids[0], "promoted_ids": ids, "promoted_count": len(ids), "catalog": str(catalog_path())}


def cmd_catalog_list(args: argparse.Namespace) -> dict[str, Any]: return {"entries": read_jsonl(catalog_path()), "catalog": str(catalog_path())}
def cmd_catalog_report(args: argparse.Namespace) -> dict[str, Any]:
    entries = read_jsonl(catalog_path())
    return {"catalog": str(catalog_path()), "entries": len(entries),
            "normal": sum(e.get("promotion") == "normal" for e in entries),
            "explicit": sum(e.get("promotion") == "explicit" for e in entries),
            "task_families": sorted({e.get("profile", {}).get("task_family") for e in entries if e.get("profile", {}).get("task_family")})}


def cmd_export(args: argparse.Namespace) -> dict[str, Any]:
    root = root_from(args); records = read_records_input(getattr(args, "records", None), evidence_path(root)); grouped: dict[str, list[dict[str, Any]]] = {}
    for r in records: grouped.setdefault(r.get("profile_id", "unknown"), []).append(r)
    learnings = []
    for pid, profile_records in grouped.items():
        for group in comparable_groups(profile_records):
            state = promotion(group, load_policy(root)); last = group[-1]
            learnings.append(sanitize_learning({"profile_id": pid, "profile": last["profile"], "task_signature": last.get("task_signature", {}),
                                      "aggregate": state["stats"], "promotion": state["status"],
                                      "source_passed_gates": state["stats"]["evidence_count"] > 0 and state["stats"]["pass_count"] == state["stats"]["evidence_count"],
                                      "fresh_at": last.get("created_at"),
                                      "provenance_hash": digest({"id": pid, "task": task_signature_key(last), "n": len(group)})}))
    bundle = {"schema": SCHEMA, "exported_at": now(), "learnings": learnings}
    output = Path(args.output).absolute()
    if output.suffix != ".json" or output.name in {"policy.json", "config.json", "settings.json", "opencode.json", "mcp.json"}:
        raise UserError("export requires a dedicated .json bundle output path")
    if output.is_symlink(): raise UserError("export refuses symlink outputs")
    if output.exists(): raise UserError("export refuses overwriting an existing file; choose a new bundle path")
    write_json(output, bundle)
    return {"exported": len(learnings), "path": str(output), "sanitized": True}


def cmd_import(args: argparse.Namespace) -> dict[str, Any]:
    root = root_from(args); bundle = read_json(Path(args.input));
    if bundle.get("schema") != SCHEMA: raise UserError(f"unsupported learning schema: {bundle.get('schema')}")
    task = object_arg(args.task, "task"); context = object_arg(args.context, "context"); policy = load_policy(root)
    existing = read_jsonl(evidence_path(root)); accepted, rejected = [], []
    for learning in bundle.get("learnings", []):
        learning = sanitize_learning(learning)
        if learning.get("profile_id") != profile_id(learning.get("profile", {})):
            raise UserError("imported profile_id does not match its profile")
        learning["content_id"] = digest(learning, 64)
        p = learning.get("profile", {}); ok, why = eligible(p, context, policy); comp, matched = compatibility(learning, task, context)
        stats = learning.get("aggregate", {})
        stale = is_stale(learning, policy)
        available_models = context.get("available_models")
        available = available_models is not None and p.get("model_revision", p.get("model")) in available_models
        source_promotion = learning.get("promotion")
        source_qualified = int(stats.get("evidence_count", 0)) >= int(policy.get("minimum_comparable_outcomes", 3)) or source_promotion == "explicit"
        if stats.get("pass_count") != stats.get("evidence_count") or not stats.get("evidence_count"):
            source_qualified = False
        comparison_required = source_promotion in {"early-decisive", "provisional"} or learning.get("confidence") in {"low", "moderate"}
        local_conflict = any(task_signature_key(r) == task_signature_key(task)
                             and r.get("profile_id") != learning.get("profile_id")
                             and promotion([x for x in existing if x.get("profile_id") == r.get("profile_id")], policy)["normal"]
                             for r in existing)
        trusted = (ok and comp >= float(policy.get("import_compatibility_floor", .80))
                   and bool(learning.get("source_passed_gates")) and source_qualified
                   and (stats.get("conservative_quality") or -1) >= policy["quality_floor"]
                   and not stale and available and not local_conflict)
        failure = why if not ok else "stale" if stale else "model unavailable" if not available else "stronger local conflict" if local_conflict else "insufficient compatibility/evidence"
        item = {"profile_id": learning.get("profile_id"), "eligible": trusted,
                "reason": "exploratory prior requiring local comparison" if trusted and comparison_required else "trusted prior pending local verification" if trusted else failure,
                "compatibility": comp, "matches": matched, "comparison_required": comparison_required}
        (accepted if trusted else rejected).append((item, learning))
    if args.apply:
        for item, learning in accepted:
            record = {"schema": "ultra-delegation-import-v1", "created_at": now(), "profile_id": learning["profile_id"], "profile": learning["profile"],
                      "task_signature": learning.get("task_signature", {}), "imported_prior": True,
                      "status": "imported-prior-pending-verification", "provenance_hash": learning.get("provenance_hash"),
                      "content_id": learning["content_id"],
                      "source_promotion": learning.get("promotion"), "comparison_required": item["comparison_required"],
                      "accepted": False, "gates": [], "metrics": {}}
            if not any(r.get("content_id") == record["content_id"] for r in existing):
                append_jsonl(evidence_path(root), record)
                existing.append(record)
    return {"dry_run": not args.apply, "accepted": [x[0] for x in accepted], "rejected": [x[0] for x in rejected],
            "trust_but_verify": "accepted priors are pending local verification; failed verification must be quarantined and trigger a bakeoff"}


def cmd_verify_import(args: argparse.Namespace) -> dict[str, Any]:
    root = root_from(args); existing = read_jsonl(evidence_path(root))
    imported = [r for r in existing if r.get("profile_id") == args.profile_id and r.get("status") == "imported-prior-pending-verification"]
    if not imported: raise UserError(f"no pending imported prior: {args.profile_id}")
    result = normalize_outcome(object_arg(args.result, "result"))
    validate_public_value(result)
    floor = load_policy(root)["quality_floor"]
    passed = all_gates_pass(result) and (metric(result, "quality_score") or -1) >= floor
    if args.comparison_run_id:
        comparisons = [r for r in existing if r.get("run_id") == args.comparison_run_id
                       and r.get("profile_id") != args.profile_id and all_gates_pass(r)
                       and (metric(r, "quality_score") or -1) >= floor
                       and not is_stale(r, load_policy(root))
                       and r.get("profile", {}).get("host") == imported[-1]["profile"].get("host")
                       and r.get("profile", {}).get("provider") == imported[-1]["profile"].get("provider")
                       and task_signature_key(r) == task_signature_key(imported[-1])]
        if not comparisons: raise UserError("comparison run must reference passing evidence for a different comparable profile")
    imported_requires_comparison = any(r.get("comparison_required") for r in imported)
    if passed and not args.comparison_run_id and (args.validation_strength == "weak" or imported_requires_comparison):
        status = "comparison-required"
    elif passed:
        status = "locally-verified"
    else:
        status = "quarantined"
    verification = {**result, "schema": "ultra-delegation-evidence-v1", "created_at": now(),
                    "profile": imported[-1]["profile"], "profile_id": args.profile_id,
                    "task_signature": imported[-1].get("task_signature", {}),
                    "imported_provenance_hash": imported[-1].get("provenance_hash"),
                    "status": status, "validation_strength": args.validation_strength,
                    "comparison_run_id": args.comparison_run_id}
    append_jsonl(evidence_path(root), verification)
    if status == "quarantined":
        raw = read_json(policy_path(root), {})
        quarantined = list(raw.get("quarantined_imports", []))
        if args.profile_id not in quarantined: quarantined.append(args.profile_id)
        raw["quarantined_imports"] = quarantined
        write_json(policy_path(root), raw)
    return {"profile_id": args.profile_id, "status": status,
            "next_action": "trigger host-native bakeoff" if status == "quarantined" else "compare one eligible alternative" if status == "comparison-required" else "use as locally verified"}


def safe_child(base: Path, child: str) -> Path:
    target = (base / child).resolve()
    if base.resolve() not in target.parents: raise UserError("unsafe isolation path")
    return target


def cmd_isolation(args: argparse.Namespace) -> dict[str, Any]:
    root = root_from(args); base = root / "runs" / "isolation"; target = safe_child(base, args.name)
    if args.isolation_action == "prepare":
        if target.exists(): raise UserError(f"isolation already exists: {target}")
        target.mkdir(parents=True); write_json(target / "manifest.json", {"created_at": now(), "mode": args.mode, "managed_by": "ultra-delegation"})
        return {"prepared": str(target), "mode": args.mode, "note": "no worktree or commands were executed"}
    manifest = target / "manifest.json"
    if not manifest.exists() or read_json(manifest).get("managed_by") != "ultra-delegation": raise UserError("refusing cleanup without managed manifest")
    shutil.rmtree(target); return {"cleaned": str(target)}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--root", help=".ultra-delegation directory (default: cwd/.ultra-delegation)")
    subs = p.add_subparsers(dest="command", required=True)
    def sub(name: str): return subs.add_parser(name)
    x = sub("init"); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_init)
    x = sub("validate"); x.set_defaults(func=cmd_validate)
    g = sub("guard"); gs = g.add_subparsers(dest="guard_action", required=True)
    x = gs.add_parser("evaluate"); x.add_argument("--snapshot", required=True); x.add_argument("--run-id"); x.add_argument("--write", action="store_true"); x.set_defaults(func=cmd_guard_evaluate)
    x = gs.add_parser("checkpoint"); x.add_argument("--run-id", required=True); x.add_argument("--summary", required=True); x.add_argument("--write", action="store_true"); x.set_defaults(func=cmd_guard_checkpoint)
    x = sub("profile-id"); x.add_argument("profile"); x.set_defaults(func=lambda a: {"profile_id": profile_id(object_arg(a.profile, "profile"))})
    x = sub("doctor"); x.add_argument("--context", default="{}"); x.set_defaults(func=cmd_doctor)
    x = sub("rank"); x.add_argument("--context", required=True); x.add_argument("--task", required=True); x.add_argument("--candidates", required=True); x.add_argument("--records"); x.set_defaults(func=cmd_rank)
    e = sub("experiment"); es = e.add_subparsers(dest="experiment_action", required=True); x = es.add_parser("score"); x.add_argument("--context", required=True); x.add_argument("experiment"); x.set_defaults(func=cmd_experiment_score)
    x = sub("record"); x.add_argument("record"); x.set_defaults(func=cmd_record)
    r = sub("report"); rs = r.add_subparsers(dest="report_kind", required=True)
    for name in ("run", "project"):
        x = rs.add_parser(name); x.add_argument("--run-id", required=name == "run"); x.add_argument("--records"); x.add_argument("--write", action="store_true"); x.set_defaults(func=cmd_report)
    c = sub("catalog"); cs = c.add_subparsers(dest="catalog_action", required=True)
    x = cs.add_parser("promote"); x.add_argument("profile_id"); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_catalog_promote)
    x = cs.add_parser("list"); x.set_defaults(func=cmd_catalog_list)
    x = cs.add_parser("report"); x.set_defaults(func=cmd_catalog_report)
    x = sub("export"); x.add_argument("--records"); x.add_argument("--output", required=True); x.set_defaults(func=cmd_export)
    x = sub("import"); x.add_argument("--input", required=True); x.add_argument("--task", required=True); x.add_argument("--context", required=True); mode = x.add_mutually_exclusive_group(required=True); mode.add_argument("--dry-run", action="store_true"); mode.add_argument("--apply", action="store_true"); x.set_defaults(func=cmd_import)
    x = sub("verify-import"); x.add_argument("profile_id"); x.add_argument("--result", required=True); x.add_argument("--validation-strength", choices=("strong", "weak"), required=True); x.add_argument("--comparison-run-id"); x.set_defaults(func=cmd_verify_import)
    i = sub("isolation"); ins = i.add_subparsers(dest="isolation_action", required=True)
    x = ins.add_parser("prepare"); x.add_argument("name"); x.add_argument("--mode", choices=("patch-proposal", "temporary-copy"), default="patch-proposal"); x.set_defaults(func=cmd_isolation)
    x = ins.add_parser("cleanup"); x.add_argument("name"); x.set_defaults(func=cmd_isolation)
    return p


def main() -> int:
    try:
        args = parser().parse_args(); result = args.func(args)
        if isinstance(result, dict) and "skill_release" not in result: result = {"skill_release": RELEASE, **result}
        print(json.dumps(result, indent=2, sort_keys=True)); return 0
    except (UserError, ValueError, TypeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 2
    except OSError as exc:
        print(f"filesystem error: {exc}", file=sys.stderr); return 3


if __name__ == "__main__": raise SystemExit(main())
