import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from common import Fixture

CLI = Path(__file__).resolve().parents[1] / "scripts" / "rover.py"


class RoutingTests(Fixture):
    def setUp(self):
        super().setUp()
        self.store = self.module("store").Store(self.base / "state")
        self.life = self.module("lifecycle")
        self.integration = self.module("integration")

    def prompt(self, turn="turn-1", now=100):
        return self.integration.hook({"session_id": "s", "hook_event_name": "UserPromptSubmit",
                                      "turn_id": turn, "prompt": "private task content"}, self.store, now=now)

    def test_empty_catalog_still_receives_routing_check_without_enrolling_candidates(self):
        result = self.prompt()
        self.assertTrue(result["hookSpecificOutput"]["additionalContext"])
        state = self.store.read()
        self.assertEqual(state["entries"], {})
        self.assertEqual(state["routing"]["s"]["checks"], 1)
        self.assertEqual(state["routing"]["s"]["decision"], "pending")
        self.assertNotIn("private task content", json.dumps(state))

    def test_same_turn_hook_does_not_reset_completed_decision(self):
        self.prompt()
        routing = self.module("routing")
        routing.record(self.store, "s", "none", "Simple factual question", now=101)
        self.prompt(now=102)
        state = self.store.read()["routing"]["s"]
        self.assertEqual(state["checks"], 1)
        self.assertEqual(state["decision"], "none")
        self.prompt("turn-2", now=103)
        self.assertEqual(self.store.read()["routing"]["s"]["checks"], 2)
        self.assertEqual(self.store.read()["routing"]["s"]["decision"], "pending")

    def test_pending_route_receives_one_followup_then_stays_quiet(self):
        self.prompt()
        payload = {"session_id": "s", "hook_event_name": "PostToolUse"}
        self.assertIn("hookSpecificOutput", self.integration.hook(payload, self.store, now=101))
        self.assertEqual(self.integration.hook(payload, self.store, now=102), {})
        self.assertEqual(self.store.read()["entries"], {})

    def test_new_prompt_is_not_suppressed_by_due_reminder_throttle(self):
        entry = self.life.install(self.store, self.skill(), review_seconds=1, now=0)
        self.life.load(self.store, entry["id"], "s", now=1)
        self.prompt(now=2)
        result = self.prompt("turn-2", now=3)
        self.assertIn("hookSpecificOutput", result)
        self.assertIsNone(self.store.read()["entries"][entry["id"]]["reviewed_at"])

    def test_use_enrolls_loads_and_records_selection_without_postponing_deadline(self):
        routing = self.module("routing")
        source = self.skill()
        self.prompt()
        first = routing.use(self.store, source, "s", "Preserves invoice columns", review_seconds=60, now=100)
        second = routing.use(self.store, source, "s", "Same extraction task", review_seconds=3000, now=159)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["loaded_at"], 100)
        self.assertEqual(second["last_used_at"], 159)
        self.assertEqual(len(self.store.read()["entries"]), 1)
        self.assertEqual(self.store.read()["routing"]["s"]["selected_ids"], [first["id"]])
        self.assertEqual(self.life.due(self.store, now=160)[0]["due_at"], 160)
        self.assertTrue((source / "SKILL.md").exists())

    def test_old_turn_use_cannot_complete_a_new_turns_routing_check(self):
        routing = self.module("routing")
        self.prompt(now=100)
        loaded, resume = threading.Event(), threading.Event()
        original_load = self.life.load

        def paused_load(*args, **kwargs):
            result = original_load(*args, **kwargs)
            loaded.set()
            if not resume.wait(5):
                raise RuntimeError("test synchronization timed out")
            return result

        with patch.object(self.life, "load", paused_load), ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(routing.use, self.store, self.skill(), "s", "Old task fit", now=101)
            try:
                self.assertTrue(loaded.wait(5))
                self.prompt("turn-2", now=110)
            finally:
                resume.set()
            result = future.result(timeout=5)
        current = self.store.read()["routing"]["s"]
        self.assertEqual(current["decision"], "pending")
        self.assertIsNone(current["decided_at"])
        self.assertIn(result["id"], self.store.read()["uses"]["s"])

    def test_stale_explicit_check_does_not_mark_current_turn_as_none(self):
        routing = self.module("routing")
        self.prompt(now=100)
        first = self.store.read()["routing"]["s"]
        self.prompt("turn-2", now=110)
        result = routing.record(self.store, "s", "none", "Old question was simple",
                                check_id=first["check_id"], now=111)
        self.assertFalse(result["recorded"])
        self.assertEqual(self.store.read()["routing"]["s"]["decision"], "pending")

    def test_use_cannot_reload_usage_after_session_ended(self):
        routing = self.module("routing")
        self.prompt(now=100)
        installed, resume = threading.Event(), threading.Event()
        original_install = self.life.install

        def paused_install(*args, **kwargs):
            result = original_install(*args, **kwargs)
            installed.set()
            if not resume.wait(5):
                raise RuntimeError("test synchronization timed out")
            return result

        with patch.object(self.life, "install", paused_install), ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(routing.use, self.store, self.skill(), "s", "Task fit", now=101)
            try:
                self.assertTrue(installed.wait(5))
                self.integration.hook({"session_id": "s", "hook_event_name": "SessionEnd"}, self.store, now=110)
            finally:
                resume.set()
            with self.assertRaises(ValueError):
                future.result(timeout=5)
        self.assertEqual(self.store.read()["uses"], {})
        self.assertIsNone(next(iter(self.store.read()["entries"].values()))["loaded_at"])

    def test_session_start_allows_loading_again_after_verified_session_end(self):
        entry = self.life.install(self.store, self.skill(), now=0)
        self.integration.hook({"session_id": "s", "hook_event_name": "SessionEnd"}, self.store, now=100)
        with self.assertRaises(ValueError):
            self.life.load(self.store, entry["id"], "s", now=101)
        self.integration.hook({"session_id": "s", "hook_event_name": "SessionStart"}, self.store, now=110)
        self.life.load(self.store, entry["id"], "s", now=111)
        self.assertEqual(self.store.read()["uses"]["s"], [entry["id"]])

    def test_duplicate_session_start_preserves_live_check_and_completed_decision(self):
        payload = {"session_id": "s", "hook_event_name": "SessionStart"}
        self.integration.hook(payload, self.store, now=100)
        first = self.store.read()["routing"]["s"]["check_id"]
        self.module("routing").record(self.store, "s", "none", "No specialized workflow needed", now=101)
        self.integration.hook(payload, self.store, now=102)
        current = self.store.read()["routing"]["s"]
        self.assertEqual(current["check_id"], first)
        self.assertEqual(current["decision"], "none")

    def test_late_prompt_cannot_reopen_an_ended_session(self):
        self.prompt(now=100)
        self.integration.hook({"session_id": "s", "hook_event_name": "SessionEnd"}, self.store, now=110)
        closed = self.store.read()
        for turn in ("late-turn", None):
            payload = {"session_id": "s", "hook_event_name": "UserPromptSubmit"}
            if turn is not None:
                payload["turn_id"] = turn
            with self.assertRaises(ValueError):
                self.integration.hook(payload, self.store, now=111)
            self.assertEqual(self.store.read(), closed)
        self.integration.hook({"session_id": "s", "hook_event_name": "SessionStart"}, self.store, now=120)
        self.assertIn("hookSpecificOutput", self.prompt("fresh-turn", now=121))

    def test_nested_corrupt_routing_state_is_preserved_and_hook_fails_open(self):
        self.store.root.mkdir()
        for invalid in [[], {"checks": 0, "decision": "selected", "selected_ids": "bad"},
                        {"checks": 0, "decision": "invented"}, {"checks": 0, "ended_at": "bad"}]:
            with self.subTest(invalid=invalid):
                state = {"version": 1, "entries": {}, "uses": {}, "history": [], "notices": {}, "routing": {"s": invalid}}
                raw = json.dumps(state)
                self.store.path.write_text(raw)
                result = subprocess.run([sys.executable, str(CLI), "--state-dir", str(self.store.root), "hook"],
                                        input=json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "s"}),
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout), {})
                self.assertIn("error", json.loads(result.stderr))
                self.assertEqual(self.store.path.read_text(), raw)

    def test_use_rejects_implicit_only_policy_before_copying(self):
        routing = self.module("routing")
        source = self.skill(extra="disable-model-invocation: true\n")
        with self.assertRaises(ValueError):
            routing.use(self.store, source, "s", "Wanted extractor", now=100)
        self.assertEqual(self.store.read()["entries"], {})
        self.assertFalse((self.store.root / "packages").exists())

    def test_use_validates_session_and_reason_before_installation(self):
        routing = self.module("routing")
        for session, reason in [("", "Task fit"), ("s", "")]:
            with self.assertRaises(ValueError):
                routing.use(self.store, self.skill(), session, reason, now=100)
        self.assertEqual(self.store.read()["entries"], {})

    def test_status_distinguishes_installed_loaded_and_in_use_and_exposes_next_review(self):
        routing = self.module("routing")
        unloaded = self.life.install(self.store, self.skill("unused"), now=0)
        used = routing.use(self.store, self.skill("used"), "s", "Task fit", review_seconds=60, now=100)
        self.life.release(self.store, "s")
        report = routing.status(self.store, now=101)
        self.assertEqual(report["summary"]["managed_active"], 2)
        self.assertEqual(report["summary"]["ever_loaded"], 1)
        self.assertEqual(report["summary"]["in_use"], 0)
        schedule = {row["id"]: row for row in report["review_schedule"]}
        self.assertEqual(schedule[used["id"]]["next_review_at"], 160)
        self.assertIsNone(schedule[unloaded["id"]]["next_review_at"])
        self.assertEqual(report["summary"]["next_review_at"], 160)

    def test_status_preserves_old_state_without_optional_routing_field(self):
        self.store.root.mkdir()
        old = {"version": 1, "entries": {}, "uses": {}, "history": [], "notices": {}}
        self.store.path.write_text(json.dumps(old))
        report = self.module("routing").status(self.store, now=100)
        self.assertEqual(report["summary"]["routing_checks"], 0)
        self.assertEqual(json.loads(self.store.path.read_text()), old)

    def test_unreviewed_use_cli_is_rejected_without_enrollment(self):
        result = subprocess.run([sys.executable, str(CLI), "--state-dir", str(self.store.root),
                                 "use", str(self.skill()), "--session", "s", "--reason", "Task fit"],
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.store.read()["entries"], {})

    def test_use_cli_returns_instructions_and_status_schedule(self):
        source = self.skill()
        result = subprocess.run([sys.executable, str(CLI), "--state-dir", str(self.store.root),
                                 "use", str(source), "--reviewed", "--session", "s", "--reason", "Task fit"],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertIn("Extract PDF tables.", output["instructions"])
        status = subprocess.run([sys.executable, str(CLI), "--state-dir", str(self.store.root), "status"],
                                text=True, capture_output=True)
        report = json.loads(status.stdout)
        self.assertEqual(report["summary"]["ever_loaded"], 1)
        self.assertEqual(report["review_schedule"][0]["next_review_at"] - output["loaded_at"], 86400)

    def test_global_hook_uses_payload_project_unless_explicit_state_is_supplied(self):
        project = self.base / "project"
        project.mkdir()
        payload = {"hook_event_name": "UserPromptSubmit", "session_id": "s", "cwd": str(project)}
        for prefix, expected in [([], project / ".skill-rover"),
                                 (["--state-dir", str(self.store.root)], self.store.root)]:
            result = subprocess.run([sys.executable, str(CLI), *prefix, "hook"], cwd=self.base,
                                    input=json.dumps(payload), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(str(expected), json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])
            self.assertTrue((expected / "state.json").exists())
        self.assertFalse((self.base / ".skill-rover").exists())
