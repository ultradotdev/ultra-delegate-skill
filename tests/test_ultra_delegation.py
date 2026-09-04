"""Dependency-free behavior tests for the Ultra Delegation helper.

The suite intentionally imports the skill helper directly: no provider, network, or
host delegation interface is exercised.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPOSITORY = Path(__file__).resolve().parents[1]
HELPER = REPOSITORY / ".agents/skills/ultra-delegation/scripts/ultra_delegation.py"
SPEC = importlib.util.spec_from_file_location("ultra_delegation", HELPER)
ud = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(ud)


def profile(model="gpt-5.5", thinking="medium", native="medium"):
    return {
        "task_family": "python-edit",
        "provider": "openai",
        "model": model,
        "model_revision": model,
        "host": "codex",
        "execution_location": "remote",
        "thinking": {"normalized": thinking, "native": native},
        "prompt_profile": "prompt-v1",
        "tool_policy": "read-write-v1",
    }


def task():
    return {
        "task_family": "python-edit", "operation": "refactor", "language": "python",
        "framework": "stdlib", "framework_major": "3", "risk": "low",
        "coupling": "low", "validation": "unittest", "tools": "shell",
    }


def result(score=85, cost=1.0, latency=100, accepted=True, **extra):
    return {
        "accepted": accepted,
        "gates": [{"mandatory": True, "passed": accepted}],
        "metrics": {"quality_score": score, "cost_usd": cost, "latency_ms": latency},
        **extra,
    }


def record(p, score=85, cost=1.0, run_id="run-1", **extra):
    return {
        "profile": p, "task_signature": task(), "run_id": run_id,
        "accepted": True, "gates": [{"mandatory": True, "passed": True}],
        "metrics": {"quality_score": score, "cost_usd": cost, "latency_ms": 100},
        **extra,
    }


class UltraDelegationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / ".ultra-delegation"
        ud.cmd_init(argparse.Namespace(root=str(self.root), force=False))
        self.context = {"provider": "openai", "host": "codex", "available_models": ["gpt-5.5", "gpt-5.6"],
                        "thinking_settings": {model: ["low", "medium", "high"] for model in ("gpt-5.5", "gpt-5.6")}}

    def call_record(self, item):
        return ud.cmd_record(argparse.Namespace(root=str(self.root), record=json.dumps(item)))

    def score_experiment(self, experiment):
        return ud.cmd_experiment_score(argparse.Namespace(
            root=str(self.root), context=json.dumps(self.context),
            experiment=json.dumps(experiment),
        ))

    def evaluate_guard(self, snapshot, write=False, run_id=None):
        snapshot = {"observed_at": ud.now(), "telemetry": {"availability": "measured"}, **snapshot}
        return ud.cmd_guard_evaluate(argparse.Namespace(
            root=str(self.root), snapshot=json.dumps(snapshot), write=write, run_id=run_id,
        ))

    def test_profile_identity_is_stable_and_thinking_sensitive(self):
        first = profile()
        self.assertEqual(ud.profile_id(first), ud.profile_id(dict(reversed(list(first.items())))))
        self.assertNotEqual(ud.profile_id(first), ud.profile_id(profile(thinking="high", native="high")))
        with self.assertRaises(ud.UserError):
            ud.profile_id({"task_family": "missing-fields"})

    def test_nested_policy_overrides_are_loaded_and_validation_rejects_phase_two(self):
        ud.write_json(ud.policy_path(self.root), {
            "routing": {"quality_floor": 91, "global_catalog": "disabled"},
            "experiments": {"minimum_comparable_outcomes": 4},
            "promotion": {"moving_alias_stale_days": 11},
        })
        loaded = ud.load_policy(self.root)
        self.assertEqual(91, loaded["quality_floor"])
        self.assertFalse(loaded["global_catalog"])
        self.assertEqual(4, loaded["minimum_comparable_outcomes"])
        self.assertEqual(11, loaded["moving_alias_retest_days"])
        ud.write_json(ud.policy_path(self.root), {"routing": {"external_adapters": "enabled"}})
        checked = ud.cmd_validate(argparse.Namespace(root=str(self.root)))
        self.assertFalse(checked["valid"])
        self.assertIn("Phase 1 requires external_adapters=disabled", checked["errors"])

    def test_context_guard_policy_is_backward_compatible_and_validated(self):
        ud.write_json(ud.policy_path(self.root), {"routing": {"quality_floor": 85}})
        loaded = ud.load_policy(self.root)
        self.assertEqual(.70, loaded["context_guard"]["elevated_ratio"])
        self.assertTrue(ud.cmd_validate(argparse.Namespace(root=str(self.root)))["valid"])
        ud.write_json(ud.policy_path(self.root), {"context_guard": {"high_ratio": .95, "critical_ratio": .90}})
        checked = ud.cmd_validate(argparse.Namespace(root=str(self.root)))
        self.assertFalse(checked["valid"])
        self.assertIn("context_guard ratios must be ordered elevated <= high <= critical", checked["errors"])

    def test_context_guard_exact_utilization_boundaries(self):
        expectations = ((699, "healthy"), (700, "elevated"), (819, "elevated"),
                        (820, "high"), (899, "high"), (900, "critical"))
        for used, expected in expectations:
            with self.subTest(used=used):
                result = self.evaluate_guard({
                    "telemetry": {"availability": "measured"},
                    "context": {"used_tokens": used, "window_tokens": 1000},
                })
                self.assertEqual(expected, result["risk"])
        high = self.evaluate_guard({"context": {"used_tokens": 820, "window_tokens": 1000}})
        self.assertTrue(high["checkpoint_required"])
        self.assertFalse(high["delegation_allowed"])
        resumed = self.evaluate_guard({
            "context": {"used_tokens": 820, "window_tokens": 1000},
            "checkpoint": {"completed_for_snapshot": high["snapshot_id"]},
        })
        self.assertTrue(resumed["delegation_allowed"])

    def test_context_guard_detects_observed_compaction_regression(self):
        result = self.evaluate_guard({
            "observed_at": ud.now(),
            "telemetry": {"availability": "measured"},
            "context": {"used_tokens": 301766, "window_tokens": 258400},
            "compactions": [{
                "timestamp": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=30)).isoformat(),
                "before_tokens": 302000,
                "after_tokens": 301766,
            }],
            "active_workers": 2,
        })
        self.assertEqual("critical", result["risk"])
        self.assertEqual("stop_and_handoff", result["required_action"])
        self.assertFalse(result["delegation_allowed"])
        self.assertEqual(2, result["active_workers"])
        self.assertTrue(any("post-compaction" in reason for reason in result["reasons"]))

    def test_context_guard_detects_repeated_compactions_that_stay_high(self):
        result = self.evaluate_guard({
            "observed_at": ud.now(),
            "context": {"used_tokens": 850, "window_tokens": 1000},
            "compactions": [
                {"timestamp": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=6)).isoformat(), "before_tokens": 1100, "after_tokens": 850},
                {"timestamp": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)).isoformat(), "before_tokens": 1080, "after_tokens": 840},
            ],
        })
        self.assertEqual("critical", result["risk"])
        self.assertTrue(any("2 compactions" in reason for reason in result["reasons"]))

    def test_context_guard_unknown_telemetry_uses_milestone_and_unattended_fallbacks(self):
        ordinary = self.evaluate_guard({
            "telemetry": {"availability": "unavailable"},
            "history": {"attachment_count": 500, "serialized_bytes": 50_000_000, "task_age_minutes": 10000},
        })
        self.assertEqual("unknown", ordinary["risk"])
        self.assertTrue(ordinary["delegation_allowed"])
        self.assertFalse(ordinary["checkpoint_required"])
        milestone = self.evaluate_guard({
            "telemetry": {"availability": "unavailable"},
            "milestone": {"completed": True},
        })
        self.assertTrue(milestone["checkpoint_required"])
        unattended = self.evaluate_guard({
            "telemetry": {"availability": "unavailable"},
            "unattended": True,
            "checkpoint": {"minutes_since": 60},
        })
        self.assertTrue(unattended["checkpoint_required"])
        self.assertEqual("checkpoint_before_delegation", unattended["required_action"])

    def test_guard_checkpoint_writes_sanitized_deterministic_handoff(self):
        summary = {
            "objective": "Add context guardrails",
            "completed": ["Implemented evaluation"],
            "decisions": ["Stop at critical risk"],
            "remaining": ["Run validation"],
            "validation": ["python3 -m unittest"],
            "artifact_references": [{"label": "patch", "path": "artifacts/guard.patch", "hash": "abc123"}],
            "active_workers": ["worker-1 requested to return terse status"],
            "next_action": "Start a fresh task from this handoff.",
        }
        self.evaluate_guard({}, write=True, run_id="guard-run")
        with patch.object(ud, "now", return_value="2026-08-08T05:00:00+00:00"):
            result = ud.cmd_guard_checkpoint(argparse.Namespace(
                root=str(self.root), run_id="guard-run", summary=json.dumps(summary), write=True,
            ))
        markdown_path, json_path = map(Path, result["paths"])
        self.assertTrue(markdown_path.exists())
        envelope = json.loads(json_path.read_text())
        self.assertEqual(ud.RELEASE, envelope["skill_release"])
        self.assertEqual("requires_guard_reevaluation", envelope["delegation_state"])
        self.assertNotIn("critical_action", envelope)
        self.assertIn(f"Release: {ud.RELEASE}", markdown_path.read_text())
        with self.assertRaisesRegex(ValueError, "forbidden"):
            ud.validate_handoff({"objective": "unsafe", "completed": [], "raw_output": "private"})
        unsafe = {**summary, "next_action": "send sk-secret-value"}
        with self.assertRaisesRegex(ud.UserError, "possible secret"):
            ud.validate_handoff(unsafe)
        oversized = {**summary, "completed": ["x" * 4001]}
        with self.assertRaisesRegex(ValueError, "oversized|too large"):
            ud.validate_handoff(oversized)

    def test_written_guard_state_is_included_in_run_report(self):
        evaluated = self.evaluate_guard({
            "context": {"used_tokens": 90, "window_tokens": 100},
        }, write=True, run_id="guard-report")
        self.assertTrue(Path(evaluated["state_path"]).exists())
        report = ud.cmd_report(argparse.Namespace(
            root=str(self.root), records=None, report_kind="run", run_id="guard-report", write=False,
        ))
        self.assertEqual("critical", report["data"]["context_guard"]["latest_risk"])
        self.assertIn("## Context guard", report["markdown"])
        self.assertIn(f"Release: {ud.RELEASE}", report["markdown"])

    def test_rank_filters_external_provider_and_host_before_cost(self):
        cheap_external = profile("gpt-5.6")
        cheap_external["provider"] = "ollama"
        cheap_host = profile("gpt-5.6")
        cheap_host["host"] = "opencode"
        ranked = ud.cmd_rank(argparse.Namespace(
            root=str(self.root), context=json.dumps(self.context), task=json.dumps(task()),
            candidates=json.dumps([{"profile": cheap_external}, {"profile": cheap_host}, {"profile": profile()}]),
        ))["ranked"]
        self.assertTrue(ranked[0]["eligible"])
        self.assertEqual("provider outside current scope", ranked[-2]["reason"])
        self.assertEqual("host outside current scope", ranked[-1]["reason"])

    def test_rank_rejects_model_unavailable_in_current_host(self):
        ranked = ud.cmd_rank(argparse.Namespace(
            root=str(self.root), context=json.dumps(self.context), task=json.dumps(task()),
            candidates=json.dumps([{"profile": profile("gpt-5.999")}]),
        ))["ranked"]
        self.assertFalse(ranked[0]["eligible"])
        self.assertEqual("model unavailable", ranked[0]["reason"])

        moving_alias = profile("gpt-5.5")
        moving_alias["model_revision"] = "gpt-5.5-2026-07-01"
        alias_rank = ud.cmd_rank(argparse.Namespace(
            root=str(self.root), context=json.dumps(self.context), task=json.dumps(task()),
            candidates=json.dumps([{"profile": moving_alias}]),
        ))["ranked"]
        self.assertFalse(alias_rank[0]["eligible"])
        self.assertEqual("model unavailable", alias_rank[0]["reason"])

    def test_experiment_enforces_one_variable_and_promotes_half_cost_equivalence(self):
        a, b = profile("gpt-5.5"), profile("gpt-5.6")
        experiment = {"id": "exp-1", "variable": "model", "quality_floor": 80, "candidates": [
            {"id": "cheap", "profile": a, "result": result(85, .5, 100)},
            {"id": "expensive", "profile": b, "result": result(86, 1.0, 105)},
        ]}
        scored = self.score_experiment(experiment)
        self.assertEqual("cheap", scored["winner"])
        self.assertEqual("early-decisive", scored["promotion_status"])
        self.assertEqual("equivalent quality and latency at half cost", scored["early_decisive_reason"])
        b["thinking"] = {"normalized": "high", "native": "high"}
        with self.assertRaisesRegex(ud.UserError, "one-variable rule"):
            self.score_experiment(experiment)

    def test_experiment_rejects_non_variable_identity_changes(self):
        for key, changed_value in (("tool_policy", "read-only-v2"), ("provider", "ollama"), ("host", "opencode")):
            a, b = profile("gpt-5.5"), profile("gpt-5.6")
            a[key] = changed_value
            experiment = {"variable": "model", "candidates": [
                {"id": "a", "profile": a, "result": result()},
                {"id": "b", "profile": b, "result": result()},
            ]}
            with self.subTest(key=key), self.assertRaisesRegex(ud.UserError, key):
                self.score_experiment(experiment)

    def test_experiment_rejects_candidates_outside_current_provider(self):
        first, second = profile("local-a"), profile("local-b")
        for candidate in (first, second):
            candidate["provider"] = "ollama"
        experiment = {"variable": "model", "candidates": [
            {"id": "external-a", "profile": first, "result": result()},
            {"id": "external-b", "profile": second, "result": result()},
        ]}
        with self.assertRaisesRegex(ud.UserError, "provider outside current scope"):
            self.score_experiment(experiment)

    def test_early_decisive_only_passing_and_normal_promotion(self):
        one = {"variable": "thinking", "candidates": [
            {"id": "low", "profile": profile(thinking="low", native="low"), "result": result(70, .1)},
            {"id": "medium", "profile": profile(), "result": result(86, .2)},
        ]}
        scored = self.score_experiment(one)
        self.assertEqual("medium", scored["winner"])
        self.assertEqual("only passing candidate", scored["early_decisive_reason"])
        p = profile()
        rows = [record(p, score=88), record(p, score=90), record(p, score=92)]
        state = ud.promotion(rows, ud.load_policy(self.root))
        self.assertTrue(state["normal"])
        self.assertEqual("locally-proven", state["status"])

    def test_promotion_cannot_average_away_below_floor_or_regressed_outcome(self):
        policy = ud.load_policy(self.root)
        below_floor = [record(profile(), score=score) for score in (100, 100, 79)]
        self.assertGreater(ud.aggregate(below_floor)["conservative_quality"], policy["quality_floor"])
        regressed = [record(profile(), score=100) for _ in range(3)]
        regressed[-1]["regression"] = True
        for label, rows in (("below-floor legacy acceptance", below_floor), ("explicit regression", regressed)):
            with self.subTest(label=label):
                self.assertFalse(ud.promotion(rows, policy)["normal"])

    def test_report_keeps_bakeoff_overhead_separate_from_projected_savings(self):
        p = profile()
        self.call_record(record(p, score=85, cost=.5, selected=True, experiment=True))
        self.call_record(record(profile("gpt-5.6"), score=86, cost=1.0, comparator=True, experiment=True))
        data = ud.cmd_report(argparse.Namespace(root=str(self.root), report_kind="run", run_id="run-1", write=False))["data"]
        costs = data["cost"]
        self.assertEqual(.5, costs["selected_total_usd"])
        self.assertEqual(1.5, costs["experiment_total_usd"])
        # The rejected candidate is the full bakeoff investment; the projected
        # routine saving is deliberately reported separately.
        self.assertEqual(1.0, costs["experiment_overhead_usd"])
        self.assertEqual(.5, costs["projected_savings_per_task_usd"])
        self.assertEqual(2, costs["break_even_tasks"])
        self.assertEqual(0.0, costs["realized_savings_usd"])
        self.assertEqual(["run-1"], data["details"]["run_ids"])

    def test_report_labels_measured_estimated_and_unavailable_costs(self):
        measured = record(profile(), run_id="measured")
        measured_data = ud.report_data([measured], ud.load_policy(self.root))
        self.assertEqual("measured", measured_data["cost"]["selected_cost_kind"])

        estimated = record(profile(), run_id="estimated")
        estimated["metrics"].pop("cost_usd")
        estimated["usage"] = {"input_tokens": 1_000_000, "output_tokens": 500_000}
        policy = ud.load_policy(self.root)
        policy["price_table"] = {
            "gpt-5.5": {
                "effective_date": "2026-08-07",
                "input_per_million_usd": 1.0,
                "output_per_million_usd": 2.0,
            }
        }
        estimated_data = ud.report_data([estimated], policy)
        self.assertEqual("estimated", estimated_data["cost"]["selected_cost_kind"])
        self.assertEqual(2.0, estimated_data["cost"]["selected_total_usd"])

        unavailable = record(profile(), run_id="unavailable")
        unavailable["metrics"].pop("cost_usd")
        unavailable_data = ud.report_data([unavailable], ud.load_policy(self.root))
        self.assertEqual("unavailable", unavailable_data["cost"]["selected_cost_kind"])
        self.assertIsNone(unavailable_data["cost"]["selected_total_usd"])

    def test_cached_tokens_and_included_thinking_are_not_double_counted(self):
        item = record(profile())
        item["metrics"].pop("cost_usd")
        item["usage"] = {"input_tokens": 1_000_000, "cached_input_tokens": 500_000,
                         "output_tokens": 200_000, "thinking_tokens": 100_000, "thinking_in_output": True}
        policy = ud.load_policy(self.root)
        policy["price_table"] = {"gpt-5.5": {"effective_date": "2026-09-04", "input_per_million_usd": 2,
            "cached_input_per_million_usd": .5, "output_per_million_usd": 4, "thinking_per_million_usd": 4}}
        self.assertEqual((2.05, "estimated"), ud.cost(item, policy))
        item["usage"]["thinking_in_output"] = False
        self.assertAlmostEqual(2.45, ud.cost(item, policy)[0])
        del item["usage"]["thinking_in_output"]
        self.assertEqual((None, "unavailable"), ud.cost(item, policy))
        item["usage"]["thinking_in_output"] = True
        del policy["price_table"]["gpt-5.5"]["cached_input_per_million_usd"]
        self.assertEqual((None, "unavailable"), ud.cost(item, policy))

    def test_rank_records_prefers_zero_cost_and_does_not_write_fallback(self):
        rows = []
        for model, amount in (("gpt-5.5", 1.0), ("gpt-5.6", 0.0)):
            for index in range(3):
                rows.append({**record(profile(model), cost=amount, run_id=f"{model}-{index}"), "created_at": ud.now()})
        path = Path(self.temp.name) / "records.json"
        ud.write_json(path, {"records": rows})
        ranked = ud.cmd_rank(argparse.Namespace(root=str(self.root), records=str(path), context=json.dumps(self.context),
            task=json.dumps(task()), candidates=json.dumps([{"profile": profile()}, {"profile": profile("gpt-5.6")}])))["ranked"]
        self.assertEqual(ud.profile_id(profile("gpt-5.6")), ranked[0]["profile_id"])
        self.assertEqual(0, ranked[0]["cost_usd"])
        self.assertEqual("locally-proven", ranked[0]["status"])
        self.assertFalse(ud.evidence_path(self.root).exists())

    def test_unknown_empty_and_unsupported_thinking_catalogs_fail_closed(self):
        policy = ud.load_policy(self.root)
        unknown = {key: value for key, value in self.context.items() if key != "available_models"}
        self.assertEqual((False, "model capabilities unknown"), ud.eligible(profile(), unknown, policy))
        self.assertEqual((False, "model unavailable"), ud.eligible(profile(), {**self.context, "available_models": []}, policy))
        self.assertFalse(ud.eligible(profile(thinking="max", native="max"), self.context, policy)[0])

    def test_experiment_and_record_respect_project_quality_floor(self):
        ud.write_json(ud.policy_path(self.root), {"quality_floor": 95})
        experiment = {"variable": "model", "quality_floor": 80, "candidates": [
            {"id": "a", "profile": profile(), "result": result(90)},
            {"id": "b", "profile": profile("gpt-5.6"), "result": result(92)}]}
        self.assertIsNone(self.score_experiment(experiment)["winner"])
        recorded = self.call_record(record(profile(), score=90))
        self.assertFalse(recorded["accepted"])

    def test_export_is_sanitized(self):
        item = record(profile(), project_name="secret-project", paths=["/secret/file.py"],
                      prompt="do not export", raw_output="private", source_code="x=1")
        with self.assertRaises(ValueError):
            self.call_record(item)
        # Simulate an existing legacy record. New writes reject these fields,
        # while export must safely project already-persisted older evidence.
        item["profile_id"] = ud.profile_id(item["profile"])
        ud.evidence_path(self.root).write_text(json.dumps(item) + "\n")
        out = Path(self.temp.name) / "bundle.json"
        ud.cmd_export(argparse.Namespace(root=str(self.root), output=str(out)))
        rendered = out.read_text()
        self.assertNotIn("secret-project", rendered)
        self.assertNotIn("secret/file.py", rendered)
        self.assertNotIn("do not export", rendered)
        self.assertEqual(ud.SCHEMA, json.loads(rendered)["schema"])

    def test_report_and_export_accept_host_supplied_records_without_fallback_writes(self):
        records_path = Path(self.temp.name) / "cortex-records.json"
        ud.write_json(records_path, {"records": [record(profile(), score=91)]})
        report_data = ud.cmd_report(argparse.Namespace(
            root=str(self.root), records=str(records_path), report_kind="project",
            run_id=None, write=False,
        ))["data"]
        self.assertEqual(1, report_data["quality"]["evidence_count"])
        bundle_path = Path(self.temp.name) / "cortex-bundle.json"
        exported = ud.cmd_export(argparse.Namespace(
            root=str(self.root), records=str(records_path), output=str(bundle_path),
        ))
        self.assertEqual(1, exported["exported"])
        self.assertFalse(ud.evidence_path(self.root).exists())

    def trusted_bundle(self, fresh_at=None, model="gpt-5.5"):
        p = profile(model)
        return {"schema": ud.SCHEMA, "learnings": [{
            "profile_id": ud.profile_id(p), "profile": p, "task_signature": task(),
            "aggregate": {"evidence_count": 3, "pass_count": 3, "conservative_quality": 86, "mean_cost_usd": .5},
            "promotion": "locally-proven", "source_passed_gates": True,
            "fresh_at": fresh_at or ud.now(), "provenance_hash": "source-hash",
        }]}

    def test_import_trust_but_verify_is_idempotent(self):
        bundle_path = Path(self.temp.name) / "prior.json"
        ud.write_json(bundle_path, self.trusted_bundle())
        args = argparse.Namespace(root=str(self.root), input=str(bundle_path), task=json.dumps(task()),
                                  context=json.dumps(self.context), apply=True, dry_run=False)
        first = ud.cmd_import(args)
        second = ud.cmd_import(args)
        self.assertEqual(1, len(first["accepted"]))
        self.assertEqual("trusted prior pending local verification", first["accepted"][0]["reason"])
        rows = ud.read_jsonl(ud.evidence_path(self.root))
        self.assertEqual(1, len(rows))
        self.assertEqual("imported-prior-pending-verification", rows[0]["status"])
        self.assertEqual(1, len(second["accepted"]))
        ranked = ud.cmd_rank(argparse.Namespace(
            root=str(self.root), context=json.dumps(self.context), task=json.dumps(task()),
            candidates=json.dumps([{"profile": profile()}]),
        ))["ranked"]
        self.assertEqual("imported-prior-pending-verification", ranked[0]["status"])
        self.assertEqual(2, ranked[0]["tier"])
        self.assertTrue(ranked[0]["pending_verification"])

    def test_import_rejects_stale_and_unavailable_models(self):
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=31)).replace(microsecond=0).isoformat()
        bundle_path = Path(self.temp.name) / "prior.json"
        ud.write_json(bundle_path, self.trusted_bundle(old))
        args = argparse.Namespace(root=str(self.root), input=str(bundle_path), task=json.dumps(task()),
                                  context=json.dumps(self.context), apply=False, dry_run=True)
        self.assertEqual("stale", ud.cmd_import(args)["rejected"][0]["reason"])
        ud.write_json(bundle_path, self.trusted_bundle(model="gpt-5.999"))
        self.assertEqual("model unavailable", ud.cmd_import(args)["rejected"][0]["reason"])

    def test_import_rejects_contradictory_gate_counts_and_unqualified_promotion(self):
        bundle_path = Path(self.temp.name) / "counts-prior.json"
        args = argparse.Namespace(root=str(self.root), input=str(bundle_path), task=json.dumps(task()),
                                  context=json.dumps(self.context), apply=False, dry_run=True)
        for count, passes, promotion in ((3, 2, "locally-proven"), (0, 0, "explicit"), (2, 2, "locally-proven")):
            bundle = self.trusted_bundle()
            learning = bundle["learnings"][0]
            learning["aggregate"].update(evidence_count=count, pass_count=passes)
            learning["promotion"] = promotion
            ud.write_json(bundle_path, bundle)
            with self.subTest(count=count, passes=passes, promotion=promotion):
                preview = ud.cmd_import(args)
                self.assertEqual([], preview["accepted"])
                self.assertEqual(1, len(preview["rejected"]))
        bundle["learnings"][0]["promotion"] = "explicit"
        ud.write_json(bundle_path, bundle)
        self.assertEqual(1, len(ud.cmd_import(args)["accepted"]))

    def test_future_or_naive_freshness_cannot_preserve_prior(self):
        current = dt.datetime.now(dt.timezone.utc)
        policy = ud.load_policy(self.root)
        for stamp in ((current + dt.timedelta(minutes=2)).isoformat(), current.replace(tzinfo=None).isoformat(), "invalid", None):
            with self.subTest(stamp=stamp):
                self.assertTrue(ud.is_stale({"profile": profile(), "fresh_at": stamp}, policy, today=current))
        self.assertFalse(ud.is_stale({"profile": profile(), "fresh_at": current.isoformat()}, policy, today=current))

    def test_resource_abort_is_reported_without_quality_contamination(self):
        good = record(profile(), score=88)
        abort = {"profile": profile(), "accepted": False, "failure_kind": "resource", "run_id": "aborted",
                 "local_execution": {"status": "resource-aborted", "reason": "memory pressure", "local_dispatch_stopped": True}}
        self.call_record(abort)
        data = ud.report_data([good, abort], ud.load_policy(self.root))
        self.assertEqual(1, data["quality"]["evidence_count"])
        self.assertEqual(88, data["quality"]["mean_quality"])
        self.assertEqual([abort["local_execution"]], data["local_execution"]["results"])
        self.assertEqual("disabled", data["local_execution"]["mode"])
        self.assertEqual(1, ud.promotion([good, abort], ud.load_policy(self.root))["stats"]["evidence_count"])

    def test_import_yields_to_stronger_local_conflict(self):
        local = profile("gpt-5.6")
        for index, score in enumerate((88, 90, 92)):
            self.call_record(record(local, score=score, run_id=f"local-{index}"))
        bundle_path = Path(self.temp.name) / "prior.json"
        ud.write_json(bundle_path, self.trusted_bundle())
        preview = ud.cmd_import(argparse.Namespace(
            root=str(self.root), input=str(bundle_path), task=json.dumps(task()),
            context=json.dumps(self.context), apply=False, dry_run=True,
        ))
        self.assertEqual("stronger local conflict", preview["rejected"][0]["reason"])

    def test_import_strong_verification_promotes_and_ranks_as_local(self):
        bundle_path = Path(self.temp.name) / "prior.json"
        bundle = self.trusted_bundle()
        ud.write_json(bundle_path, bundle)
        ud.cmd_import(argparse.Namespace(
            root=str(self.root), input=str(bundle_path), task=json.dumps(task()),
            context=json.dumps(self.context), apply=True, dry_run=False,
        ))
        pid = bundle["learnings"][0]["profile_id"]
        verified = ud.cmd_verify_import(argparse.Namespace(
            root=str(self.root), profile_id=pid, result=json.dumps(result()),
            validation_strength="strong", comparison_run_id=None,
        ))
        self.assertEqual("locally-verified", verified["status"])
        ranked = ud.cmd_rank(argparse.Namespace(
            root=str(self.root), context=json.dumps(self.context), task=json.dumps(task()),
            candidates=json.dumps([{"profile": profile()}]),
        ))["ranked"]
        self.assertEqual("locally-verified", ranked[0]["status"])
        self.assertEqual(3, ranked[0]["tier"])

    def test_import_weak_verification_requires_comparison(self):
        bundle_path = Path(self.temp.name) / "prior.json"
        bundle = self.trusted_bundle()
        ud.write_json(bundle_path, bundle)
        ud.cmd_import(argparse.Namespace(
            root=str(self.root), input=str(bundle_path), task=json.dumps(task()),
            context=json.dumps(self.context), apply=True, dry_run=False,
        ))
        pid = bundle["learnings"][0]["profile_id"]
        pending = ud.cmd_verify_import(argparse.Namespace(
            root=str(self.root), profile_id=pid, result=json.dumps(result()),
            validation_strength="weak", comparison_run_id=None,
        ))
        self.assertEqual("comparison-required", pending["status"])
        with self.assertRaisesRegex(ud.UserError, "comparison run"):
            ud.cmd_verify_import(argparse.Namespace(
                root=str(self.root), profile_id=pid, result=json.dumps(result()),
                validation_strength="weak", comparison_run_id="nonexistent-comparison",
            ))
        self.call_record(record(profile("gpt-5.6"), run_id="comparison-1", comparator=True))
        confirmed = ud.cmd_verify_import(argparse.Namespace(
            root=str(self.root), profile_id=pid, result=json.dumps(result()),
            validation_strength="weak", comparison_run_id="comparison-1",
        ))
        self.assertEqual("locally-verified", confirmed["status"])

    def test_failed_import_is_quarantined_and_ineligible(self):
        bundle_path = Path(self.temp.name) / "prior.json"
        bundle = self.trusted_bundle()
        ud.write_json(bundle_path, bundle)
        ud.cmd_import(argparse.Namespace(
            root=str(self.root), input=str(bundle_path), task=json.dumps(task()),
            context=json.dumps(self.context), apply=True, dry_run=False,
        ))
        pid = bundle["learnings"][0]["profile_id"]
        failed = ud.cmd_verify_import(argparse.Namespace(
            root=str(self.root), profile_id=pid,
            result=json.dumps(result(score=40, accepted=False)),
            validation_strength="strong", comparison_run_id=None,
        ))
        self.assertEqual("quarantined", failed["status"])
        ranked = ud.cmd_rank(argparse.Namespace(
            root=str(self.root), context=json.dumps(self.context), task=json.dumps(task()),
            candidates=json.dumps([{"profile": profile()}]),
        ))["ranked"]
        self.assertFalse(ranked[0]["eligible"])
        self.assertEqual("quarantined imported profile", ranked[0]["reason"])
        self.assertEqual("quarantined", ranked[0]["status"])
        self.assertFalse(ranked[0]["pending_verification"])
        self.assertEqual(1, ranked[0]["tier"])

    def test_exploratory_import_cannot_skip_comparison(self):
        bundle_path = Path(self.temp.name) / "prior.json"
        bundle = self.trusted_bundle()
        bundle["learnings"][0]["promotion"] = "early-decisive"
        bundle["learnings"][0]["confidence"] = "moderate"
        ud.write_json(bundle_path, bundle)
        preview = ud.cmd_import(argparse.Namespace(
            root=str(self.root), input=str(bundle_path), task=json.dumps(task()),
            context=json.dumps(self.context), apply=True, dry_run=False,
        ))
        self.assertTrue(preview["accepted"][0]["comparison_required"])
        pid = bundle["learnings"][0]["profile_id"]
        pending = ud.cmd_verify_import(argparse.Namespace(
            root=str(self.root), profile_id=pid, result=json.dumps(result()),
            validation_strength="strong", comparison_run_id=None,
        ))
        self.assertEqual("comparison-required", pending["status"])

    def test_catalog_promotion_uses_global_home_and_only_after_explicit_action(self):
        p = profile()
        for score in (88, 90, 92): self.call_record(record(p, score=score))
        global_home = Path(self.temp.name) / "global"
        with patch.dict(os.environ, {"ULTRA_DELEGATION_HOME": str(global_home)}):
            promoted = ud.cmd_catalog_promote(argparse.Namespace(root=str(self.root), profile_id=ud.profile_id(p), force=False))
            self.assertTrue(Path(promoted["catalog"]).exists())
            listed = ud.cmd_catalog_list(argparse.Namespace())
            self.assertEqual(1, len(listed["entries"]))
            summary = ud.cmd_catalog_report(argparse.Namespace())
            self.assertEqual(["python-edit"], summary["task_families"])

    def test_catalog_and_export_never_combine_incomparable_operations(self):
        p = profile()
        for index, operation in enumerate(("refactor", "migration", "rename")):
            item = record(p, score=90, run_id=f"mixed-{index}")
            item["task_signature"] = {**task(), "operation": operation}
            self.call_record(item)
        with self.assertRaisesRegex(ud.UserError, "no locally proven comparable task group"):
            ud.cmd_catalog_promote(argparse.Namespace(
                root=str(self.root), profile_id=ud.profile_id(p), force=False,
            ))
        output = Path(self.temp.name) / "mixed-bundle.json"
        ud.cmd_export(argparse.Namespace(root=str(self.root), output=str(output)))
        learnings = ud.read_json(output)["learnings"]
        self.assertEqual(3, len(learnings))
        self.assertEqual({1}, {item["aggregate"]["evidence_count"] for item in learnings})

    def test_rank_discovers_eligible_global_catalog_prior(self):
        p = profile()
        entry = self.trusted_bundle()["learnings"][0]
        global_home = Path(self.temp.name) / "global"
        global_home.mkdir()
        with patch.dict(os.environ, {"ULTRA_DELEGATION_HOME": str(global_home)}):
            ud.append_jsonl(global_home / "catalog.jsonl", entry)
            ranked = ud.cmd_rank(argparse.Namespace(
                root=str(self.root), context=json.dumps(self.context), task=json.dumps(task()),
                candidates=json.dumps([{"profile": profile("gpt-5.6")}]),
            ))["ranked"]
        self.assertEqual(ud.profile_id(p), ranked[0]["profile_id"])
        self.assertEqual("global", ranked[0]["source"])
        self.assertTrue(ranked[0]["pending_verification"])

    def test_rank_does_not_route_stale_global_catalog_prior(self):
        entry = self.trusted_bundle()["learnings"][0]
        entry["fresh_at"] = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=31)
        ).replace(microsecond=0).isoformat()
        global_home = Path(self.temp.name) / "global"
        global_home.mkdir()
        with patch.dict(os.environ, {"ULTRA_DELEGATION_HOME": str(global_home)}):
            ud.append_jsonl(global_home / "catalog.jsonl", entry)
            ranked = ud.cmd_rank(argparse.Namespace(
                root=str(self.root), context=json.dumps(self.context), task=json.dumps(task()),
                candidates=json.dumps([]),
            ))["ranked"]
        self.assertFalse(ranked[0]["pending_verification"])
        self.assertEqual(1, ranked[0]["tier"])

        entry["profile"]["model_revision"] = "gpt-5.5-2026-06-01"
        entry["fresh_at"] = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=31)
        ).replace(microsecond=0).isoformat()
        self.assertFalse(ud.is_stale(entry, ud.load_policy(self.root)))

    def test_rank_does_not_transfer_local_proof_between_operations(self):
        p = profile()
        for index, score in enumerate((88, 90, 92)):
            self.call_record(record(p, score=score, run_id=f"refactor-{index}"))
        migration = {**task(), "operation": "migration"}
        ranked = ud.cmd_rank(argparse.Namespace(
            root=str(self.root), context=json.dumps(self.context), task=json.dumps(migration),
            candidates=json.dumps([{"profile": p}]),
        ))["ranked"]
        self.assertEqual("provisional", ranked[0]["status"])
        self.assertEqual(1, ranked[0]["tier"])
        self.assertEqual(0, ranked[0]["stats"]["evidence_count"])

    def test_helper_has_no_process_or_network_execution_primitives(self):
        tree = ast.parse(HELPER.read_text())
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue({"subprocess", "socket", "urllib", "requests", "httpx", "aiohttp"}.isdisjoint(imported))
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue({"system", "popen", "spawn", "urlopen"}.isdisjoint(calls))

    def test_isolation_refuses_unsafe_and_unmanaged_cleanup(self):
        prepared = ud.cmd_isolation(argparse.Namespace(root=str(self.root), isolation_action="prepare", name="trial", mode="patch-proposal"))
        target = Path(prepared["prepared"])
        self.assertTrue((target / "manifest.json").exists())
        cleaned = ud.cmd_isolation(argparse.Namespace(root=str(self.root), isolation_action="cleanup", name="trial"))
        self.assertFalse(Path(cleaned["cleaned"]).exists())
        with self.assertRaisesRegex(ud.UserError, "unsafe isolation path"):
            ud.cmd_isolation(argparse.Namespace(root=str(self.root), isolation_action="prepare", name="../escape", mode="patch-proposal"))
        unmanaged = self.root / "runs" / "isolation" / "unmanaged"
        unmanaged.mkdir(parents=True)
        with self.assertRaisesRegex(ud.UserError, "managed manifest"):
            ud.cmd_isolation(argparse.Namespace(root=str(self.root), isolation_action="cleanup", name="unmanaged"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
