"""Bounded public evidence contracts. No I/O, host execution, or network access.

Normalization is a projection for legacy reads; validation rejects unknown fields
on new writes. Neither function modifies its argument or rewrites old evidence.
Secret detection is defense in depth, not a promise to identify arbitrary secrets.
"""
from __future__ import annotations

import json
import math
import re

MAX_BYTES = 65536
MAX_STRING = 4096
MAX_ITEMS = 128
SECRET = re.compile(r"(?:data:[^\s,;]+[;,]|-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk-(?:proj-)?|gh[pousr]_|github_pat_|AKIA)[A-Za-z0-9_\-]{16,}|\bBearer\s+[A-Za-z0-9._\-]{16,}|(?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*\S{6,})", re.I)
BASE64 = re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{256,}={0,2}(?![A-Za-z0-9+/])")
FORBIDDEN = {"source", "source_code", "prompt", "rendered_prompt", "raw_output", "image", "image_url", "screenshot", "base64", "secret", "credential", "credentials", "password", "api_key", "access_token", "reasoning_trace"}

def validate_public_value(value, label="value", _depth=0):
    """Validate bounded JSON and reject recognizable secrets/embedded media.

    This is content validation only; callers must also apply their own field
    allowlist (for example the handoff contract) and path validation.
    """
    if _depth > 8:
        raise ValueError(f"{label}: nesting too deep")
    if isinstance(value, dict):
        if len(value) > MAX_ITEMS:
            raise ValueError(f"{label}: too many fields")
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 128 or key.lower() in FORBIDDEN:
                raise ValueError(f"{label}: forbidden or invalid field")
            validate_public_value(item, f"{label}.{key}", _depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_ITEMS:
            raise ValueError(f"{label}: too many items")
        for item in value:
            validate_public_value(item, label, _depth + 1)
    elif isinstance(value, str):
        if len(value) > MAX_STRING or SECRET.search(value) or BASE64.search(value):
            raise ValueError(f"{label}: oversized or sensitive content")
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label}: numeric values must be finite")
    elif value is not None and not isinstance(value, (bool, int)):
        raise ValueError(f"{label}: must contain only JSON values")
    if _depth == 0 and len(json.dumps(value, allow_nan=False).encode()) > MAX_BYTES:
        raise ValueError(f"{label}: exceeds {MAX_BYTES} bytes")
    return value

# A schema leaf names a type; dicts and one-item lists define recursive fields.
TEXT = "text"
NUMBER = "number"
COUNT = "count"
BOOL = "bool"
SCORE = "score"
CONFIDENCE = "confidence"
THINKING = {"normalized": TEXT, "native": "native"}
PROFILE = {key: TEXT for key in ("task_family", "provider", "model", "model_revision", "host", "runtime", "prompt_profile", "prompt_profile_hash", "prompt_hash", "tool_policy", "tool_policy_version", "execution_location", "endpoint_classification")}
PROFILE["thinking"] = THINKING
TASK = {key: TEXT for key in ("task_family", "operation", "language", "language_version", "framework", "framework_major", "framework_version", "risk", "coupling", "validation", "validation_type")}
TASK["tools"] = "tools"
GATE = {"id": TEXT, "name": TEXT, "mandatory": BOOL, "passed": BOOL, "kind": TEXT}
METRICS = {key: NUMBER for key in ("cost_usd", "latency_ms", "total_latency_ms", "time_to_first_token_ms", "tokens_per_second", "throughput", "time_to_accepted_ms")}
METRICS.update({key: COUNT for key in ("tool_turns", "retries", "escalations", "regressions")})
METRICS["quality_score"] = SCORE
METRICS["baseline_cost_usd"] = NUMBER
USAGE = {key: COUNT for key in ("input_tokens", "output_tokens", "thinking_tokens", "cached_input_tokens", "total_tokens")}
USAGE.update({"thinking_in_output": BOOL, "output_includes_thinking": BOOL})
AGGREGATE = {key: NUMBER for key in ("quality_stddev", "mean_cost_usd", "mean_latency_ms")}
AGGREGATE.update({key: SCORE for key in ("mean_quality", "conservative_quality")})
AGGREGATE["conservative_quality"] = "conservative_score"
AGGREGATE.update({key: COUNT for key in ("evidence_count", "pass_count")})
AGGREGATE["gate_reliability"] = "ratio"
PROMOTION = {"status": TEXT, "method": TEXT, "confidence": CONFIDENCE, "confirmation_required": BOOL}
LEARNING_FIELDS = {key: TEXT for key in ("schema", "catalog_id", "created_at", "fresh_at", "profile_id", "promotion", "promotion_method", "evaluation_methodology", "provenance_hash", "content_hash", "source_promotion")}
LEARNING_FIELDS.update({"profile": PROFILE, "task_signature": TASK, "aggregate": AGGREGATE, "source_passed_gates": BOOL, "confidence": CONFIDENCE, "moving_alias": BOOL})
OUTCOME = {key: TEXT for key in ("id", "schema", "run_id", "created_at", "fresh_at", "profile_id", "status", "promotion_status", "provenance_hash", "imported_provenance_hash", "content_hash", "source_promotion", "validation_strength", "comparison_run_id", "baseline_revision", "isolation_mode", "prompt_hash", "cost_kind", "price_date", "failure_kind")}
OUTCOME.update({key: BOOL for key in ("accepted", "selected", "comparator", "experiment", "moving_alias", "imported_prior", "comparison_required", "source_passed_gates", "regression", "resource_failure")})
OUTCOME.update({"profile": PROFILE, "task_signature": TASK, "gates": [GATE], "metrics": METRICS, "usage": USAGE, "aggregate": AGGREGATE, "confidence": CONFIDENCE, "evaluator_confidence": CONFIDENCE, "selections_since_test": COUNT, "artifact_hashes": [TEXT], "comparison_record_ids": [TEXT]})
OUTCOME.update(METRICS)
OUTCOME.update({"verification_commands": [TEXT], "content_id": TEXT})
OUTCOME.update({key: TEXT for key in ("baseline_cost_kind", "baseline_source", "baseline_run_id", "baseline_profile_id", "baseline_price_date", "baseline_provenance")})
OUTCOME["local_execution"] = {"status": "local_status", "reason": TEXT, "failure_kind": TEXT,
    "local_dispatch_stopped": BOOL, "cancel_owned_request": BOOL}
RUN = {key: OUTCOME[key] for key in ("run_id", "created_at", "baseline_revision", "isolation_mode", "selected", "comparator", "experiment", "artifact_hashes")}
RUN["id"] = TEXT
QUALITY = {"score": SCORE, "quality_score": SCORE, "gates": [GATE], "accepted": BOOL, "evaluator_confidence": CONFIDENCE, "regressions": COUNT}
COST = {"usd": NUMBER, "cost_usd": NUMBER, "kind": TEXT, "cost_kind": TEXT, "price_date": TEXT, "usage": USAGE}
LEARNING = {key: OUTCOME[key] for key in ("status", "promotion_status", "confidence", "fresh_at", "moving_alias", "provenance_hash", "comparison_required", "selections_since_test")}
INPUT = {**OUTCOME, "run": RUN, "task": TASK, "quality": QUALITY, "performance": METRICS, "cost": COST, "learning": LEARNING}

def _project(value, spec, strict, label):
    if value is None or value == "unavailable":
        return None
    if isinstance(spec, dict):
        if not isinstance(value, dict):
            raise ValueError(f"{label}: must be an object")
        if strict and set(value) - set(spec):
            raise ValueError(f"{label}: unsupported fields: {', '.join(sorted(set(value) - set(spec)))}")
        return {k: _project(v, spec[k], strict, f"{label}.{k}") for k, v in value.items() if k in spec}
    if isinstance(spec, list):
        if not isinstance(value, list):
            raise ValueError(f"{label}: must be an array")
        return [_project(v, spec[0], strict, label) for v in value]
    if spec == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{label}: must be boolean")
    elif spec in {"number", "count", "score", "ratio", "conservative_score"}:
        minimum = -100 if spec == "conservative_score" else 0
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
            raise ValueError(f"{label}: must be finite and nonnegative")
        if spec == "count" and (not isinstance(value, int)):
            raise ValueError(f"{label}: must be an integer")
        if spec in {"score", "conservative_score"} and value > 100 or spec == "ratio" and value > 1:
            raise ValueError(f"{label}: out of range")
    elif spec == "confidence":
        if isinstance(value, bool) or not (isinstance(value, str) and value in {"low", "moderate", "medium", "high"} or isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 1):
            raise ValueError(f"{label}: invalid confidence")
    elif spec == "local_status":
        if value not in {"excluded-by-policy", "insufficient-headroom", "unknown-footprint", "concurrency-busy", "resource-aborted", "eligible", "unsupported-runtime", "unknown-location"}:
            raise ValueError(f"{label}: invalid local execution status")
    elif spec == "tools":
        if not isinstance(value, str) and not (isinstance(value, list) and all(isinstance(item, str) for item in value)):
            raise ValueError(f"{label}: requires a tool name or list of tool names")
    elif spec == "native":
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError(f"{label}: use an exact native string or integer")
    elif not isinstance(value, str):
        raise ValueError(f"{label}: must be a string")
    return value

def _normalize(record, strict):
    if not isinstance(record, dict):
        raise ValueError("outcome must be an object")
    projected = _project(record, INPUT, strict, "outcome")
    result = {key: value for key, value in projected.items() if key in OUTCOME}
    def assign(key, value):
        if key in result and result[key] != value:
            raise ValueError(f"conflicting outcome field: {key}")
        result[key] = value
    metrics = dict(result.get("metrics") or {})
    def metric(key, value):
        if key in metrics and metrics[key] != value:
            raise ValueError(f"conflicting metric: {key}")
        metrics[key] = value
    for key, value in (projected.get("run") or {}).items():
        assign("run_id" if key == "id" else key, value)
    if "task" in projected:
        assign("task_signature", projected["task"])
    for key, value in (projected.get("quality") or {}).items():
        if key in {"score", "quality_score", "regressions"}:
            metric("quality_score" if key == "score" else key, value)
        else:
            assign(key, value)
    for key, value in (projected.get("performance") or {}).items():
        metric(key, value)
    for key, value in (projected.get("cost") or {}).items():
        if key in {"usd", "cost_usd"}:
            metric("cost_usd", value)
        else:
            assign("cost_kind" if key == "kind" else key, value)
    for key, value in (projected.get("learning") or {}).items():
        assign(key, value)
    for key in METRICS:
        if key in result:
            metric(key, result.pop(key))
    if metrics:
        result["metrics"] = metrics
    validate_public_value(result, "outcome")
    return result

def normalize_outcome(record):
    """Project old records to safe fields; invalid retained values raise ValueError."""
    return _normalize(record, False)

def validate_outcome(record):
    """Validate a new observation and return its canonical flat representation."""
    result = _normalize(record, True)
    profile = result.get("profile") or {}
    required = {"task_family", "provider", "model", "host", "thinking", "prompt_profile", "tool_policy"}
    if any(not profile.get(key) for key in required):
        raise ValueError("outcome.profile missing required identity fields")
    thinking = profile["thinking"]
    if thinking.get("normalized") not in {"off", "low", "medium", "high", "xhigh", "max", "custom"} or thinking.get("native") is None:
        raise ValueError("outcome.profile.thinking requires normalized and native settings")
    if not isinstance(result.get("accepted"), bool):
        raise ValueError("outcome.accepted is required")
    if result.get("failure_kind") == "resource":
        if result["accepted"] or (result.get("local_execution") or {}).get("status") != "resource-aborted":
            raise ValueError("resource event must be rejected with resource-aborted status")
        if (result.get("metrics") or {}).get("quality_score") is not None or result.get("gates"):
            raise ValueError("resource event must not fabricate quality scores or gates")
        return result
    gates = result.get("gates") or []
    if any(not isinstance(gate, dict) or not isinstance(gate.get("passed"), bool) or ("mandatory" in gate and not isinstance(gate["mandatory"], bool)) for gate in gates):
        raise ValueError("every gate requires a boolean passed result")
    if not any(gate.get("mandatory", True) for gate in gates):
        raise ValueError("outcome requires at least one mandatory gate")
    if result["accepted"] and any(not gate["passed"] for gate in gates if gate.get("mandatory", True)):
        raise ValueError("accepted outcome has failed mandatory gates")
    if (result.get("metrics") or {}).get("quality_score") is None:
        raise ValueError("outcome requires quality_score")
    if result.get("cost_kind") not in {None, "measured", "estimated", "unavailable"}:
        raise ValueError("invalid cost_kind")
    return result

def sanitize_learning(record):
    """Export only generalized evidence fields; no arbitrary nested metadata."""
    result = _project(record, LEARNING_FIELDS, False, "learning")
    validate_public_value(result, "learning")
    return result
