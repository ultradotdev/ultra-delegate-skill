"""Conservative local-inference admission, monitoring decisions, and process lease.

No model, server, subprocess, or network is invoked. Hosts supply measured snapshots
and perform scoped cancellation. A passing decision is not proof of hard enforcement.

evaluate_local(profile, context, policy): profile.execution_location must be remote
or local. For local execution context.local_resources contains observed_at (Unix
seconds), ram_total_bytes, ram_available_bytes, memory_pressure ('normal'),
active_local_requests, existing_model_processes (count), unified_memory (boolean),
and capabilities booleans: context_limit, output_limit, timeout, monitoring,
scoped_cancel. footprint contains runtime, model_revision, quantization,
context_tokens, weights_bytes, cache_bytes, overhead_bytes, and optionally
vram_bytes. Discrete GPU use requires gpu_kind='discrete', vram_total_bytes and
vram_available_bytes; otherwise gpu_kind='cpu' or 'unified'. context.now optionally
supplies an evaluation Unix timestamp for reproducible testing. local_authorized
permits one-task use even when disabled/ask; exclusions still win. local_run_state
must be retained by the host across dispatches. monitor_local returns that state
and a cancel_owned_request decision; the host must execute cancellation.

LocalLease is a process-held OS file lock, shared across projects. Keep the object
alive throughout owned request execution. Kernel lock release handles crashes;
expiry alone never steals a live lease. Release requires the exact owner token.
"""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from pathlib import Path

GIB = 1024 ** 3
DEFAULT_LOCAL_POLICY = {
    "mode": "disabled", "excluded_models": [], "allowed_models": None,
    "ram_reserve_ratio": .25, "ram_reserve_bytes": 4 * GIB,
    "vram_reserve_ratio": .20, "vram_reserve_bytes": GIB,
    "max_context_tokens": 8192, "max_output_tokens": 2048,
    "max_duration_seconds": 300, "max_attempts": 1,
    "max_snapshot_age_seconds": 10, "max_concurrent_requests": 1,
}
CAPABILITIES = ("context_limit", "output_limit", "timeout", "monitoring", "scoped_cancel")


def _number(value, minimum=0):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= minimum)


def _result(status, reason, **extra):
    return {"eligible": status in {"eligible", "remote"}, "status": status,
            "reason": reason, **extra}


def evaluate_local(profile, context, policy):
    """Evaluate a fresh snapshot without mutation; fail closed on missing evidence."""
    if not all(isinstance(item, dict) for item in (profile, context, policy)):
        return _result("invalid-policy", "Profile, context and policy must be objects")
    location = profile.get("execution_location", "unknown")
    if location == "remote":
        return _result("remote", "Remote execution does not consume local inference resources")
    if location != "local":
        return _result("unknown-location", "Execution location has not been established")
    supplied = policy.get("local_execution", {})
    if not isinstance(supplied, dict):
        return _result("invalid-policy", "local_execution must be an object")
    config = {**DEFAULT_LOCAL_POLICY, **supplied}
    identity = f"{profile.get('provider', '')}/{profile.get('model_revision') or profile.get('model', '')}"
    if config["mode"] not in ("disabled", "ask", "enabled"):
        return _result("invalid-policy", "Invalid local execution mode")
    for key in ("excluded_models", "allowed_models"):
        entries = config[key]
        if key == "allowed_models" and entries is None:
            continue
        if not isinstance(entries, list) or not all(isinstance(x, str) and "/" in x and "*" not in x for x in entries):
            return _result("invalid-policy", "Model controls require exact provider/model identities")
    if identity in config["excluded_models"]:
        return _result("excluded-by-policy", "Exact model identity is excluded")
    if config["allowed_models"] is not None and identity not in config["allowed_models"]:
        return _result("excluded-by-policy", "Exact model identity is not allowlisted")
    if config["mode"] != "enabled" and context.get("local_authorized") is not True:
        return _result("excluded-by-policy", "Explicit local execution authorization is required")
    run_state = context.get("local_run_state", {})
    if not isinstance(run_state, dict):
        return _result("invalid-policy", "Run state must be an object")
    if run_state.get("local_dispatch_stopped"):
        return _result("resource-aborted", "Further local dispatch is stopped for this run")
    for key in ("ram_reserve_ratio", "vram_reserve_ratio"):
        if not _number(config[key]) or config[key] > 1:
            return _result("invalid-policy", "Reserve ratios must be between zero and one")
    for key in ("ram_reserve_bytes", "vram_reserve_bytes", "max_context_tokens",
                "max_output_tokens", "max_duration_seconds", "max_snapshot_age_seconds"):
        if not _number(config[key], 1):
            return _result("invalid-policy", f"Invalid {key}")
    if (type(config["max_attempts"]) is not int or config["max_attempts"] != 1
            or type(config["max_concurrent_requests"]) is not int or config["max_concurrent_requests"] != 1):
        return _result("invalid-policy", "Local execution requires one attempt and one concurrent request")
    if context.get("local_attempt", 1) != 1:
        return _result("resource-aborted", "Local retries are disabled")
    snapshot = context.get("local_resources", {})
    if not isinstance(snapshot, dict):
        return _result("unknown-footprint", "Resource snapshot must be an object")
    observed = snapshot.get("observed_at")
    current = context.get("now", time.time())
    if not _number(current) or not _number(observed) or not 0 <= current - observed <= config["max_snapshot_age_seconds"]:
        return _result("stale-observation", "Fresh resource observations are required")
    capabilities = snapshot.get("capabilities", {})
    if not isinstance(capabilities, dict) or not all(capabilities.get(key) is True for key in CAPABILITIES):
        return _result("unsupported-controls", "Bounds, timeout, monitoring and scoped cancellation are required")
    if snapshot.get("memory_pressure") != "normal":
        return _result("insufficient-headroom", "Memory pressure is elevated or unavailable")
    if not _number(snapshot.get("active_local_requests")) or not _number(snapshot.get("existing_model_processes")):
        return _result("unknown-footprint", "Existing model processes and requests must be observed")
    # A monitor may subtract exactly its own known request; admission never does.
    active = snapshot["active_local_requests"] - (1 if context.get("monitoring_owned_request") is True else 0)
    if active > 0:
        return _result("concurrency-busy", "Another local inference request is active")
    footprint = snapshot.get("footprint", {})
    if not isinstance(footprint, dict):
        return _result("unknown-footprint", "Runtime footprint must be an object")
    if (not footprint.get("runtime") or not footprint.get("quantization")
            or footprint.get("model_revision") != profile.get("model_revision", profile.get("model"))
            or not all(_number(footprint.get(k)) for k in ("weights_bytes", "cache_bytes", "overhead_bytes"))
            or footprint.get("weights_bytes", 0) <= 0 or footprint.get("overhead_bytes", 0) <= 0):
        return _result("unknown-footprint", "Runtime-specific weights, cache and overhead estimate is required")
    context_tokens = context.get("context_tokens", config["max_context_tokens"])
    output_tokens = context.get("output_tokens", config["max_output_tokens"])
    if (not _number(context_tokens, 1) or context_tokens > config["max_context_tokens"]
            or not _number(output_tokens, 1) or output_tokens > config["max_output_tokens"]
            or not _number(footprint.get("context_tokens"), context_tokens)):
        return _result("unsupported-controls", "Requested token limits exceed policy or estimated footprint")
    total, available = snapshot.get("ram_total_bytes"), snapshot.get("ram_available_bytes")
    if not _number(total, 1) or not _number(available) or available > total:
        return _result("insufficient-headroom", "System memory availability is unknown or invalid")
    required = sum(footprint[k] for k in ("weights_bytes", "cache_bytes", "overhead_bytes"))
    reserve = max(total * config["ram_reserve_ratio"], config["ram_reserve_bytes"])
    incremental = 0 if context.get("monitoring_owned_request") is True else required
    if available - incremental < reserve:
        return _result("insufficient-headroom", "Model would consume reserved system memory")
    kind = snapshot.get("gpu_kind")
    if kind not in {"cpu", "unified", "discrete"} or not isinstance(snapshot.get("unified_memory"), bool):
        return _result("unknown-footprint", "GPU memory topology must be known")
    if (kind == "unified") != snapshot["unified_memory"]:
        return _result("unknown-footprint", "Conflicting memory topology")
    if kind == "discrete":
        vt, va, needed = snapshot.get("vram_total_bytes"), snapshot.get("vram_available_bytes"), footprint.get("vram_bytes")
        if not _number(vt, 1) or not _number(va) or va > vt or not _number(needed, 1):
            return _result("unknown-footprint", "Discrete GPU availability and footprint are required")
        incremental_gpu = 0 if context.get("monitoring_owned_request") is True else needed
        if va - incremental_gpu < max(vt * config["vram_reserve_ratio"], config["vram_reserve_bytes"]):
            return _result("insufficient-headroom", "Model would consume reserved GPU memory")
    return _result("eligible", "Preflight passed; acquire lease and enforce runtime limits before dispatch",
                   limits={"context_tokens": context_tokens, "output_tokens": output_tokens,
                           "duration_seconds": config["max_duration_seconds"], "attempts": 1},
                   requires_lease=True)


def monitor_local(profile, context, policy, state):
    """Return updated state and owned-request cancellation intent; never cancel here."""
    state = dict(state)
    observation = {**context, "local_run_state": state, "monitoring_owned_request": True}
    result = evaluate_local(profile, observation, policy)
    elapsed = context.get("elapsed_seconds")
    limit = {**DEFAULT_LOCAL_POLICY, **policy.get("local_execution", {})}["max_duration_seconds"]
    if not _number(elapsed) or elapsed >= limit or not result["eligible"]:
        state.update(local_dispatch_stopped=True, failure_kind="resource", status="resource-aborted")
        return {**_result("resource-aborted", "Runtime resource or time bound reached"),
                "cancel_owned_request": True, "state": state, "cause": result["status"]}
    return {**result, "cancel_owned_request": False, "state": state}


class LocalLease:
    """Exclusive user-scoped lease. Linux/macOS flock releases on process death.

    File remains after release intentionally: unlinking a locked file creates a
    second inode and permits two owners. Metadata is informational, never authority.
    """
    def __init__(self, directory=None):
        self.directory = Path(directory or os.environ.get("ULTRA_DELEGATION_HOME", Path.home() / ".ultra-delegation"))
        self._fd = None
        self.owner_token = None

    def acquire(self):
        import fcntl
        if self._fd is not None:
            raise ValueError("Lease already held by this object")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.directory / "local-execution.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return None
        except BaseException:
            os.close(fd)
            raise
        token = uuid.uuid4().hex
        try:
            data = json.dumps({"owner_token": token, "pid": os.getpid(), "acquired_at": time.time()}).encode()
            os.ftruncate(fd, 0)
            os.write(fd, data)
            os.fsync(fd)
        except BaseException:
            os.close(fd)
            raise
        self._fd, self.owner_token = fd, token
        return token

    def release(self, owner_token):
        if self._fd is None or owner_token != self.owner_token:
            raise ValueError("Only the active lease owner may release it")
        os.close(self._fd)
        self._fd, self.owner_token = None, None

    def __enter__(self):
        if self.acquire() is None:
            raise RuntimeError("concurrency-busy")
        return self

    def __exit__(self, *_):
        self.release(self.owner_token)
