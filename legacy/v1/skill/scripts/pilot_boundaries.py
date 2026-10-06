"""Structured, auditable task boundaries for pilot worker contracts."""
from __future__ import annotations

import copy
import json


_CATEGORIES = (
    "allowed_changes",
    "allowed_actions",
    "protected_behavior",
    "protected_data",
    "coordinator_decisions",
)


def _core():
    # pilot_core delegates packet validation here, so keep this import lazy.
    import pilot_core
    return pilot_core


def _category(value, limit):
    core = _core()
    core.fields(value, {"items", "not_applicable"})
    items = value["items"]
    explanation = value["not_applicable"]
    core.require(isinstance(items, list) and len(items) <= limit, "invalid-task-boundaries")
    for item in items:
        core.prose(item)
    if explanation is not None:
        core.prose(explanation)
    core.require(bool(items) != (explanation is not None), "invalid-task-boundaries")


def validate(value):
    """Return a defensive, deeply validated copy of one boundary contract."""
    core = _core()
    result = copy.deepcopy(value)
    core.fields(result, set(_CATEGORIES) | {
        "security_requirements", "authorization", "security_sensitive",
    })
    for name in _CATEGORIES:
        _category(result[name], 24)

    security = result["security_requirements"]
    core.fields(security, {"items", "not_applicable"})
    items = security["items"]
    explanation = security["not_applicable"]
    core.require(isinstance(items, list) and len(items) <= 12, "invalid-task-boundaries")
    seen = set()
    for item in items:
        core.fields(item, {"id", "requirement", "mandatory"})
        core.label(item["id"])
        core.prose(item["requirement"])
        core.require(type(item["mandatory"]) is bool, "invalid-task-boundaries")
        core.require(item["id"] not in seen, "invalid-task-boundaries")
        seen.add(item["id"])
    if explanation is not None:
        core.prose(explanation)
    core.require(bool(items) != (explanation is not None), "invalid-task-boundaries")

    core.require(result["authorization"] in {"granted", "unknown"}, "invalid-task-boundaries")
    core.require(type(result["security_sensitive"]) is bool, "invalid-task-boundaries")
    return result


def contract_hash(value):
    """Hash exactly the validated boundary object written to a worker contract."""
    return _core().digest(validate(value))


def worker_contract(value):
    """Render an inspectable Markdown contract containing exact JSON and its hash."""
    contract = validate(value)
    digest = _core().digest(contract)
    encoded = json.dumps(contract, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return ("# Worker contract\n\n"
            f"Contract hash: `sha256:{digest}`\n\n"
            "```json\n" + encoded + "\n```\n")


def example():
    """Return an explicit synthetic patch-and-test contract for examples and tests."""
    return validate({
        "allowed_changes": {
            "items": [
                "Modify the synthetic parser implementation within its assigned module.",
                "Add or update focused tests for the synthetic parser patch.",
            ],
            "not_applicable": None,
        },
        "allowed_actions": {
            "items": [
                "Read the assigned synthetic parser module and its focused tests.",
                "Run the focused parser tests locally without external effects.",
            ],
            "not_applicable": None,
        },
        "protected_behavior": {
            "items": ["Preserve the parser's documented public API and unrelated behavior."],
            "not_applicable": None,
        },
        "protected_data": {
            "items": [],
            "not_applicable": "The synthetic example contains no user, production, or credential data.",
        },
        "coordinator_decisions": {
            "items": ["The coordinator decides whether to accept, dispatch, or publish the patch."],
            "not_applicable": None,
        },
        "security_requirements": {
            "items": [{
                "id": "no-external-effects",
                "requirement": "Do not use networks, external services, credentials, or external writes.",
                "mandatory": True,
            }],
            "not_applicable": None,
        },
        "authorization": "granted",
        "security_sensitive": False,
    })
